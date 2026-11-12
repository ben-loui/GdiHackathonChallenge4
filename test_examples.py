"""Offline-Tests der Beispiel-Chats: kein LLM-Aufruf, kein Internet (Mock-WFS aus conftest.py)."""
import importlib.util
import json
import sys
from pathlib import Path

import anyio
import pytest
from mcp.client import Client

import mcp_server

BEISPIELE = Path(__file__).with_name("examples")


def _lade(name):
    spec = importlib.util.spec_from_file_location(name, BEISPIELE / f"{name}.py")
    modul = importlib.util.module_from_spec(spec)
    sys.modules[name] = modul  # nötig für dataclasses
    spec.loader.exec_module(modul)
    return modul


llm_chat = _lade("llm_chat")


def _tool_call(args):
    return {"choices": [{"message": {"content": None, "tool_calls": [{
        "id": "call_1", "type": "function",
        "function": {"name": "zustaendigkeit_finden", "arguments": json.dumps(args)},
    }]}}]}


def _text(t):
    return {"choices": [{"message": {"content": t}}]}


def test_llm_chat_fuehrt_tool_ueber_mcp_aus(zf):
    """Gescriptetes LLM ruft das Tool auf, das Ergebnis landet als tool-Nachricht im Verlauf."""
    antworten = [_tool_call({"lat": 50.5, "lon": 8.5, "behoerdentypen": ["arbeitsagentur"]}),
                 _text("Zuständig ist die AG West.")]
    gesehen = []

    async def go():
        async with Client(mcp_server.server) as mcp:
            tools = llm_chat.mcp_tools_als_functions((await mcp.list_tools()).tools)

            async def llm(msgs, tls):
                gesehen.append(tls)
                return antworten.pop(0)

            async def tool(name, args):
                return llm_chat.tool_ergebnis_text(await mcp.call_tool(name, args))

            messages = [{"role": "user", "content": "Wer ist zuständig?"}]
            return await llm_chat.antworte(messages, tools, llm, tool), messages

    text, messages = anyio.run(go)
    assert text == "Zuständig ist die AG West."
    fn = gesehen[0][0]["function"]
    assert fn["name"] == "zustaendigkeit_finden" and fn["parameters"]["type"] == "object"
    tool_msg = next(m for m in messages if m["role"] == "tool")
    assert tool_msg["tool_call_id"] == "call_1"
    assert json.loads(tool_msg["content"])["ergebnisse"][0]["zustaendig"] == ["AG West"]


def test_llm_chat_ungueltiges_json_wird_zurueckgemeldet(zf):
    kaputt = _tool_call({})
    kaputt["choices"][0]["message"]["tool_calls"][0]["function"]["arguments"] = "{kein json"
    antworten = [kaputt, _text("ok")]

    async def go():
        async def llm(m, t):
            return antworten.pop(0)

        async def tool(n, a):
            raise AssertionError("darf nicht aufgerufen werden")

        messages = []
        await llm_chat.antworte(messages, [], llm, tool)
        return messages

    messages = anyio.run(go)
    assert next(m for m in messages if m["role"] == "tool")["content"].startswith("FEHLER")


def test_llm_chat_konfiguration(monkeypatch):
    import argparse

    for v in ("LLM_BASE_URL", "LLM_MODEL", "LLM_API_KEY", "MISTRAL_API_KEY"):
        monkeypatch.delenv(v, raising=False)
    args = argparse.Namespace(anbieter="ollama", base_url=None, modell=None)
    assert llm_chat._konfiguration(args) == ("http://localhost:11434/v1", None, "qwen3")
    monkeypatch.setenv("MISTRAL_API_KEY", "k")
    args = argparse.Namespace(anbieter="mistral", base_url=None, modell="mistral-small-latest")
    assert llm_chat._konfiguration(args) == ("https://api.mistral.ai/v1", "k", "mistral-small-latest")
    monkeypatch.delenv("MISTRAL_API_KEY")
    with pytest.raises(SystemExit):
        llm_chat._konfiguration(argparse.Namespace(anbieter="mistral", base_url=None, modell=None))


def test_claude_chat_wandelt_mcp_tools_um(zf):
    pytest.importorskip("anthropic")
    from anthropic.lib.tools.mcp import async_mcp_tool

    _lade("claude_chat")  # Import und Syntax prüfen

    async def go():
        async with Client(mcp_server.server) as mcp:
            tool = async_mcp_tool((await mcp.list_tools()).tools[0], mcp)
            definition = tool.to_dict()
            ergebnis = await tool.call({"lat": 50.5, "lon": 8.5, "behoerdentypen": ["arbeitsagentur"]})
            return definition, ergebnis

    definition, ergebnis = anyio.run(go)
    assert definition["name"] == "zustaendigkeit_finden"
    assert "AG West" in json.dumps(ergebnis, default=str, ensure_ascii=False)
