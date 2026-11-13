"""
Gemeinsame Test-Fixtures: Mock-WFS statt echter Dienste, kein Internet nötig.

- `zf`: Modul `zustaendigkeit` mit Standardkonfiguration (quellen/bzb-open.toml), Mock-WFS,
  leerem Cache und gesperrtem Geocoder.
- `zf_zwei_quellen`: wie `zf`, zusätzlich ein eigener WFS (Quelle "eigen", Mock unter EIGEN_URL).
"""
from __future__ import annotations

import json
import textwrap

import pytest
from pyproj import Transformer

import zustaendigkeit as _zf

BZB_OPEN_URL = "https://sgx.geodatenzentrum.de/wfs_bzb_open"
EIGEN_URL = "http://wfs.test/geoserver/bzb/ows"


def _rechteck(lon0, lat0, lon1, lat1, achsen_vertauscht=False):
    ring = [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]
    if achsen_vertauscht:
        ring = [[b, a] for a, b in ring]
    return {"type": "Polygon", "coordinates": [ring]}


_nach_utm = Transformer.from_crs(4326, 25832, always_xy=True)


def _rechteck_utm(lon0, lat0, lon1, lat1):
    """Rechteck in EPSG:25832 (Meter), wie es ein eigener Dienst ohne Umprojektion liefern würde."""
    ring = _rechteck(lon0, lat0, lon1, lat1)["coordinates"][0]
    return {"type": "Polygon", "coordinates": [[list(_nach_utm.transform(x, y)) for x, y in ring]]}


def _feature(fid, name, geom, **attr):
    props = {"name": name, **attr} if name is not None else attr
    return {"type": "Feature", "id": fid, "geometry": geom, "properties": props}


# Testgebiet in Hessen: AG West (lon 8–9) und AG Ost (lon 9–10) grenzen bei lon 9 aneinander.
BZB_OPEN_FEATURES = {
    "bzb-open:ba_arbeitsagenturen": [
        _feature("aa.1", "AG West", _rechteck(8, 50, 9, 51), dst_nr="111"),
        _feature("aa.2", "AG Ost", _rechteck(9, 50, 10, 51), dst_nr="222"),
    ],
    "bzb-open:ba_jobcenter": [
        _feature("jc.1", "Jobcenter Fern", _rechteck(11, 52, 12, 53)),
    ],
    # Liefert lat/lon statt lon/lat – muss automatisch korrigiert werden.
    "bzb-open:justiz_amtsgerichte": [
        _feature("ag.1", "Amtsgericht Mitte", _rechteck(8, 50, 10, 51, achsen_vertauscht=True)),
    ],
    # Mehr Features als eine Seite – prüft das Paging.
    "bzb-open:justiz_landgerichte": [
        _feature(f"lg.{i}", f"Landgericht {i}", _rechteck(8 + i * 0.1, 50, 8.1 + i * 0.1, 51))
        for i in range(5)
    ],
}

# Eigener Dienst im Stil von bzb-db/GeoServer: Namensraum "bzb:", Meterkoordinaten ohne CRS-Angabe,
# Namen in *_lang-Attributen, Layer mit gemeinsamem Präfix (exakte Suche nötig).
EIGEN_FEATURES = {
    "bzb:bpol_inspektionen": [
        _feature("BPOLI F", None, _rechteck_utm(8, 50, 9, 51), ins_kn="BPOLI F",
                 dir_lang="Bundespolizeidirektion Koblenz", ins_lang="Bundespolizeiinspektion Frankfurt"),
    ],
    "bzb:bpol_inspektionen_250": [
        _feature("BPOLI F", None, _rechteck_utm(8, 50, 9, 51), ins_lang="NICHT VERWENDEN (Übersicht)"),
    ],
    "bzb:zoll_fks": [
        _feature("fks.1", None, _rechteck_utm(8, 50, 9, 51), hza_lang="Hauptzollamt Gießen",
                 zst_lang="FKS Standort Frankfurt"),
    ],
}

