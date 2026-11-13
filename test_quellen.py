"""Tests für mehrere Datenquellen und die Konfiguration in quellen/*.toml (Fixtures aus conftest.py)."""
from __future__ import annotations

import importlib
import json
import shutil
from pathlib import Path

import anyio
import pytest

import zustaendigkeit

ECHTES_GET = zustaendigkeit._get  # vor dem Monkeypatching der Fixtures festhalten
BEISPIEL = Path(__file__).with_name("quellen") / "bzb-eigen.toml.example"


# --------------------------------------------------------------------------- #
# Zwei Quellen gleichzeitig
# --------------------------------------------------------------------------- #
def test_typen_aus_zwei_quellen_in_einer_abfrage(zf_zwei_quellen):
    zf = zf_zwei_quellen
    erg = zf.finde_zustaendigkeit(lat=50.5, lon=8.5, typen=["arbeitsagentur", "bundespolizeiinspektion"])
    aa, bpol = erg["ergebnisse"]
    assert (aa["quelle"], bpol["quelle"]) == ("bzb_open", "eigen")
    assert aa["treffer"][0]["name"] == "AG West"
    assert [q["id"] for q in erg["quellen"]] == ["bzb_open", "eigen"]


def test_nur_genutzte_quellen_werden_genannt(zf_zwei_quellen):
    erg = zf_zwei_quellen.finde_zustaendigkeit(lat=50.5, lon=8.5, typen=["zoll_fks"])
    assert [q["quellenvermerk"] for q in erg["quellen"]] == ["BZB © BKG (Test)"]


def test_name_und_uebergeordnet_aus_konfigurierten_attributen(zf_zwei_quellen):
    # Ohne name_attribut würde die Heuristik "dir_lang" (Direktion) statt "ins_lang" wählen.
    t = zf_zwei_quellen.zustaendigkeit_an_punkt(50.5, 8.5, "bundespolizeiinspektion")[0]
    assert t["name"] == "Bundespolizeiinspektion Frankfurt"
    assert t["uebergeordnet"] == "Bundespolizeidirektion Koblenz"
    assert t["attribute"]["ins_kn"] == "BPOLI F"


def test_meterkoordinaten_ohne_crs_werden_umgerechnet(zf_zwei_quellen):
    gdf = zf_zwei_quellen.lade_flaechen_fuer("zoll_fks")
    minx, miny, maxx, maxy = gdf.total_bounds
    assert (round(minx, 3), round(maxy, 3)) == (8.0, 51.0)
    assert zf_zwei_quellen.zustaendigkeit_an_punkt(50.5, 8.5, "zoll_fks")[0]["name"] == "FKS Standort Frankfurt"


def test_exakter_layername_schlaegt_teilstring(zf_zwei_quellen):
    # "bpol_inspektionen" steckt auch in "bpol_inspektionen_250"
    assert zf_zwei_quellen.layer_fuer("bundespolizeiinspektion") == "bzb:bpol_inspektionen"


def test_mehrdeutige_suche_ist_fehler(zf_zwei_quellen, monkeypatch):
    zf = zf_zwei_quellen
    t = zf.BEHOERDENTYPEN["bundespolizeiinspektion"]
    monkeypatch.setitem(zf.BEHOERDENTYPEN, t.key, zf.Behoerdentyp(t.key, t.label, t.quelle, layer_suche="bpol_insp"))
    with pytest.raises(zf.LayerNichtGefunden, match="mehrdeutig"):
        zf.layer_fuer("bundespolizeiinspektion")


def test_wfs_version_bestimmt_parameter(zf_zwei_quellen, mock_wfs):
    zf = zf_zwei_quellen
    zf.lade_flaechen_fuer("arbeitsagentur")
    zf.lade_flaechen_fuer("zoll_fks")
    get = {a["url"]: a for a in mock_wfs.aufrufe if a["request"] == "GetFeature"}
    assert {"typeName", "maxFeatures"} <= set(get["https://sgx.geodatenzentrum.de/wfs_bzb_open"])
    assert {"typeNames", "count"} <= set(get["http://wfs.test/geoserver/bzb/ows"])
    assert get["http://wfs.test/geoserver/bzb/ows"]["version"] == "2.0.0"


