"""
zustaendigkeit.py – Zuständige Behörde zu einer Adresse finden.

Datenbasis: BZB-Open (BKG), WFS https://sgx.geodatenzentrum.de/wfs_bzb_open
Kernfunktion:  finde_zustaendigkeit("Straße 1, 12345 Ort", typen=["arbeitsagentur"])

Ablauf: Adresse -> Koordinate (Nominatim) -> Punkt-in-Polygon gegen die
Zuständigkeitsflächen (einmal per WFS geladen und lokal zwischengespeichert).
"""
from __future__ import annotations

import json
import logging
import math
import os
import re
import threading
import time
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from io import BytesIO
from pathlib import Path

import geopandas as gpd
import requests
from shapely.geometry import Point, mapping
import shapely

log = logging.getLogger("zustaendigkeit")

WFS_URL = "https://sgx.geodatenzentrum.de/wfs_bzb_open"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = os.environ.get(
    "ZF_USER_AGENT",
    "hack4GDI-DE-Zustaendigkeitsfinder/1.0 (kontakt: jupyter@hack4gdi.de)",
)
CACHE_DIR = Path(os.environ.get("ZF_CACHE_DIR", Path.home() / ".cache" / "zustaendigkeit"))
CACHE_MAX_AGE_TAGE = 30  # Zuständigkeitsflächen ändern sich selten
TIMEOUT = 60
SEITENGROESSE = 1000  # Features pro WFS-Request (Schutz vor Server-Limits)


# --------------------------------------------------------------------------- #
# Fehler
# --------------------------------------------------------------------------- #
class ZustaendigkeitError(Exception):
    """Basisklasse."""


class AdresseNichtGefunden(ZustaendigkeitError):
    pass


class LayerNichtGefunden(ZustaendigkeitError):
    pass


class DienstFehler(ZustaendigkeitError):
    """Geocoder oder WFS nicht erreichbar bzw. unbrauchbare Antwort."""


# --------------------------------------------------------------------------- #
# Behördentypen – nur, was BZB-Open tatsächlich enthält
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Behoerdentyp:
    key: str
    label: str
    layer_hinweis: str  # Teilstring zum Finden des Layers in GetCapabilities
    layer: str | None = None  # fester Name, wenn bekannt (überschreibt Suche)


BEHOERDENTYPEN: dict[str, Behoerdentyp] = {
    t.key: t
    for t in [
        Behoerdentyp("arbeitsagentur", "Agentur für Arbeit", "arbeitsagenturen",
                     layer="bzb-open:ba_arbeitsagenturen"),
        Behoerdentyp("geschaeftsstelle", "Geschäftsstelle der Agentur für Arbeit", "geschaeftsstellen"),
        Behoerdentyp("jobcenter", "Jobcenter", "jobcenter"),
        Behoerdentyp("regionaldirektion", "Regionaldirektion der Bundesagentur für Arbeit", "regionaldirektionen"),
        Behoerdentyp("amtsgericht", "Amtsgericht", "amtsgerichte"),
        Behoerdentyp("landgericht", "Landgericht", "landgerichte"),
        Behoerdentyp("oberlandesgericht", "Oberlandesgericht", "oberlandesgerichte"),
    ]
}

# Beispiele für die Auswahl statt Freitext. Vor Produktivbetrieb fachlich prüfen lassen.
ANLIEGEN: dict[str, str] = {
    "Arbeitslosengeld beantragen / arbeitsuchend melden": "arbeitsagentur",
    "Berufsberatung": "arbeitsagentur",
    "Grundsicherung für Arbeitsuchende beantragen": "jobcenter",
    "Betreuung, Nachlass, Familiensachen, Grundbuch": "amtsgericht",
    "Zivilklage mit hohem Streitwert": "landgericht",
    "Berufung gegen ein Urteil des Landgerichts": "oberlandesgericht",
}


