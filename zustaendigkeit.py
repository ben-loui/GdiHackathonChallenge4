"""
zustaendigkeit.py – Zuständige Behörde zu einer Adresse finden.

Datenbasis: beliebige WFS mit Zuständigkeitsflächen, konfiguriert in quellen/*.toml
(Standard: BZB-Open des BKG, https://sgx.geodatenzentrum.de/wfs_bzb_open).
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
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field, fields
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from typing import Iterable

import geopandas as gpd
import requests
from shapely.geometry import Point, mapping
import shapely

log = logging.getLogger("zustaendigkeit")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = os.environ.get(
    "ZF_USER_AGENT",
    "hack4GDI-DE-Zustaendigkeitsfinder/1.0 (kontakt: jupyter@hack4gdi.de)",
)
CACHE_DIR = Path(os.environ.get("ZF_CACHE_DIR", Path.home() / ".cache" / "zustaendigkeit"))
CACHE_MAX_AGE_TAGE = 30  # Zuständigkeitsflächen ändern sich selten
TIMEOUT = 60
SEITENGROESSE = 1000  # Features pro WFS-Request, wenn die Quelle nichts anderes festlegt
QUELLEN_STANDARD = Path(__file__).with_name("quellen")
# Grobe Plausibilitätsgrenze (lon/lat) für Deutschland einschließlich der AWZ in Nord- und Ostsee
# (Bundespolizei See reicht bis etwa 3,1° O).
DEUTSCHLAND_BBOX = (2.5, 46.5, 16.0, 56.0)


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


class KonfigurationsFehler(ZustaendigkeitError):
    """Fehlerhafte oder fehlende Quellen-Konfiguration (quellen/*.toml)."""


# --------------------------------------------------------------------------- #
# Datenquellen und Behördentypen (aus quellen/*.toml)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Datenquelle:
    """Ein WFS mit Zuständigkeitsflächen."""
    id: str
    titel: str
    herausgeber: str
    wfs_url: str
    quellenvermerk: str
    kurzname: str = ""
    lizenz: str = ""
    info_url: str = ""
    wfs_version: str = "1.1.0"
    output_format: str = "application/json"
    srs: str = "EPSG:4326"  # angefordertes CRS; der Dienst rechnet um
    crs_fallback: str = "EPSG:25832"  # gilt für Meterkoordinaten ohne CRS-Angabe in der Antwort
    seitengroesse: int | None = None
    auth_env: str | None = None  # Umgebungsvariable mit "benutzer:passwort" für HTTP-Basic-Auth

    @property
    def name(self) -> str:
        return self.kurzname or self.id

    def info(self) -> dict:
        return {
            "id": self.id, "titel": self.titel, "herausgeber": self.herausgeber,
            "dienst": self.wfs_url, "lizenz": self.lizenz or None,
            "quellenvermerk": self.quellenvermerk, "info_url": self.info_url or None,
        }


@dataclass(frozen=True)
class Behoerdentyp:
    key: str
    label: str
    quelle: str  # id der Datenquelle
    layer: str | None = None  # fester Feature-Type-Name
    layer_suche: str | None = None  # sonst: Suche in GetCapabilities
    name_attribut: str | None = None  # Attribut mit dem Namen der Stelle (sonst Heuristik)
    uebergeordnet_attribut: str | None = None
    anliegen: tuple[str, ...] = ()


QUELLEN: dict[str, Datenquelle] = {}
BEHOERDENTYPEN: dict[str, Behoerdentyp] = {}
ANLIEGEN: dict[str, str] = {}  # Beispiel-Anliegen -> Behördentyp

_SCHLUESSEL = re.compile(r"^[a-z0-9_]+$")


def _felder(cls, daten: dict, wo: str) -> dict:
    erlaubt = {f.name for f in fields(cls)}
    unbekannt = set(daten) - erlaubt
    if unbekannt:
        raise KonfigurationsFehler(f"{wo}: unbekannte Felder {sorted(unbekannt)}. Erlaubt: {sorted(erlaubt)}")
    for k, v in daten.items():
        if k == "seitengroesse":
            continue
        if k == "anliegen":
            if not (isinstance(v, list) and all(isinstance(x, str) for x in v)):
                raise KonfigurationsFehler(f"{wo}: anliegen muss eine Liste von Texten sein.")
        elif not isinstance(v, str):
            raise KonfigurationsFehler(f"{wo}: {k} muss ein Text sein, nicht {type(v).__name__}.")
    return daten


def _quelle_aus(daten: dict, wo: str) -> Datenquelle:
    try:
        q = Datenquelle(**_felder(Datenquelle, daten, wo))
    except TypeError as e:
        raise KonfigurationsFehler(f"{wo}: {e}") from e
    if not _SCHLUESSEL.match(q.id):
        raise KonfigurationsFehler(f"{wo}: id '{q.id}' nur aus a-z, 0-9 und _ bilden.")
    if not q.wfs_url.startswith(("http://", "https://")):
        raise KonfigurationsFehler(f"{wo}: wfs_url muss mit http:// oder https:// beginnen.")
    if q.seitengroesse is not None and (not isinstance(q.seitengroesse, int) or q.seitengroesse < 1):
        raise KonfigurationsFehler(f"{wo}: seitengroesse muss eine positive Ganzzahl sein.")
    return q


def _typ_aus(daten: dict, quelle: str, wo: str) -> Behoerdentyp:
    daten = dict(_felder(Behoerdentyp, {**daten, "quelle": quelle}, wo))
    daten["anliegen"] = tuple(daten.get("anliegen", ()))
    try:
        t = Behoerdentyp(**daten)
    except TypeError as e:
        raise KonfigurationsFehler(f"{wo}: {e}") from e
    if not _SCHLUESSEL.match(t.key):
        raise KonfigurationsFehler(f"{wo}: key '{t.key}' nur aus a-z, 0-9 und _ bilden.")
    if not (t.layer or t.layer_suche):
        raise KonfigurationsFehler(f"{wo}: 'layer' oder 'layer_suche' angeben.")
    return t


def _toml_dateien(pfade: Iterable[str | Path]) -> list[Path]:
    dateien = []
    for p in map(Path, pfade):
        if p.is_dir():
            dateien += sorted(p.glob("*.toml"))
        elif p.is_file():
            dateien.append(p)
        else:
            raise KonfigurationsFehler(f"Quellen-Konfiguration '{p}' nicht gefunden.")
    return dateien


def lade_konfiguration(
    pfade: str | Path | Iterable[str | Path] | None = None,
) -> tuple[dict[str, Datenquelle], dict[str, Behoerdentyp]]:
    """
    Liest Datenquellen und Behördentypen aus TOML-Dateien oder Ordnern (dort alle *.toml).
    Ohne Angabe: Umgebungsvariable ZF_QUELLEN (kommagetrennt), sonst der Ordner quellen/.
    """
    if pfade is None:
        env = os.environ.get("ZF_QUELLEN", "").strip()
        pfade = [s.strip() for s in env.split(",") if s.strip()] if env else [QUELLEN_STANDARD]
    elif isinstance(pfade, (str, Path)):
        pfade = [pfade]

    quellen: dict[str, Datenquelle] = {}
    typen: dict[str, Behoerdentyp] = {}
    for datei in _toml_dateien(pfade):
        try:
            inhalt = tomllib.loads(datei.read_text(encoding="utf-8"))
        except (tomllib.TOMLDecodeError, OSError) as e:
            raise KonfigurationsFehler(f"{datei}: {e}") from e
        if set(inhalt) - {"quelle", "behoerdentyp"}:
            raise KonfigurationsFehler(f"{datei}: nur [quelle] und [[behoerdentyp]] erlaubt.")
        if "quelle" not in inhalt:
            raise KonfigurationsFehler(f"{datei}: Abschnitt [quelle] fehlt.")
        q = _quelle_aus(inhalt["quelle"], f"{datei} [quelle]")
        if q.id in quellen:
            raise KonfigurationsFehler(f"{datei}: Quelle '{q.id}' ist doppelt definiert.")
        quellen[q.id] = q
        eintraege = inhalt.get("behoerdentyp", [])
        if not eintraege:
            raise KonfigurationsFehler(f"{datei}: keine [[behoerdentyp]]-Einträge.")
        for i, roh in enumerate(eintraege, 1):
            t = _typ_aus(roh, q.id, f"{datei} Behördentyp {i}")
            if t.key in typen:
                raise KonfigurationsFehler(
                    f"{datei}: Behördentyp '{t.key}' gibt es schon in Quelle '{typen[t.key].quelle}'.")
            typen[t.key] = t
    if not typen:
        raise KonfigurationsFehler(f"Keine Behördentypen konfiguriert (gelesen: {', '.join(map(str, pfade))}).")
    return quellen, typen


def konfigurieren(pfade: str | Path | Iterable[str | Path] | None = None) -> None:
    """Lädt die Konfiguration und ersetzt QUELLEN, BEHOERDENTYPEN und ANLIEGEN (an Ort und Stelle)."""
    quellen, typen = lade_konfiguration(pfade)
    QUELLEN.clear()
    QUELLEN.update(quellen)
    BEHOERDENTYPEN.clear()
    BEHOERDENTYPEN.update(typen)
    ANLIEGEN.clear()
    ANLIEGEN.update({a: t.key for t in typen.values() for a in t.anliegen})
    verfuegbare_layer.cache_clear()
    with _flaechen_lock:
        _flaechen.clear()


def typen() -> list[dict]:
    return [{"key": t.key, "label": t.label, "quelle": t.quelle} for t in BEHOERDENTYPEN.values()]


def anliegen() -> list[dict]:
    return [{"anliegen": a, "typ": k} for a, k in ANLIEGEN.items()]


def quellen() -> list[dict]:
    return [q.info() for q in QUELLEN.values()]


def _typ(typ: str) -> Behoerdentyp:
    if typ not in BEHOERDENTYPEN:
        raise ValueError(f"Unbekannter Behördentyp '{typ}'. Erlaubt: {', '.join(BEHOERDENTYPEN)}")
    return BEHOERDENTYPEN[typ]


def _quelle(quelle_id: str) -> Datenquelle:
    if quelle_id not in QUELLEN:
        raise KonfigurationsFehler(f"Unbekannte Datenquelle '{quelle_id}'.")
    return QUELLEN[quelle_id]


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
def _get(quelle: Datenquelle, params: dict) -> requests.Response:
    auth = None
    if quelle.auth_env:
        wert = os.environ.get(quelle.auth_env, "")
        if ":" not in wert:
            raise DienstFehler(
                f"{quelle.name}: Umgebungsvariable {quelle.auth_env} fehlt oder hat nicht das Format benutzer:passwort.")
        auth = tuple(wert.split(":", 1))
    try:
        r = requests.get(quelle.wfs_url, params=params, headers={"User-Agent": USER_AGENT},
                         auth=auth, timeout=TIMEOUT)
        r.raise_for_status()
        return r
    except requests.RequestException as e:
        raise DienstFehler(f"WFS {quelle.name} nicht erreichbar: {e}") from e


@lru_cache(maxsize=None)
def verfuegbare_layer(quelle_id: str) -> tuple[str, ...]:
    """Feature-Typ-Namen aus GetCapabilities (ohne OWSLib, damit leicht testbar)."""
    q = _quelle(quelle_id)
    r = _get(q, {"service": "WFS", "version": q.wfs_version, "request": "GetCapabilities"})
    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        raise DienstFehler(f"GetCapabilities von {q.name} nicht lesbar: {e}") from e
    namen = []
    for el in root.iter():
        if el.tag.split("}")[-1] == "FeatureType":
            for kind in el:
                if kind.tag.split("}")[-1] == "Name" and kind.text:
                    namen.append(kind.text.strip())
    if not namen:
        raise DienstFehler(f"GetCapabilities von {q.name} enthält keine Feature-Typen.")
    return tuple(namen)


def layer_fuer(typ: str) -> str:
    """Feature-Type-Name eines Behördentyps: fest eingetragen oder per Suche in GetCapabilities.

    Suche: zuerst exakter Name (mit oder ohne Namensraum-Präfix), dann eindeutiger Teilstring.
    """
    t = _typ(typ)
    if t.layer:
        return t.layer
    namen = verfuegbare_layer(t.quelle)
    suche = t.layer_suche.lower()
    exakt = [n for n in namen if suche in (n.lower(), n.lower().rsplit(":", 1)[-1])]
    if exakt:
        return exakt[0]
    teil = [n for n in namen if suche in n.lower()]
    if len(teil) == 1:
        return teil[0]
    if not teil:
        raise LayerNichtGefunden(
            f"Kein Layer für '{typ}' in {_quelle(t.quelle).name} (Suche nach '{t.layer_suche}'). "
            f"Verfügbar: {', '.join(namen)}"
        )
    raise LayerNichtGefunden(
        f"Suche '{t.layer_suche}' für '{typ}' ist mehrdeutig: {', '.join(teil)}. "
        f"Bitte 'layer' in der Konfiguration fest eintragen."
    )


def _hole_geojson(quelle: Datenquelle, layer: str) -> dict:
    """Alle Features eines Layers holen; bei Server-Limit seitenweise."""
    groesse = quelle.seitengroesse or SEITENGROESSE
    wfs2 = quelle.wfs_version.startswith("2")
    features, start, crs, gesehen = [], 0, None, set()
    for _ in range(200):
        r = _get(quelle, {
            "service": "WFS", "version": quelle.wfs_version, "request": "GetFeature",
            ("typeNames" if wfs2 else "typeName"): layer, "outputFormat": quelle.output_format,
            "srsName": quelle.srs, ("count" if wfs2 else "maxFeatures"): groesse, "startIndex": start,
        })
        try:
            data = r.json()
        except ValueError as e:
            auszug = getattr(r, "text", "")[:300]
            raise DienstFehler(
                f"{quelle.name}/{layer}: Antwort ist kein GeoJSON (output_format "
                f"'{quelle.output_format}' prüfen). Antwort: {auszug}"
            ) from e
        seite = data.get("features", [])
        crs = crs or data.get("crs")
        neu = [f for f in seite if f.get("id") is None or f["id"] not in gesehen]
        gesehen.update(f["id"] for f in neu if f.get("id") is not None)
        features += neu
        gesamt = data.get("totalFeatures", data.get("numberMatched"))
        fertig = len(seite) < groesse or not neu
        if isinstance(gesamt, int):
            fertig = fertig or len(features) >= gesamt
        if fertig:
            if isinstance(gesamt, int) and len(features) < gesamt:
                raise DienstFehler(f"{quelle.name}/{layer}: nur {len(features)} von {gesamt} Features erhalten.")
            break
        start += len(seite)
    if not features:
        raise DienstFehler(f"Layer {layer} von {quelle.name} lieferte keine Features.")
    out = {"type": "FeatureCollection", "features": features}
    if crs:
        out["crs"] = crs
    return out


def _achsen_korrigieren(gdf: gpd.GeoDataFrame, crs_fallback: str = "EPSG:25832") -> gpd.GeoDataFrame:
    """Sorgt für lon/lat in EPSG:4326. Erkennt vertauschte Achsen und fehlende CRS-Angaben."""
    minx, miny, maxx, maxy = gdf.total_bounds
    if not all(map(math.isfinite, (minx, miny, maxx, maxy))):
        raise DienstFehler("Ungültige Geometrien im Layer.")

    def lonlat(a, b, c, d):
        x0, y0, x1, y1 = DEUTSCHLAND_BBOX
        return x0 <= a and c <= x1 and y0 <= b and d <= y1

    if max(abs(minx), abs(maxx), abs(miny), abs(maxy)) > 1000:  # Meter statt Grad
        if gdf.crs is None or gdf.crs.is_geographic:  # Meterwerte mit Grad-CRS: Angabe falsch
            gdf = gdf.set_crs(crs_fallback, allow_override=True)
        return gdf.to_crs(epsg=4326)
    if lonlat(minx, miny, maxx, maxy):
        return gdf.set_crs(epsg=4326) if gdf.crs is None else gdf.to_crs(epsg=4326)
    if lonlat(miny, minx, maxy, maxx):
        log.warning("Vertauschte Achsen (lat/lon) erkannt – korrigiere.")
        gdf = gdf.copy()
        gdf["geometry"] = gdf.geometry.map(lambda g: shapely.transform(g, lambda c: c[:, ::-1]))
        return gdf.set_crs(epsg=4326, allow_override=True)
    raise DienstFehler(f"Bounds {gdf.total_bounds} liegen nicht in Deutschland – CRS prüfen.")


_flaechen: dict[tuple[str, str], gpd.GeoDataFrame] = {}
_flaechen_lock = threading.Lock()


def _sicher(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", name)


def _cache_pfad(quelle_id: str, layer: str) -> Path:
    return CACHE_DIR / _sicher(quelle_id) / (_sicher(layer) + ".geojson")


def lade_flaechen(quelle_id: str, layer: str, neu_laden: bool = False) -> gpd.GeoDataFrame:
    """Zuständigkeitsflächen eines Layers (EPSG:4326, lon/lat). Speicher- und Dateicache je Quelle."""
    q = _quelle(quelle_id)
    with _flaechen_lock:
        if not neu_laden and (q.id, layer) in _flaechen:
            return _flaechen[(q.id, layer)]
        pfad = _cache_pfad(q.id, layer)
        frisch = (
            pfad.exists() and not neu_laden
            and time.time() - pfad.stat().st_mtime < CACHE_MAX_AGE_TAGE * 86400
        )
        if frisch:
            roh = pfad.read_bytes()
        else:
            roh = json.dumps(_hole_geojson(q, layer)).encode("utf-8")
            pfad.parent.mkdir(parents=True, exist_ok=True)
            pfad.write_bytes(roh)
        gdf = _achsen_korrigieren(gpd.read_file(BytesIO(roh)), q.crs_fallback)
        gdf.sindex  # Spatial Index vorab aufbauen
        _flaechen[(q.id, layer)] = gdf
        return gdf


def lade_flaechen_fuer(typ: str, neu_laden: bool = False) -> gpd.GeoDataFrame:
    return lade_flaechen(_typ(typ).quelle, layer_fuer(typ), neu_laden)


def geladene_layer() -> list[str]:
    return sorted(f"{q}:{layer}" for q, layer in _flaechen)


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


def _text(attr: dict, schluessel: str | None) -> str | None:
    v = attr.get(schluessel) if schluessel else None
    return v.strip() if isinstance(v, str) and v.strip() else None


def _anzeigename(attr: dict, bevorzugt: str | None = None) -> str | None:
    """Name der Stelle: konfiguriertes Attribut, sonst Heuristik. Die Rohattribute bleiben immer erhalten."""
    if name := _text(attr, bevorzugt):
        return name
    for hint in ("name", "bezeichnung", "bez", "lang"):
        for k, v in attr.items():
            if hint in k.lower() and isinstance(v, str) and v.strip():
                return v.strip()
    return next((v for v in attr.values() if isinstance(v, str) and v.strip()), None)


def zustaendigkeit_an_punkt(lat: float, lon: float, typ: str, mit_geometrie: bool = False) -> list[dict]:
    t = _typ(typ)
    flaechen = lade_flaechen_fuer(typ)
    punkt = Point(lon, lat)
    idx = flaechen.sindex.query(punkt, predicate="intersects")
    treffer = []
    for pos in idx:
        zeile = flaechen.iloc[int(pos)]
        attr = {k: _json_sicher(v) for k, v in zeile.drop(labels="geometry").items()}
        eintrag = {"name": _anzeigename(attr, t.name_attribut)}
        if t.uebergeordnet_attribut:
            eintrag["uebergeordnet"] = _text(attr, t.uebergeordnet_attribut)
        eintrag["attribute"] = attr
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
    "quellen" nennt nur die Datenquellen der abgefragten Typen.
    """
    typen = typen or list(BEHOERDENTYPEN)
    unbekannt = [t for t in typen if t not in BEHOERDENTYPEN]
    if unbekannt:
        raise ValueError(f"Unbekannte Behördentypen: {', '.join(unbekannt)}")

    if lat is not None and lon is not None:
        x0, y0, x1, y1 = DEUTSCHLAND_BBOX
        if not (y0 <= lat <= y1 and x0 <= lon <= x1):
            raise ValueError("Koordinate liegt außerhalb Deutschlands (lat/lon vertauscht?).")
        ort = Ort(lat, lon, adresse or f"{lat:.5f}, {lon:.5f}")
    elif adresse:
        ort = geocode(adresse)
    else:
        raise ValueError("Adresse oder lat und lon angeben.")

    ergebnisse = []
    for typ in typen:
        t = BEHOERDENTYPEN[typ]
        e = {"typ": typ, "label": t.label, "quelle": t.quelle}
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

    genutzt = dict.fromkeys(e["quelle"] for e in ergebnisse)
    return {
        "ort": asdict(ort),
        "ergebnisse": ergebnisse,
        "quellen": [QUELLEN[q].info() for q in genutzt],
        "geocoding": "© OpenStreetMap-Mitwirkende (Nominatim)" if adresse and lat is None else None,
    }


konfigurieren()