def test_capabilities_und_dateicache_je_quelle(zf_zwei_quellen, mock_wfs):
    zf = zf_zwei_quellen
    zf.lade_flaechen_fuer("jobcenter")
    zf.lade_flaechen_fuer("zoll_fks")
    caps = {a["url"] for a in mock_wfs.aufrufe if a["request"] == "GetCapabilities"}
    assert len(caps) == 2
    assert (zf.CACHE_DIR / "eigen" / "bzb_zoll_fks.geojson").exists()
    assert (zf.CACHE_DIR / "bzb_open" / "bzb-open_ba_jobcenter.geojson").exists()
    assert zf.geladene_layer() == ["bzb_open:bzb-open:ba_jobcenter", "eigen:bzb:zoll_fks"]


def test_anliegen_und_typen_aus_allen_quellen(zf_zwei_quellen):
    zf = zf_zwei_quellen
    assert zf.ANLIEGEN["Anzeige am Bahnhof"] == "bundespolizeiinspektion"
    assert zf.ANLIEGEN["Berufsberatung"] == "arbeitsagentur"
    assert {"key": "zoll_fks", "label": "Zoll – Finanzkontrolle Schwarzarbeit", "quelle": "eigen"} in zf.typen()
    assert [q["id"] for q in zf.quellen()] == ["bzb_open", "eigen"]


# --------------------------------------------------------------------------- #
# Konfiguration
# --------------------------------------------------------------------------- #
def test_standardordner_laedt_keine_beispieldateien(zf):
    assert list(zf.QUELLEN) == ["bzb_open"]
    assert "staatsanwaltschaft" not in zf.BEHOERDENTYPEN


def test_beispielkonfiguration_bzb_eigen_ist_gueltig(zf, tmp_path):
    ziel = tmp_path / "bzb-eigen.toml"
    shutil.copy(BEISPIEL, ziel)
    quellen, typen = zf.lade_konfiguration([zf.QUELLEN_STANDARD, ziel])
    assert set(quellen) == {"bzb_open", "bzb_eigen"}
    assert {"staatsanwaltschaft", "thw_regionalstelle", "zoll_vollstreckung"} <= set(typen)
    assert all(t.name_attribut for t in typen.values() if t.quelle == "bzb_eigen")


def test_zf_quellen_umgebungsvariable(zf, eigen_toml, monkeypatch):
    monkeypatch.setenv("ZF_QUELLEN", f"{eigen_toml}, {zf.QUELLEN_STANDARD}")
    quellen, _ = zf.lade_konfiguration()
    assert list(quellen) == ["eigen", "bzb_open"]


@pytest.mark.parametrize("toml, meldung", [
    ('[quelle]\nid="x"\n', "fehlt|missing|behoerdentyp"),
    ('[quelle]\nid="x"\ntitel="t"\nherausgeber="h"\nwfs_url="ftp://x"\nquellenvermerk="v"\n'
     '[[behoerdentyp]]\nkey="a"\nlabel="A"\nlayer="l"\n', "http"),
    ('[quelle]\nid="x"\ntitel="t"\nherausgeber="h"\nwfs_url="http://x"\nquellenvermerk="v"\n'
     '[[behoerdentyp]]\nkey="a"\nlabel="A"\n', "layer"),
    ('[quelle]\nid="x"\ntitel="t"\nherausgeber="h"\nwfs_url="http://x"\nquellenvermerk="v"\n'
     '[[behoerdentyp]]\nkey="a"\nlabel="A"\nlayer="l"\nlayr_suche="tippfehler"\n', "unbekannte Felder"),
    ('[quelle]\nid="X-1"\ntitel="t"\nherausgeber="h"\nwfs_url="http://x"\nquellenvermerk="v"\n'
     '[[behoerdentyp]]\nkey="a"\nlabel="A"\nlayer="l"\n', "a-z"),
    ('[quelle]\nid="x"\ntitel="t"\nherausgeber="h"\nwfs_url="http://x"\nquellenvermerk="v"\n'
     '[[behoerdentyp]]\nkey="arbeitsagentur"\nlabel="A"\nlayer="l"\n', "gibt es schon"),
    ('[quelle]\nid="x"\ntitel="t"\nherausgeber="h"\nwfs_url="http://x"\nquellenvermerk="v"\n'
     '[[behoerdentyp]]\nkey="a"\nlabel="A"\nlayer="l"\nanliegen="kein Array"\n', "Liste"),
    ('[quelle]\nid="x"\ntitel="t"\nherausgeber="h"\nwfs_url="http://x"\nquellenvermerk="v"\n'
     '[[behoerdentyp]]\nkey=1\nlabel="A"\nlayer="l"\n', "Text"),
    ("kein toml [", "Invalid|Expected|line"),
])
def test_konfigurationsfehler(zf, tmp_path, toml, meldung):
    datei = tmp_path / "kaputt.toml"
    datei.write_text(toml, encoding="utf-8")
    with pytest.raises(zf.KonfigurationsFehler, match=meldung):
        zf.lade_konfiguration([zf.QUELLEN_STANDARD, datei])


