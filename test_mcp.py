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
    t = next(x for x in tools.tools if x.name == "zustaendigkeit_finden")
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

    assert sorted(anyio.run(go)) == ["behoerde_finden", "zustaendigkeit_finden"]


def test_cli_standardwerte(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    monkeypatch.delenv("ZF_TRANSPORT", raising=False)
    args = mcp_server._argumente([])
    assert (args.transport, args.port) == ("http", 8000)
    monkeypatch.setenv("PORT", "9000")
    assert mcp_server._argumente(["--transport", "stdio"]).port == 9000


def test_health_endpunkt():
    from starlette.testclient import TestClient

    with TestClient(mcp_server.server.streamable_http_app()) as c:
        r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok" and r.json()["mcp_endpunkt"] == "/mcp"


def test_behoerde_finden_tool(zf, pvog_mock):
    _, r = _call("behoerde_finden", {"kategorie": "Bürgerbüro", "lat": 50.5, "lon": 8.5})
    assert not r.is_error
    daten = json.loads(r.content[0].text)
    assert daten["kategorie"] == "Bürgeramt / Bürgerbüro" and daten["eindeutig"]
    s = daten["stellen"][0]
    assert s["name"] == "Bürgerbüro" and s["telefon"] == ["06151 1150"] and "pvog_id" not in s
    assert "VG250" in daten["quelle"] and "PVOG" in daten["quelle"]


def test_behoerde_finden_unbekannte_kategorie(zf, pvog_mock):
    _, r = _call("behoerde_finden", {"kategorie": "Hundefriseur", "lat": 50.5, "lon": 8.5})
    assert r.is_error and "Erlaubt" in r.content[0].text


def test_anweisungen_nennen_kategorien_und_keine_veraltete_einschraenkung():
    assert "finanzamt (Finanzamt)" in mcp_server.INSTRUCTIONS
    assert "Kfz-Zulassung, Finanzamt" not in mcp_server.INSTRUCTIONS
