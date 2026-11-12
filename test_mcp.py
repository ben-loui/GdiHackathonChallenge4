"""Tests des MCP-Servers (Fixture `zf` aus conftest.py)."""
import json

import anyio
from mcp.client import Client
import mcp_server

def _call(name, args):
    async def go():
        async with Client(mcp_server.server) as c:
            tools = await c.list_tools()
            r = await c.call_tool(name, args)
            return tools, r
    return anyio.run(go)

def test_tool_liste_und_schema(zf):
    tools, _ = _call("zustaendigkeit_finden", {"lat": 50.5, "lon": 8.5, "behoerdentypen": ["arbeitsagentur"]})
    t = tools.tools[0]
    assert t.name == "zustaendigkeit_finden" and t.annotations.read_only_hint
    enum = t.input_schema["properties"]["behoerdentypen"]
    assert "jobcenter" in json.dumps(enum)

def test_treffer(zf):
    _, r = _call("zustaendigkeit_finden", {"lat": 50.5, "lon": 8.5, "behoerdentypen": ["arbeitsagentur"]})
    assert not r.is_error
    daten = json.loads(r.content[0].text)
    assert daten["ergebnisse"][0]["zustaendig"] == ["AG West"]

def test_fehler_als_toolerror(zf, monkeypatch):
    def nf(a): raise zf.AdresseNichtGefunden("Keine Koordinate.")
    monkeypatch.setattr(zf, "geocode", nf)
    _, r = _call("zustaendigkeit_finden", {"adresse": "Nirgendwo 1"})
    assert r.is_error and "Hausnummer" in r.content[0].text

def test_ungueltiger_typ(zf):
    _, r = _call("zustaendigkeit_finden", {"lat": 50.5, "lon": 8.5, "behoerdentypen": ["kfz"]})
    assert r.is_error


def test_stdio_transport_startet_und_listet_tools():
    """Startet den Server wie ein lokaler Client (Claude Desktop, Cursor) als Unterprozess über stdio."""
    import sys
    from pathlib import Path

    from mcp.client.stdio import StdioServerParameters

    skript = Path(__file__).with_name("mcp_server.py")
    params = StdioServerParameters(command=sys.executable, args=[str(skript), "--transport", "stdio"],
                                   cwd=str(Path(skript).parent.parent))

    async def go():
        async with Client(params) as c:
            return [t.name for t in (await c.list_tools()).tools]

    assert anyio.run(go) == ["zustaendigkeit_finden"]


def test_cli_standardwerte(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("ZF_TRANSPORT", raising=False)
    args = mcp_server._argumente([])
    assert (args.transport, args.port) == ("http", 8000)
    monkeypatch.setenv("PORT", "9000")
    assert mcp_server._argumente(["--transport", "stdio"]).port == 9000
