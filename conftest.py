"""
Gemeinsame Test-Fixtures: Mock-WFS statt echter Dienste, kein Internet nötig.

- `zf`: Modul `zustaendigkeit` mit Standardkonfiguration (quellen/bzb-open.toml), Mock-WFS,
  leerem Cache und gesperrtem Geocoder.
- `zf_zwei_quellen`: wie `zf`, zusätzlich ein eigener WFS (Quelle "eigen", Mock unter EIGEN_URL).
- `pvog_mock`: ersetzt die PVOG-Suchdienst-API durch feste Antworten (PVOG_* unten) und zählt die Aufrufe.
"""
from __future__ import annotations

import json
import textwrap

import pytest
from pyproj import Transformer
from shapely.geometry import box, shape

import zustaendigkeit as _zf

BZB_OPEN_URL = "https://sgx.geodatenzentrum.de/wfs_bzb_open"
EIGEN_URL = "http://wfs.test/geoserver/bzb/ows"
VG250_URL = "https://sgx.geodatenzentrum.de/wfs_vg250"


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
    # Bundespolizei See: Fläche in der AWZ der Nordsee (bis ca. 3,1° O) – muss als Deutschland gelten.
    # In Grad, wie GeoServer sie nach Umprojektion auf das angeforderte EPSG:4326 liefert.
    "bzb:bpol_direktionen": [
        _feature("BPOLD BBS See", None, _rechteck(3.1, 53.5, 8.0, 55.9), dir_lang="Bundespolizeidirektion Bad Bramstedt (See)"),
        _feature("BPOLD KO", None, _rechteck(8, 50, 9, 51), dir_lang="Bundespolizeidirektion Koblenz"),
    ],
    "bzb:zoll_fks": [
        _feature("fks.1", None, _rechteck_utm(8, 50, 9, 51), hza_lang="Hauptzollamt Gießen",
                 zst_lang="FKS Standort Frankfurt"),
    ],
}

# VG250 (Abfrage per BBOX am Punkt): Teststadt (lon 8–9) und Testdorf (lon 9–10)
VG250_FEATURES = {
    "vg250:vg250_gem": [
        _feature("gem.1", None, _rechteck(8, 50, 9, 51), gen="Teststadt", bez="Stadt", ars="064120000000", sn_l="06"),
        _feature("gem.2", None, _rechteck(9, 50, 10, 51), gen="Testdorf", bez="Gemeinde", ars="064350001001", sn_l="06"),
    ],
    "vg250:vg250_krs": [
        _feature("krs.1", None, _rechteck(8, 50, 9, 51), gen="Teststadt", bez="Kreisfreie Stadt", ars="06412", sn_l="06"),
        _feature("krs.2", None, _rechteck(9, 50, 10, 51), gen="Testkreis", bez="Landkreis", ars="06435", sn_l="06"),
    ],
    "vg250:vg250_rbz": [
        _feature("rbz.1", None, _rechteck(8, 50, 10, 51), gen="Darmstadt", bez="Regierungsbezirk", ars="064", sn_l="06"),
    ],
}

DIENSTE = {BZB_OPEN_URL: BZB_OPEN_FEATURES, EIGEN_URL: EIGEN_FEATURES, VG250_URL: VG250_FEATURES}


def _bbox_filter(features: list[dict], bbox: str) -> list[dict]:
    """BBOX 'lat0,lon0,lat1,lon1,urn:ogc:def:crs:EPSG::4326' (Achsenfolge lat/lon)."""
    lat0, lon0, lat1, lon1 = map(float, bbox.split(",")[:4])
    fenster = box(lon0, lat0, lon1, lat1)
    return [f for f in features if shape(f["geometry"]).intersects(fenster)]

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
    key = "bundespolizeidirektion"
    label = "Bundespolizeidirektion"
    layer_suche = "bpol_direktionen"
    name_attribut = "dir_lang"

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
            if "bbox" in params:
                alle = _bbox_filter(alle, params["bbox"])
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


# --------------------------------------------------------------------------- #
# PVOG-Suchdienst (Mock)
# --------------------------------------------------------------------------- #
def _oe(oe_id, titel, strasse=None, ort="64283 Teststadt", telefon=None, email=None, traeger=None,
        art="Hausanschrift", zeiten=None):
    adresse = {"type": art, "street": strasse or "keine Straße", "houseNumber": "1" if strasse else "",
               "zip": ort.split()[0], "city": ort.split(maxsplit=1)[1]}
    komm = ([{"code": "02", "name": "Telefon Festnetz", "value": telefon}] if telefon else []) + \
           ([{"code": "01", "name": "E-Mail", "value": email}] if email else [])
    return {"id": oe_id, "title": titel, "location": {"addresses": [adresse], "communications": komm},
            "internetAddresses": [{"uri": "https://www.teststadt.de", "title": traeger}] if traeger else [],
            "additionalInformation": [{"type": "INFO_TIMES", "title": "Öffnungszeiten", "text": zeiten}] if zeiten else []}


