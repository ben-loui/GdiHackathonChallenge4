"""
Beispiel-Chat: Claude über die Anthropic-API + Zuständigkeitsfinder-MCP-Server.

Nutzt das offizielle Anthropic-SDK: Die MCP-Tools werden mit `async_mcp_tool` in Claude-Tools umgewandelt,
der Tool Runner übernimmt die Schleife aus Modellantwort und Tool-Aufruf.

    pip install "anthropic[mcp]"
    export ANTHROPIC_API_KEY=...          # oder vorher: ant auth login
    python examples/claude_chat.py
    python examples/claude_chat.py --frage "Welches Amtsgericht ist für Schillerplatz 1, 55116 Mainz zuständig?"
    python examples/claude_chat.py --server http://localhost:8000/mcp

Ohne --server startet das Skript den MCP-Server selbst (stdio).
Für Claude.ai, Claude Desktop und Claude Code ist kein Skript nötig, siehe docs/llm-clients.md.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import anyio
from anthropic import AsyncAnthropic
from anthropic.lib.tools.mcp import async_mcp_tool
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent
MODELL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")


async def frage_stellen(claude: AsyncAnthropic, tools: list, system: str, verlauf: list, frage: str) -> str:
    verlauf.append({"role": "user", "content": frage})
    runner = claude.beta.messages.tool_runner(
        model=MODELL,
        max_tokens=16000,
        system=system,
        tools=tools,
        messages=verlauf,
        output_config={"effort": "low"},  # einfache Auskunft; für schwierige Fälle "medium"/"high"
        # Lehnt das Modell aus Sicherheitsgründen ab, übernimmt automatisch ein Ersatzmodell.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    letzte = None
    async for nachricht in runner:
        letzte = nachricht
        for block in nachricht.content:
            if block.type == "tool_use":
                print(f"  → Tool {block.name}({json.dumps(block.input, ensure_ascii=False)})")
    if letzte is None:
        return ""
    if letzte.stop_reason == "refusal":
        return "(Claude hat die Anfrage abgelehnt.)"
    text = "".join(b.text for b in letzte.content if b.type == "text")
    verlauf.append({"role": "assistant", "content": text})
    return text


async def _main(args) -> None:
    ziel = args.server or StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "mcp_server.py"), "--transport", "stdio"], cwd=str(ROOT)
    )
    claude = AsyncAnthropic()
    async with Client(ziel, read_timeout_seconds=180) as mcp:
        tools = [async_mcp_tool(t, mcp) for t in (await mcp.list_tools()).tools]
        system = mcp.instructions or ""
        print(f"Modell: {MODELL} | Tools: {', '.join(t.name for t in tools)}")
        verlauf: list = []
        while True:
            if args.frage:
                frage = args.frage
                print(f"\nDu: {frage}")
            else:
                try:
                    frage = await anyio.to_thread.run_sync(input, "\nDu: ")
                except EOFError:
                    break
                if frage.strip().lower() in {"", "exit", "quit", "ende"}:
                    break
            print("\nClaude:", await frage_stellen(claude, tools, system, verlauf, frage))
            if args.frage:
                break


def main() -> None:
    p = argparse.ArgumentParser(description="Claude + Zuständigkeitsfinder-MCP (Anthropic-SDK)")
    p.add_argument("--server", help="MCP-URL, z. B. http://localhost:8000/mcp (Standard: lokal über stdio)")
    p.add_argument("--frage", help="Eine Frage stellen und beenden (sonst interaktiv)")
    anyio.run(_main, p.parse_args())


if __name__ == "__main__":
    main()
