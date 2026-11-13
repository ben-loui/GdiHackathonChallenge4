"""
behoerdenfinder.py – Behördenkategorie + Ort -> zuständige Stelle mit Kontaktdaten.

Eingang (z. B. von der semantischen Suche):  kategorie="finanzamt", adresse oder lat/lon,
optional LeiKa-Leistungsschlüssel.

Ablauf:
  1. Kategorie (Schlüsselwort oder Synonym) -> Eintrag aus kategorien.toml
  2. Ort -> Koordinate (Nominatim) -> Gemeinde mit ARS (VG250) und Zuständigkeitsflächen
  3. ARS + Leistungsschlüssel -> PVOG: zuständige Stellen, Anschrift, Telefon, Onlinedienste
  4. Flächen-Treffer und PVOG-Stellen zusammenführen (gleicher Name -> eine Stelle)
"""
from __future__ import annotations

import difflib
import os
import re
import tomllib
from dataclasses import dataclass, field, fields
from pathlib import Path

import pvog
import zustaendigkeit as zf

KATEGORIEN_DATEI = Path(os.environ.get("ZF_KATEGORIEN", Path(__file__).with_name("kategorien.toml")))
GEMEINDE_TYP = "gemeinde"


class KategorieUnbekannt(ValueError):
    pass


@dataclass(frozen=True)
class Kategorie:
    key: str
    label: str
    synonyme: tuple[str, ...] = ()
    flaechen: tuple[str, ...] = ()
    leistungen: tuple[str, ...] = ()
    raeumlich: bool = True
    hinweis: str | None = None


def _norm(text: str) -> str:
    t = text.lower().strip()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", t)


