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