def typen() -> list[dict]:
    return [{"key": t.key, "label": t.label} for t in BEHOERDENTYPEN.values()]


def anliegen() -> list[dict]:
    return [{"anliegen": a, "typ": k} for a, k in ANLIEGEN.items()]


# --------------------------------------------------------------------------- #
# Geocoding
# --------------------------------------------------------------------------- #
@dataclass
class Ort:
    lat: float
    lon: float
    anzeige: str
    hinweise: list[str] = field(default_factory=list)


_ORTSEBENE = {
    "city", "town", "village", "municipality", "county", "state", "suburb",
    "city_district", "neighbourhood", "quarter", "borough", "hamlet", "postcode",
}
_nominatim_lock = threading.Lock()
_letzter_aufruf = 0.0


@lru_cache(maxsize=1024)
def geocode(adresse: str) -> Ort:
    """Adresse -> Ort (Nominatim, Deutschland). Respektiert die 1-Request/s-Regel."""
    global _letzter_aufruf
    adresse = adresse.strip()
    if not adresse:
        raise ValueError("Leere Adresse.")
    with _nominatim_lock:
        warte = 1.1 - (time.monotonic() - _letzter_aufruf)
        if warte > 0:
            time.sleep(warte)
        try:
            r = requests.get(
                NOMINATIM_URL,
                params={"q": adresse, "format": "jsonv2", "limit": 1, "countrycodes": "de"},
                headers={"User-Agent": USER_AGENT},
                timeout=20,
            )
            r.raise_for_status()
            treffer = r.json()
        except (requests.RequestException, ValueError) as e:
            raise DienstFehler(f"Geocoding fehlgeschlagen: {e}") from e
        finally:
            _letzter_aufruf = time.monotonic()
    if not treffer:
        raise AdresseNichtGefunden(f"Keine Koordinate zu '{adresse}' gefunden.")
    t = treffer[0]
    hinweise = []
    if t.get("addresstype") in _ORTSEBENE:
        hinweise.append(
            "Die Adresse wurde nur auf Ortsebene gefunden. Innerhalb eines Ortes kann "
            "die Zuständigkeit wechseln – bitte eine vollständige Straßenadresse angeben."
        )
    return Ort(float(t["lat"]), float(t["lon"]), t.get("display_name", adresse), hinweise)


