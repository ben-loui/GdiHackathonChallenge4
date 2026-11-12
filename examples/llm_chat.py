"""
Beispiel-Chat: beliebiges LLM mit OpenAI-kompatibler Chat-Completions-API + Zuständigkeitsfinder-MCP-Server.

Für LLMs ohne eigenen MCP-Client. Das Skript holt die Tools vom MCP-Server, bietet sie dem LLM per
Function Calling an und führt dessen Tool-Aufrufe über MCP aus.

    export MISTRAL_API_KEY=...
    python examples/llm_chat.py --anbieter mistral
    python examples/llm_chat.py --anbieter ollama --modell qwen3          # lokal, kein Key
    python examples/llm_chat.py --anbieter openai --frage "Welches Jobcenter ist für Domplatz 1, 55116 Mainz zuständig?"
    python examples/llm_chat.py --anbieter eigen --base-url https://.../v1 --modell <name>   # Key in LLM_API_KEY

Ohne --server startet das Skript den MCP-Server selbst (stdio). Mit --server http://localhost:8000/mcp
oder einer Tunnel-URL wird ein laufender Server verwendet.

Für Claude gibt es examples/claude_chat.py (offizielles Anthropic-SDK).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Awaitable, Callable

import anyio
import requests
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent
MAX_TOOL_RUNDEN = 6


@dataclass(frozen=True)
class Anbieter:
    base_url: str
    key_env: str | None
    modell: str | None


# Standardmodelle lassen sich mit --modell oder LLM_MODEL überschreiben.
ANBIETER: dict[str, Anbieter] = {
    "mistral": Anbieter("https://api.mistral.ai/v1", "MISTRAL_API_KEY", "mistral-large-latest"),
    "openai": Anbieter("https://api.openai.com/v1", "OPENAI_API_KEY", "gpt-4.1-mini"),
    "openrouter": Anbieter("https://openrouter.ai/api/v1", "OPENROUTER_API_KEY", None),
    "ollama": Anbieter("http://localhost:11434/v1", None, "qwen3"),
    "lmstudio": Anbieter("http://localhost:1234/v1", None, None),
    "eigen": Anbieter("", "LLM_API_KEY", None),
}


def mcp_tools_als_functions(tools) -> list[dict]:
    """MCP-Tool-Definitionen -> OpenAI-kompatible `tools`-Liste (Function Calling)."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or t.title or t.name,
                "parameters": t.input_schema or {"type": "object", "properties": {}},
            },
        }
        for t in tools
    ]


def tool_ergebnis_text(ergebnis) -> str:
    text = "\n".join(c.text for c in ergebnis.content if getattr(c, "type", "") == "text")
    return f"FEHLER: {text}" if ergebnis.is_error else text


def chat_completion(base_url: str, api_key: str | None, modell: str, messages: list, tools: list) -> dict:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    r = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers=headers,
        json={"model": modell, "messages": messages, "tools": tools, "tool_choice": "auto"},
        timeout=180,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"LLM-API antwortet {r.status_code}: {r.text[:500]}")
    return r.json()


async def antworte(
    messages: list,
    tools: list,
    llm: Callable[[list, list], Awaitable[dict]],
    tool_aufrufen: Callable[[str, dict], Awaitable[str]],
    log: Callable[[str], None] = lambda s: None,
) -> str:
    """Eine Nutzerfrage beantworten: LLM fragen, Tool-Aufrufe ausführen, bis eine Textantwort kommt."""
    for _ in range(MAX_TOOL_RUNDEN):
        antwort = await llm(messages, tools)
        msg = antwort["choices"][0]["message"]
        aufrufe = msg.get("tool_calls") or []
        messages.append({"role": "assistant", "content": msg.get("content") or "",
                         **({"tool_calls": aufrufe} if aufrufe else {})})
        if not aufrufe:
            return msg.get("content") or ""
        for a in aufrufe:
            name = a["function"]["name"]
            try:
                argumente = json.loads(a["function"].get("arguments") or "{}")
            except json.JSONDecodeError as e:
                ergebnis = f"FEHLER: Argumente sind kein gültiges JSON ({e})."
            else:
                log(f"  → Tool {name}({json.dumps(argumente, ensure_ascii=False)})")
                ergebnis = await tool_aufrufen(name, argumente)
            messages.append({"role": "tool", "tool_call_id": a["id"], "content": ergebnis})
    return "(Abbruch: zu viele Tool-Aufrufe in Folge)"


def _konfiguration(args) -> tuple[str, str | None, str]:
    a = ANBIETER[args.anbieter]
    base_url = args.base_url or os.environ.get("LLM_BASE_URL") or a.base_url
    modell = args.modell or os.environ.get("LLM_MODEL") or a.modell
    api_key = os.environ.get("LLM_API_KEY") or (os.environ.get(a.key_env) if a.key_env else None)
    if not base_url:
        sys.exit("Basis-URL fehlt: --base-url oder LLM_BASE_URL setzen.")
    if not modell:
        sys.exit(f"Kein Standardmodell für '{args.anbieter}': --modell angeben.")
    if a.key_env and not api_key:
        sys.exit(f"API-Key fehlt: export {a.key_env}=... (oder LLM_API_KEY)")
    return base_url, api_key, modell


async def _main(args) -> None:
    base_url, api_key, modell = _konfiguration(args)
    ziel = args.server or StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "mcp_server.py"), "--transport", "stdio"], cwd=str(ROOT)
    )
    async with Client(ziel, read_timeout_seconds=180) as mcp:
        tools = mcp_tools_als_functions((await mcp.list_tools()).tools)
        messages: list[dict] = [{"role": "system", "content": mcp.instructions or ""}]
        print(f"Modell: {modell} @ {base_url} | Tools: {', '.join(t['function']['name'] for t in tools)}")

        async def llm(msgs, tls):
            return await anyio.to_thread.run_sync(chat_completion, base_url, api_key, modell, msgs, tls)

        async def tool_aufrufen(name, argumente):
            return tool_ergebnis_text(await mcp.call_tool(name, argumente))

        fragen = [args.frage] if args.frage else None
        while True:
            if fragen is not None:
                if not fragen:
                    break
                frage = fragen.pop(0)
                print(f"\nDu: {frage}")
            else:
                try:
                    frage = await anyio.to_thread.run_sync(input, "\nDu: ")
                except EOFError:
                    break
                if frage.strip().lower() in {"", "exit", "quit", "ende"}:
                    break
            messages.append({"role": "user", "content": frage})
            print("\nLLM:", await antworte(messages, tools, llm, tool_aufrufen, log=print))


def main() -> None:
    p = argparse.ArgumentParser(description="Beliebiges LLM (OpenAI-kompatibel) + Zuständigkeitsfinder-MCP")
    p.add_argument("--anbieter", choices=sorted(ANBIETER), default=os.environ.get("LLM_ANBIETER", "mistral"))
    p.add_argument("--modell", help="Modellname, überschreibt den Standard des Anbieters")
    p.add_argument("--base-url", help="Basis-URL der Chat-Completions-API (endet meist auf /v1)")
    p.add_argument("--server", help="MCP-URL, z. B. http://localhost:8000/mcp (Standard: lokal über stdio)")
    p.add_argument("--frage", help="Eine Frage stellen und beenden (sonst interaktiv)")
    anyio.run(_main, p.parse_args())


if __name__ == "__main__":
    main()