DIENSTE = {BZB_OPEN_URL: BZB_OPEN_FEATURES, EIGEN_URL: EIGEN_FEATURES}

EIGEN_TOML = textwrap.dedent(f"""\
    [quelle]
    id = "eigen"
    kurzname = "BZB (eigen)"
    titel = "Behördenzuständigkeitsbereiche (eigener Dienst)"
    herausgeber = "Testbehörde"
    wfs_url = "{EIGEN_URL}"
    quellenvermerk = "BZB © BKG (Test)"
    wfs_version = "2.0.0"
    crs_fallback = "EPSG:25832"

    [[behoerdentyp]]
    key = "bundespolizeiinspektion"
    label = "Bundespolizeiinspektion"
    layer_suche = "bpol_inspektionen"
    name_attribut = "ins_lang"
    uebergeordnet_attribut = "dir_lang"
    anliegen = ["Anzeige am Bahnhof"]

    [[behoerdentyp]]
    key = "zoll_fks"
    label = "Zoll – Finanzkontrolle Schwarzarbeit"
    layer_suche = "zoll_fks"
    name_attribut = "zst_lang"
    uebergeordnet_attribut = "hza_lang"
""")


def _capabilities(namen) -> bytes:
    return (
        '<?xml version="1.0"?>'
        '<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs">'
        "<FeatureTypeList>"
        + "".join(f"<FeatureType><Name>{n}</Name></FeatureType>" for n in namen)
        + "</FeatureTypeList></wfs:WFS_Capabilities>"
    ).encode()


class _Antwort:
    def __init__(self, inhalt: bytes):
        self.content = inhalt
        self.text = inhalt.decode()

    def json(self):
        return json.loads(self.content)


class MockWFS:
    """Ersetzt zustaendigkeit._get, bedient mehrere Dienste nach URL und zählt die Aufrufe."""

    def __init__(self):
        self.aufrufe: list[dict] = []

    def __call__(self, quelle, params: dict) -> _Antwort:
        self.aufrufe.append({"url": quelle.wfs_url, **params})
        layer_features = DIENSTE[quelle.wfs_url]
        if params["request"] == "GetCapabilities":
            return _Antwort(_capabilities(layer_features))
        if params["request"] == "GetFeature":
            alle = layer_features[params.get("typeName") or params["typeNames"]]
            start = int(params.get("startIndex", 0))
            anzahl = int(params.get("maxFeatures") or params["count"])
            seite = alle[start:start + anzahl]
            return _Antwort(json.dumps(
                {"type": "FeatureCollection", "features": seite, "totalFeatures": len(alle)}
            ).encode())
        raise AssertionError(f"Unerwartete Anfrage: {params}")


@pytest.fixture
def mock_wfs():
    return MockWFS()


@pytest.fixture
def zf(monkeypatch, tmp_path, mock_wfs):
    """Modul `zustaendigkeit` mit Standardkonfiguration, Mock-WFS, leerem Cache und gesperrtem Geocoder."""
    monkeypatch.setattr(_zf, "_get", mock_wfs)
    monkeypatch.setattr(_zf, "CACHE_DIR", tmp_path / "cache")
    _zf.konfigurieren(_zf.QUELLEN_STANDARD)

    def kein_netz(adresse):
        raise AssertionError("Geocoder in Tests nicht verfügbar – lat/lon verwenden oder geocode mocken.")

    monkeypatch.setattr(_zf, "geocode", kein_netz)
    yield _zf
    _zf.konfigurieren(_zf.QUELLEN_STANDARD)


@pytest.fixture
def eigen_toml(tmp_path):
    pfad = tmp_path / "eigen.toml"
    pfad.write_text(EIGEN_TOML, encoding="utf-8")
    return pfad


@pytest.fixture
def zf_zwei_quellen(zf, eigen_toml):
    """BZB-Open und ein eigener WFS gleichzeitig."""
    zf.konfigurieren([zf.QUELLEN_STANDARD, eigen_toml])
    return zf