def lade_kategorien(pfad: str | Path = KATEGORIEN_DATEI) -> tuple[dict[str, Kategorie], dict[str, str]]:
    """-> (Kategorien nach key, Index normalisierter Name -> key). Prüft Doppelungen und Schlüssel."""
    try:
        daten = tomllib.loads(Path(pfad).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        raise zf.KonfigurationsFehler(f"{pfad}: {e}") from e
    erlaubt = {f.name for f in fields(Kategorie)}
    kategorien: dict[str, Kategorie] = {}
    index: dict[str, str] = {}
    for i, roh in enumerate(daten.get("kategorie", []), 1):
        wo = f"{pfad} Kategorie {i}"
        if set(roh) - erlaubt:
            raise zf.KonfigurationsFehler(f"{wo}: unbekannte Felder {sorted(set(roh) - erlaubt)}")
        for feld in ("synonyme", "flaechen", "leistungen"):
            roh[feld] = tuple(roh.get(feld, ()))
        try:
            k = Kategorie(**roh)
        except TypeError as e:
            raise zf.KonfigurationsFehler(f"{wo}: {e}") from e
        if k.key in kategorien:
            raise zf.KonfigurationsFehler(f"{wo}: key '{k.key}' doppelt")
        bad = [l for l in k.leistungen if not re.fullmatch(r"\d{14}", l)]
        if bad:
            raise zf.KonfigurationsFehler(f"{wo}: LeiKa-Schlüssel müssen 14-stellig sein: {bad}")
        kategorien[k.key] = k
        for name in (k.key, k.label, *k.label.split("/"), *k.synonyme):
            n = _norm(name)
            if n and index.setdefault(n, k.key) != k.key:
                raise zf.KonfigurationsFehler(f"{wo}: '{name}' gehört schon zu Kategorie '{index[n]}'")
    if not kategorien:
        raise zf.KonfigurationsFehler(f"{pfad}: keine [[kategorie]]-Einträge")
    return kategorien, index


KATEGORIEN, _INDEX = lade_kategorien()


def kategorie_fuer(name: str) -> Kategorie:
    """Schlüsselwort, Anzeigename oder Synonym -> Kategorie (Groß-/Kleinschreibung, Umlaute egal)."""
    n = _norm(name or "")
    if n in _INDEX:
        return KATEGORIEN[_INDEX[n]]
    vorschlaege = [_INDEX[v] for v in difflib.get_close_matches(n, list(_INDEX), n=3, cutoff=0.75)]
    tipp = f" Meinten Sie: {', '.join(dict.fromkeys(vorschlaege))}?" if vorschlaege else ""
    raise KategorieUnbekannt(f"Unbekannte Behördenkategorie '{name}'.{tipp} Erlaubt: {', '.join(KATEGORIEN)}")


def kategorien() -> list[dict]:
    """Kategorien mit Abdeckung: welche Flächen konfiguriert sind und ob PVOG genutzt wird."""
    out = []
    for k in KATEGORIEN.values():
        flaechen = [t for t in k.flaechen if t in zf.BEHOERDENTYPEN]
        out.append({
            "key": k.key, "label": k.label, "raeumlich": k.raeumlich,
            "flaechen": flaechen, "flaechen_nicht_konfiguriert": [t for t in k.flaechen if t not in flaechen],
            "pvog": bool(k.leistungen), "abgedeckt": k.raeumlich and bool(flaechen or k.leistungen),
        })
    return out


# --------------------------------------------------------------------------- #
# Zusammenführen
# --------------------------------------------------------------------------- #
_KONTAKT = ("traeger", "rolle", "anschrift", "weitere_anschriften", "telefon", "email", "fax", "web",
            "sonstiges", "oeffnungszeiten", "pvog_id")


def _gleich(flaeche: str | None, pvog_name: str | None) -> bool:
    """Gleiche Stelle: gleicher Name oder Flächenname (mind. 8 Zeichen) als Anfang des PVOG-Namens,
    z. B. "Amtsgericht Hamburg" ~ "Amtsgericht Hamburg, Nachlassgericht", nicht aber "Hamburg" ~ "Hamburger ..."."""
    na, nb = _norm(flaeche or ""), _norm(pvog_name or "")
    return bool(na and nb) and (na == nb or (len(na) >= 8 and nb.startswith(na)))


def _stellen_zusammenfuehren(flaechen: list[dict], pvog_stellen: list[dict]) -> list[dict]:
    stellen, rest = [], list(pvog_stellen)
    for f in flaechen:
        partner = next((p for p in rest if _gleich(f["name"], p.get("name"))
                        or _gleich(f["name"], p.get("titel_original"))), None)
        if partner:
            rest.remove(partner)
            f = {**f, **{k: partner[k] for k in _KONTAKT if k in partner},
                 "methode": "flaeche+pvog", "quellen": f["quellen"] + ["pvog"]}
        stellen.append(f)
    ergaenzend = bool(flaechen)  # Flächen sind maßgeblich, PVOG-Stellen ohne Gegenstück nur ergänzend
    stellen += [{**p, "methode": "pvog", "quellen": ["pvog"], **({"ergaenzend": True} if ergaenzend else {})}
                for p in rest]
    return stellen


# Behördenbezeichnung der Mittelinstanz je Land (Schlüssel: sn_l aus VG250)
_MITTELBEHOERDE = {"05": "Bezirksregierung {gen}", "06": "Regierungspräsidium {gen}",
                   "08": "Regierungspräsidium {gen}", "09": "Regierung von {gen}"}


def _pvog_quelle() -> dict:
    return {"id": "pvog", "titel": "Portalverbund-Onlinegateway (PVOG), Suchdienst", "herausgeber": "FITKO / Dataport",
            "dienst": pvog.PVOG_URL, "quellenvermerk": pvog.QUELLENVERMERK, "info_url": "https://produktportal.pvog.fitko.de"}


# --------------------------------------------------------------------------- #
# Abfrage
# --------------------------------------------------------------------------- #
def finde_behoerde(
    kategorie: str,
    adresse: str | None = None,
    *,
    lat: float | None = None,
    lon: float | None = None,
    leika: str | list[str] | None = None,
) -> dict:
    """
    Behördenkategorie + Adresse (oder lat/lon) [+ LeiKa-Schlüssel] -> zuständige Stellen mit Kontakt.

    Fehler einzelner Quellen (WFS, PVOG) brechen die Antwort nicht ab, sondern stehen in "hinweise".
    """
    kat = kategorie_fuer(kategorie)
    leika_ids = [leika] if isinstance(leika, str) else list(leika or [])
    leika_ids = [l.strip() for l in leika_ids if l and l.strip()]
    falsch = [l for l in leika_ids if not re.fullmatch(r"\d{14}", l)]
    if falsch:
        raise ValueError(f"LeiKa-Schlüssel müssen 14-stellig sein: {', '.join(falsch)}")

    antwort: dict = {"kategorie": {"key": kat.key, "label": kat.label}, "ort": None, "stellen": [], "leistung": None,
                     "onlinedienste": [], "eindeutig": False, "hinweise": [], "quellen": []}
    if kat.hinweis:
        antwort["hinweise"].append(kat.hinweis)
    if not kat.raeumlich:
        return antwort

    flaechen_typen = [t for t in kat.flaechen if t in zf.BEHOERDENTYPEN]
    abfrage_typen = list(dict.fromkeys(([GEMEINDE_TYP] if GEMEINDE_TYP in zf.BEHOERDENTYPEN else []) + flaechen_typen))
    if abfrage_typen:
        erg = zf.finde_zustaendigkeit(adresse, lat=lat, lon=lon, typen=abfrage_typen)
    else:  # kein Gemeinde-Typ konfiguriert: nur den Ort bestimmen
        o = zf.ort_bestimmen(adresse, lat, lon)
        erg = {"ort": zf.asdict(o), "ergebnisse": [], "quellen": [],
               "geocoding": zf.GEOCODING_VERMERK if adresse and lat is None else None}
        antwort["hinweise"].append(f"Kein Gemeinde-Layer ('{GEMEINDE_TYP}') konfiguriert, daher keine PVOG-Abfrage.")
    ort = {**erg["ort"]}
    nach_typ = {e["typ"]: e for e in erg["ergebnisse"]}

    # Gemeinde und ARS
    gem = nach_typ.get(GEMEINDE_TYP, {})
    ars = None
    if gem.get("treffer"):
        g = gem["treffer"][0]
        ars = str(g["attribute"].get("ars") or "") or None
        ort.update(gemeinde=g["attribute"].get("gen") or g["name"], ars=ars)
        if len(gem["treffer"]) > 1:
            antwort["hinweise"].append("Der Punkt liegt auf einer Gemeindegrenze; verwendet wurde " + g["name"] + ".")
    elif gem.get("fehler"):
        antwort["hinweise"].append(f"Gemeinde nicht ermittelbar: {gem['fehler']}")
    antwort["ort"] = ort

    # Flächen
    flaechen_stellen = []
    for typ in flaechen_typen:
        e = nach_typ.get(typ, {})
        if e.get("fehler"):
            antwort["hinweise"].append(f"{e['label']}: {e['fehler']}")
        for t in e.get("treffer", []):
            name = t["name"]
            if typ == "regierungsbezirk" and t["attribute"].get("sn_l") in _MITTELBEHOERDE:
                name = _MITTELBEHOERDE[t["attribute"]["sn_l"]].format(gen=t["attribute"].get("gen", ""))
            flaechen_stellen.append({k: v for k, v in {
                "name": name, "art": e["label"], "gebiet": t["name"] if name != t["name"] else None,
                "uebergeordnet": t.get("uebergeordnet"),
                "quellen": [e["quelle"]], "methode": "flaeche"}.items() if v is not None})
        if len(e.get("treffer", [])) > 1:
            antwort["hinweise"].append(f"{e['label']}: mehrere Flächen treffen zu (Grenzlage oder Überlappung).")

    # PVOG
    pvog_erg = None
    leistungen = list(dict.fromkeys(leika_ids + list(kat.leistungen)))
    if leistungen and ars:
        try:
            pvog_erg = pvog.zustaendige_stellen(ars, leistungen)
        except pvog.PvogFehler as err:
            antwort["hinweise"].append(f"PVOG nicht erreichbar, Kontaktdaten fehlen: {err}")
        if pvog_erg is None and not any("PVOG nicht" in h for h in antwort["hinweise"]):
            antwort["hinweise"].append("PVOG kennt für diese Leistung(en) an diesem Ort keine zuständige Stelle.")
        elif leika_ids and pvog_erg and pvog_erg["leistung"]["leika"] not in leika_ids:
            antwort["hinweise"].append(
                "Zum übergebenen Leistungsschlüssel kennt PVOG hier keine Stelle; verwendet wurde eine typische Leistung der Kategorie.")
    elif leistungen and not ars:
        antwort["hinweise"].append("Ohne Gemeindeschlüssel (ARS) keine PVOG-Abfrage möglich.")

    pvog_stellen = pvog_erg["stellen"] if pvog_erg else []
    antwort["stellen"] = _stellen_zusammenfuehren(flaechen_stellen, pvog_stellen)
    if pvog_erg:
        antwort["leistung"] = pvog_erg["leistung"]
        antwort["onlinedienste"] = pvog_erg["onlinedienste"]
        if pvog_erg["weitere_stellen"]:
            antwort["hinweise"].append(f"PVOG nennt {pvog_erg['weitere_stellen']} weitere Stellen (gekürzt).")
    haupt = [s for s in antwort["stellen"] if not s.get("ergaenzend")]
    antwort["eindeutig"] = len(haupt) == 1
    if len(haupt) > 1 and not flaechen_stellen:
        antwort["hinweise"].append("Es kommen mehrere Stellen in Frage; die genaue Zuständigkeit kann z. B. vom Stadtteil abhängen.")
    if pvog_erg and pvog_erg["nur_ansprechpunkte"] and not flaechen_stellen:
        antwort["hinweise"].append("PVOG nennt hier nur Ansprechpunkte, keine ausdrücklich zuständige Stelle.")
    if not antwort["stellen"]:
        antwort["hinweise"].append("Für diese Kategorie wurde an diesem Ort keine Stelle gefunden.")

    genutzt = {q for s in antwort["stellen"] for q in s["quellen"]}
    if ars:
        genutzt.add(gem["quelle"])
    antwort["quellen"] = [q for q in erg["quellen"] if q["id"] in genutzt]
    if pvog_erg:
        antwort["quellen"].append(_pvog_quelle())
    if erg.get("geocoding"):
        antwort["quellen"].append({"id": "nominatim", "quellenvermerk": erg["geocoding"]})
    return antwort