def _rolle(code):
    return {"code": code, "name": {"02": "Zuständige Stelle", "01": "Ansprechpunkt"}[code]}


# (LeiKa, ARS) -> Leistungen; Leistung -> Detail mit Organisationseinheiten; OE-ID -> OE-Detail
PVOG_LEISTUNGEN = {
    ("99008001012000", "064120000000"): [{"id": "LB.perso.ts", "name": "Personalausweis beantragen",
                                          "sourcePortals": [{"uri": "https://portal.test/perso"}]}],
    ("99046010001000", "064120000000"): [{"id": "LB.erbschein.ts", "name": "Erbschein beantragen"}],
    ("99107108017000", "064120000000"): [{"id": "LB.buergergeld.ts", "name": "Bürgergeld beantragen"}],
    # Testdorf: viele Ansprechpunkte, eine virtuelle "Allzuständigkeit", eine doppelte Stelle
    ("99008001012000", "064350001001"): [{"id": "LB.perso.td", "name": "Personalausweis beantragen"}],
}
PVOG_DETAILS = {
    "LB.perso.ts": {"organisations": [{"id": "OE.buergerbuero", "role": _rolle("02")}],
                    "onlineServiceLinks": [{"title": "Termin buchen", "uri": "https://termine.test/ts"}]},
    "LB.erbschein.ts": {"organisations": [{"id": "OE.ag", "role": _rolle("02")}]},
    "LB.buergergeld.ts": {"organisations": [{"id": "OE.ba", "role": _rolle("01")}]},
    "LB.perso.td": {"organisations": [
        {"id": "OE.alle", "title": "Allzuständigkeit - Einwohner", "role": _rolle("01")},
        {"id": "OE.td1", "role": _rolle("01")}, {"id": "OE.td1b", "role": _rolle("01")},
        {"id": "OE.td2", "role": _rolle("01")}]},
}
PVOG_OES = {
    "OE.buergerbuero": _oe("OE.buergerbuero", "32/2 Bürgerbüro", "Rathausplatz", telefon="06151 1150",
                           email="buergerbuero@teststadt.de", traeger="Stadt Teststadt", zeiten="<p>Mo&nbsp;8–12 Uhr</p>"),
    "OE.ag": _oe("OE.ag", "Amtsgericht Mitte, Nachlassgericht", "Gerichtsstraße", telefon="06151 1200"),
    "OE.ba": _oe("OE.ba", "Bundesagentur für Arbeit (BA), Servicecenter", telefon="0800 4555500"),
    "OE.alle": _oe("OE.alle", "Allzuständigkeit - Einwohner"),
    "OE.td1": _oe("OE.td1", "Bürgerbüro Nord", "Nordweg", ort="64300 Testdorf"),
    "OE.td1b": _oe("OE.td1b", "Bürgerbüro Nord", "Nordweg", ort="64300 Testdorf"),
    "OE.td2": _oe("OE.td2", "Bürgerbüro Süd", "Südweg", ort="64300 Testdorf"),
}


class MockPVOG:
    def __init__(self):
        self.aufrufe: list[tuple[str, dict]] = []
        self.kaputt = False

    def __call__(self, pfad: str, params: tuple):
        p = dict(params)
        self.aufrufe.append((pfad, p))
        if self.kaputt:
            import pvog
            raise pvog.PvogFehler("PVOG nicht erreichbar (Test)")
        if pfad == "/v3/servicedescriptions/leikaid":
            return {"content": PVOG_LEISTUNGEN.get((p["leikaIds"], p["ars"]), [])}
        if pfad.startswith("/v6/servicedescriptions/"):
            return PVOG_DETAILS.get(pfad.split("/")[3], {})
        if pfad == "/v5/organisationunits/detail":
            oe = PVOG_OES.get(p["q"], {})
            return {**oe, "role": None} if oe else {}
        raise AssertionError(f"Unerwartete PVOG-Anfrage: {pfad} {p}")

    def leika_abfragen(self) -> list[str]:
        return [p["leikaIds"] for pfad, p in self.aufrufe if pfad == "/v3/servicedescriptions/leikaid"]


@pytest.fixture
def pvog_mock(monkeypatch, zf):
    import pvog
    mock = MockPVOG()
    monkeypatch.setattr(pvog, "_get_roh", mock)
    pvog._get_cache.cache_clear()
    yield mock
    pvog._get_cache.cache_clear()