def test_fehlender_pfad(zf, tmp_path):
    with pytest.raises(zf.KonfigurationsFehler, match="nicht gefunden"):
        zf.lade_konfiguration(tmp_path / "gibtsnicht.toml")


def test_fehlerhafte_konfiguration_laesst_alte_bestehen(zf, tmp_path):
    datei = tmp_path / "kaputt.toml"
    datei.write_text("kein toml [", encoding="utf-8")
    with pytest.raises(zf.KonfigurationsFehler):
        zf.konfigurieren(datei)
    assert "arbeitsagentur" in zf.BEHOERDENTYPEN


# --------------------------------------------------------------------------- #
# HTTP-Details
# --------------------------------------------------------------------------- #
class _R:
    def __init__(self, text="<x/>"):
        self.text, self.content = text, text.encode()

    def raise_for_status(self):
        pass

    def json(self):
        return json.loads(self.text)


def test_basic_auth_aus_umgebungsvariable(zf, monkeypatch):
    q = zf.Datenquelle("q", "T", "H", "https://wfs.test", "V", auth_env="ZF_TEST_AUTH")
    gesendet = {}

    def fake_get(url, **kw):
        gesendet.update(kw, url=url)
        return _R()

    monkeypatch.setattr(zf.requests, "get", fake_get)
    monkeypatch.setenv("ZF_TEST_AUTH", "leser:geh:eim")
    ECHTES_GET(q, {"request": "GetCapabilities"})
    assert gesendet["url"] == "https://wfs.test" and gesendet["auth"] == ("leser", "geh:eim")

    monkeypatch.delenv("ZF_TEST_AUTH")
    with pytest.raises(zf.DienstFehler, match="ZF_TEST_AUTH"):
        ECHTES_GET(q, {"request": "GetCapabilities"})


def test_antwort_ohne_geojson_ist_dienstfehler(zf, monkeypatch):
    q = zf.Datenquelle("q", "T", "H", "https://wfs.test", "V", output_format="falsch")
    monkeypatch.setattr(zf, "_get", lambda quelle, params: _R("<ows:ExceptionReport>unbekanntes Format"))
    with pytest.raises(zf.DienstFehler, match="output_format 'falsch'.*ExceptionReport"):
        zf._hole_geojson(q, "irgendwas")


# --------------------------------------------------------------------------- #
# MCP-Server mit zwei Quellen
# --------------------------------------------------------------------------- #
@pytest.fixture
def mcp_zwei_quellen(zf_zwei_quellen):
    import mcp_server
    try:
        yield importlib.reload(mcp_server)
    finally:
        zf_zwei_quellen.konfigurieren(zf_zwei_quellen.QUELLEN_STANDARD)
        importlib.reload(mcp_server)


def test_mcp_schema_anweisungen_und_quelle_aus_konfiguration(mcp_zwei_quellen):
    from mcp.client import Client
    srv = mcp_zwei_quellen

    async def go():
        async with Client(srv.server) as c:
            tools = await c.list_tools()
            r = await c.call_tool("zustaendigkeit_finden", {
                "lat": 50.5, "lon": 8.5, "behoerdentypen": ["arbeitsagentur", "bundespolizeiinspektion"]})
            return tools.tools[0], r

    tool, r = anyio.run(go)
    schema = json.dumps(tool.input_schema["properties"]["behoerdentypen"])
    assert "zoll_fks" in schema and "jobcenter" in schema
    assert "Bundespolizeiinspektion" in tool.description
    assert "Bundespolizeiinspektion" in srv.INSTRUCTIONS and "BZB (eigen)" in srv.INSTRUCTIONS
    daten = json.loads(r.content[0].text)
    assert daten["ergebnisse"][1]["zustaendig"] == ["Bundespolizeiinspektion Frankfurt"]
    assert daten["ergebnisse"][1]["uebergeordnet"] == ["Bundespolizeidirektion Koblenz"]
    assert "uebergeordnet" not in daten["ergebnisse"][0]
    assert daten["quelle"] == "BZB-Open © BKG (dl-de/by-2-0); BZB © BKG (Test)"
