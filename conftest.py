"""
Gemeinsame Test-Fixtures: Mock-WFS statt BKG-Dienst, kein Internet nötig.

Die Fixture `zf` liefert das Modul `zustaendigkeit` mit Mock-WFS, leerem Cache und gesperrtem Geocoder.
"""
from __future__ import annotations

import json

import pytest

import zustaendigkeit as _zf


def _rechteck(lon0, lat0, lon1, lat1, achsen_vertauscht=False):
    ring = [[lon0, lat0], [lon1, lat0], [lon1, lat1], [lon0, lat1], [lon0, lat0]]
    if achsen_vertauscht:
        ring = [[b, a] for a, b in ring]
    return {"type": "Polygon", "coordinates": [ring]}


def _feature(fid, name, geom, **attr):
    return {"type": "Feature", "id": fid, "geometry": geom, "properties": {"name": name, **attr}}


# Testgebiet in Hessen: AG West (lon 8–9) und AG Ost (lon 9–10) grenzen bei lon 9 aneinander.
LAYER_FEATURES = {
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

CAPABILITIES = (
    '<?xml version="1.0"?>'
    '<wfs:WFS_Capabilities xmlns:wfs="http://www.opengis.net/wfs">'
    "<FeatureTypeList>"
    + "".join(f"<FeatureType><Name>{n}</Name></FeatureType>" for n in LAYER_FEATURES)
    + "</FeatureTypeList></wfs:WFS_Capabilities>"
)


class _Antwort:
    def __init__(self, inhalt: bytes):
        self.content = inhalt

    def json(self):
        return json.loads(self.content)


class MockWFS:
    """Ersetzt zustaendigkeit._get und zählt die Aufrufe."""

    def __init__(self):
        self.aufrufe: list[dict] = []

    def __call__(self, params: dict) -> _Antwort:
        self.aufrufe.append(dict(params))
        if params["request"] == "GetCapabilities":
            return _Antwort(CAPABILITIES.encode())
        if params["request"] == "GetFeature":
            alle = LAYER_FEATURES[params["typeName"]]
            start, anzahl = int(params.get("startIndex", 0)), int(params["maxFeatures"])
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
    """Modul `zustaendigkeit` mit Mock-WFS, leerem Cache und gesperrtem Geocoder."""
    monkeypatch.setattr(_zf, "_get", mock_wfs)
    monkeypatch.setattr(_zf, "CACHE_DIR", tmp_path / "cache")
    monkeypatch.setattr(_zf, "_flaechen", {})
    monkeypatch.setitem(_zf.BEHOERDENTYPEN, "landgericht",
                        _zf.Behoerdentyp("landgericht", "Landgericht", "landgerichte"))

    def kein_netz(adresse):
        raise AssertionError("Geocoder in Tests nicht verfügbar – lat/lon verwenden oder geocode mocken.")

    monkeypatch.setattr(_zf, "geocode", kein_netz)
    _zf.verfuegbare_layer.cache_clear()
    yield _zf
    _zf.verfuegbare_layer.cache_clear()