# --------------------------------------------------------------------------- #
# WFS: Layer finden und Flächen laden
# --------------------------------------------------------------------------- #
def _get(params: dict) -> requests.Response:
    try:
        r = requests.get(WFS_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        raise DienstFehler(f"WFS nicht erreichbar: {e}") from e


@lru_cache(maxsize=1)
def verfuegbare_layer() -> tuple[str, ...]:
    """Feature-Typ-Namen aus GetCapabilities (ohne OWSLib, damit leicht testbar)."""
    r = _get({"service": "WFS", "version": "1.1.0", "request": "GetCapabilities"})
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        raise DienstFehler(f"GetCapabilities nicht lesbar: {e}") from e
    namen = []
    for el in root.iter():
        if el.tag.split("}")[-1] == "FeatureType":
            for kind in el:
                if kind.tag.split("}")[-1] == "Name" and kind.text:
                    namen.append(kind.text.strip())
    if not namen:
        raise DienstFehler("GetCapabilities enthält keine Feature-Typen.")
    return tuple(namen)


def layer_fuer(typ: str) -> str:
    if typ not in BEHOERDENTYPEN:
        raise ValueError(f"Unbekannter Behördentyp '{typ}'. Erlaubt: {', '.join(BEHOERDENTYPEN)}")
    t = BEHOERDENTYPEN[typ]
    if t.layer:
        return t.layer
    kandidaten = [n for n in verfuegbare_layer() if t.layer_hinweis in n.lower()]
    if not kandidaten:
        raise LayerNichtGefunden(
            f"Kein Layer für '{typ}' (Suche nach '{t.layer_hinweis}'). "
            f"Verfügbar: {', '.join(verfuegbare_layer())}"
        )
    return kandidaten[0]


def _hole_geojson(layer: str) -> dict:
    """Alle Features eines Layers holen; bei Server-Limit seitenweise."""
    features, start, crs, gesehen = [], 0, None, set()
    for _ in range(200):
        data = _get({
            "service": "WFS", "version": "1.1.0", "request": "GetFeature",
            "typeName": layer, "outputFormat": "application/json",
            "srsName": "EPSG:4326", "maxFeatures": SEITENGROESSE, "startIndex": start,
        }).json()
        seite = data.get("features", [])
        crs = crs or data.get("crs")
        neu = [f for f in seite if f.get("id") is None or f["id"] not in gesehen]
        gesehen.update(f["id"] for f in neu if f.get("id") is not None)
        features += neu
        gesamt = data.get("totalFeatures", data.get("numberMatched"))
        fertig = len(seite) < SEITENGROESSE or not neu
        if isinstance(gesamt, int):
            fertig = fertig or len(features) >= gesamt
        if fertig:
            if isinstance(gesamt, int) and len(features) < gesamt:
                raise DienstFehler(f"{layer}: nur {len(features)} von {gesamt} Features erhalten.")
            break
        start += len(seite)
    if not features:
        raise DienstFehler(f"Layer {layer} lieferte keine Features.")
    out = {"type": "FeatureCollection", "features": features}
    if crs:
        out["crs"] = crs
    return out


def _achsen_korrigieren(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Sorgt für lon/lat in EPSG:4326. Erkennt vertauschte Achsen und fehlende CRS-Angaben."""
    minx, miny, maxx, maxy = gdf.total_bounds
    if not all(map(math.isfinite, (minx, miny, maxx, maxy))):
        raise DienstFehler("Ungültige Geometrien im Layer.")

    def lonlat(a, b, c, d):  # grob: Deutschland inkl. Ränder
        return 5 <= a and c <= 16 and 46.5 <= b and d <= 56

    if max(abs(minx), abs(maxx), abs(miny), abs(maxy)) > 1000:  # Meter statt Grad
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=25832)
        return gdf.to_crs(epsg=4326)
    if lonlat(minx, miny, maxx, maxy):
        return gdf.set_crs(epsg=4326) if gdf.crs is None else gdf.to_crs(epsg=4326)
    if lonlat(miny, minx, maxy, maxx):
        log.warning("Vertauschte Achsen (lat/lon) erkannt – korrigiere.")
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.map(lambda g: shapely.transform(g, lambda c: c[:, ::-1]))
        return gdf.set_crs(epsg=4326, allow_override=True)
    raise DienstFehler(f"Bounds {gdf.total_bounds} liegen nicht in Deutschland – CRS prüfen.")


_flaechen: dict[str, gpd.GeoDataFrame] = {}
_flaechen_lock = threading.Lock()


def _cache_pfad(layer: str) -> Path:
    return CACHE_DIR / (re.sub(r"[^A-Za-z0-9_.-]", "_", layer) + ".geojson")


def lade_flaechen(layer: str, neu_laden: bool = False) -> gpd.GeoDataFrame:
    """Zuständigkeitsflächen eines Layers (EPSG:4326, lon/lat). Speicher- und Dateicache."""
    with _flaechen_lock:
        if not neu_laden and layer in _flaechen:
            return _flaechen[layer]
        pfad = _cache_pfad(layer)
        frisch = (
            pfad.exists() and not neu_laden
            and time.time() - pfad.stat().st_mtime < CACHE_MAX_AGE_TAGE * 86400
        )
        if frisch:
            roh = pfad.read_bytes()
        else:
            roh = json.dumps(_hole_geojson(layer)).encode("utf-8")
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            pfad.write_bytes(roh)
        gdf = _achsen_korrigieren(gpd.read_file(BytesIO(roh)))
        gdf.sindex  # Spatial Index vorab aufbauen
        _flaechen[layer] = gdf
        return gdf


# --------------------------------------------------------------------------- #
# Abfrage
# --------------------------------------------------------------------------- #
def _json_sicher(v):
    if v is None:
        return None
    if hasattr(v, "item"):  # numpy-Skalar
        v = v.item()
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()
    return v if isinstance(v, (str, int, float, bool)) else str(v)


def _anzeigename(attr: dict) -> str | None:
    """Heuristik: das Attribut mit dem Behördennamen. Die Rohattribute bleiben immer erhalten."""
    for hint in ("name", "bezeichnung", "bez", "lang"):
        for k, v in attr.items():
            if hint in k.lower() and isinstance(v, str) and v.strip():
                return v.strip()
    return next((v for v in attr.values() if isinstance(v, str) and v.strip()), None)


def zustaendigkeit_an_punkt(lat: float, lon: float, typ: str, mit_geometrie: bool = False) -> list[dict]:
    flaechen = lade_flaechen(layer_fuer(typ))
    punkt = Point(lon, lat)
    idx = flaechen.sindex.query(punkt, predicate="intersects")
    treffer = []
    for pos in idx:
        zeile = flaechen.iloc[int(pos)]
        attr = {k: _json_sicher(v) for k, v in zeile.drop(labels="geometry").items()}
        eintrag = {"name": _anzeigename(attr), "attribute": attr}
        if mit_geometrie:
            eintrag["geometrie"] = mapping(zeile.geometry.simplify(0.0005))
        treffer.append(eintrag)
    return treffer


def finde_zustaendigkeit(
    adresse: str | None = None,
    *,
    lat: float | None = None,
    lon: float | None = None,
    typen: list[str] | None = None,
    mit_geometrie: bool = False,
) -> dict:
    """
    Adresse (oder lat/lon) + Behördentypen -> zuständige Stellen.
    Ein Fehler bei einem Typ bricht die anderen nicht ab (steht dann in "fehler").
    """
    typen = typen or list(BEHOERDENTYPEN)
    unbekannt = [t for t in typen if t not in BEHOERDENTYPEN]
    if unbekannt:
        raise ValueError(f"Unbekannte Behördentypen: {', '.join(unbekannt)}")

    if lat is not None and lon is not None:
        if not (46.5 <= lat <= 56 and 5 <= lon <= 16):
            raise ValueError("Koordinate liegt außerhalb Deutschlands (lat/lon vertauscht?).")
        ort = Ort(lat, lon, adresse or f"{lat:.5f}, {lon:.5f}")
    elif adresse:
        ort = geocode(adresse)
    else:
        raise ValueError("Adresse oder lat und lon angeben.")

    ergebnisse = []
    for typ in typen:
        e = {"typ": typ, "label": BEHOERDENTYPEN[typ].label}
        try:
            e["layer"] = layer_fuer(typ)
            e["treffer"] = zustaendigkeit_an_punkt(ort.lat, ort.lon, typ, mit_geometrie)
            if not e["treffer"]:
                e["hinweis"] = "Keine Fläche an diesem Punkt (z. B. außerhalb des Datenbestands)."
            elif len(e["treffer"]) > 1:
                e["hinweis"] = "Mehrere Flächen treffen zu (Grenzlage oder Überlappung) – bitte prüfen."
        except ZustaendigkeitError as err:
            e["fehler"] = str(err)
        ergebnisse.append(e)

    return {
        "ort": asdict(ort),
        "ergebnisse": ergebnisse,
        "quelle": {
            "daten": "Behördenzuständigkeitsbereiche Open (BZB-Open)",
            "herausgeber": "Bundesamt für Kartographie und Geodäsie (BKG)",
            "dienst": WFS_URL,
            "geocoding": "© OpenStreetMap-Mitwirkende (Nominatim)" if adresse and lat is None else None,
        },
    }
