"""
pvog.py – Zuständige Stellen mit Kontaktdaten aus dem Portalverbund-Onlinegateway (PVOG).

Suchdienst-REST-API: https://pvog.fitko.net/suchdienst/api (ohne Anmeldung nutzbar,
optionale Client-ID im Header pvog-sud-api-client-id, Doku: produktportal.pvog.fitko.de).

Ablauf je Anfrage (ARS der Gemeinde + LeiKa-Schlüssel einer Leistung):
  /v3/servicedescriptions/leikaid   -> Leistung im Gebiet
  /v6/servicedescriptions/{id}/detail -> zuständige Organisationseinheiten + Onlinedienste
  /v5/organisationunits/detail      -> Anschrift, Telefon, E-Mail, Öffnungszeiten, Web
"""
from __future__ import annotations

import html
import logging
import os
import re
import time
from functools import lru_cache

import requests

import zustaendigkeit as zf

log = logging.getLogger("zustaendigkeit.pvog")

PVOG_URL = os.environ.get("ZF_PVOG_URL", "https://pvog.fitko.net/suchdienst/api").rstrip("/")
CLIENT_ID = os.environ.get("ZF_PVOG_CLIENT_ID", "").strip()
TIMEOUT = 20
CACHE_STUNDEN = 12
MAX_STELLEN = 5
QUELLENVERMERK = "Portalverbund-Onlinegateway (PVOG), FITKO / Dataport"
ROLLE_ZUSTAENDIG = "02"


class PvogFehler(zf.DienstFehler):
    """PVOG nicht erreichbar oder unerwartete Antwort."""


def _get_roh(pfad: str, params: tuple) -> dict | list:
    headers = {"Accept": "application/json", "Accept-Language": "de", "User-Agent": zf.USER_AGENT}
    if CLIENT_ID:
        headers["pvog-sud-api-client-id"] = CLIENT_ID
    try:
        r = requests.get(f"{PVOG_URL}{pfad}", params=dict(params), headers=headers, timeout=TIMEOUT)
        if r.status_code == 404:
            return {}
        r.raise_for_status()
        return r.json()
    except (requests.RequestException, ValueError) as e:
        raise PvogFehler(f"PVOG-Abfrage {pfad} fehlgeschlagen: {e}") from e


@lru_cache(maxsize=4096)
def _get_cache(pfad: str, params: tuple, zeitfenster: int) -> dict | list:
    return _get_roh(pfad, params)


def _get(pfad: str, **params) -> dict | list:
    """GET mit Speicher-Cache (CACHE_STUNDEN); Fehler werden nicht zwischengespeichert."""
    return _get_cache(pfad, tuple(sorted(params.items())), int(time.time() // (CACHE_STUNDEN * 3600)))


# --------------------------------------------------------------------------- #
# Aufbereitung
# --------------------------------------------------------------------------- #
_CODE_VORN = re.compile(r"^(?:[0-9A-Z]{1,6}[./]){1,8}[0-9A-Z]{1,6}\s+")
_CODE_MITTE = re.compile(r"\s-\s(?:[0-9A-Z]{1,6}[./]){1,8}[0-9A-Z]{1,6}\s+")


def bereinige_titel(titel: str) -> str:
    """Interne Aktenzeichen entfernen: '00.00.KVMZ.05.52.01 Zulassung' -> 'Zulassung',
    'Stadt Ingelheim - 32/2 Pass- und Meldewesen' -> 'Stadt Ingelheim - Pass- und Meldewesen'."""
    t = _CODE_MITTE.sub(" - ", titel.strip())
    t = _CODE_VORN.sub("", t)
    return t.strip() or titel.strip()


def _text(html_text: str | None) -> str | None:
    if not html_text:
        return None
    t = re.sub(r"<br\s*/?>|</p>|</li>", "\n", html_text)
    t = html.unescape(re.sub(r"<[^>]+>", "", t))
    t = re.sub(r"[ \t\xa0]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t).strip()
    return t or None


_PLATZHALTER = re.compile(r"^(keine (straße|angabe)|-+|\.+|k\.?\s?a\.?)$", re.I)


def _wert(x: str | None) -> str | None:
    x = (x or "").strip()
    return None if not x or _PLATZHALTER.match(x) else x


def _anschrift(a: dict) -> dict:
    a = {**a, **{k: _wert(a.get(k)) for k in ("street", "houseNumber", "zip", "city", "additional", "postbox")}}
    zeile = " ".join(x for x in (a.get("street"), a.get("houseNumber")) if x).strip()
    if not zeile and a.get("postbox"):
        zeile = f"Postfach {a['postbox']}"
    ort = " ".join(x for x in (a.get("zip"), a.get("city")) if x).strip()
    out = {"art": a.get("type"), "strasse": zeile or None, "ort": ort or None,
           "zusatz": a.get("additional") or None}
    geo = a.get("geo") or {}
    if geo.get("latitude") and geo.get("longitude"):
        out["lat"], out["lon"] = float(geo["latitude"]), float(geo["longitude"])
    if a.get("wheelchairAccessible") is not None:
        out["barrierefrei"] = a["wheelchairAccessible"]
    return {k: v for k, v in out.items() if v is not None}


def _kommunikation(eintraege: list[dict]) -> dict:
    out: dict[str, list] = {}
    for c in eintraege:
        name, wert = (c.get("name") or "").lower(), c.get("value")
        if not wert:
            continue
        art = ("telefon" if "telefon" in name else "email" if "mail" in name else
               "fax" if "fax" in name else "web" if any(w in name for w in ("web", "internet", "url")) else "sonstiges")
        eintrag = wert if not c.get("additional") else f"{wert} ({c['additional']})"
        out.setdefault(art, []).append(eintrag)
    return out


def stelle_aus_oe(d: dict, rolle: dict | None = None) -> dict:
    """PVOG-Organisationseinheit -> kompakte Stelle mit Kontakt."""
    loc = d.get("location") or {}
    adressen = [_anschrift(a) for a in loc.get("addresses", [])]
    haus = [a for a in adressen if a.get("art") == "Hausanschrift"] or [a for a in adressen if a.get("strasse")]
    traeger = next((i["title"].strip() for i in d.get("internetAddresses", [])
                    if i.get("title") and not re.match(r"^(https?://|www\.)|^[\w.-]+\.(de|com|org|net|eu)$", i["title"].strip())), None)
    web = [i["uri"] for i in d.get("internetAddresses", []) if i.get("uri")]
    web += [u.get("uri") for u in loc.get("urls", []) if isinstance(u, dict) and u.get("uri")]
    zeiten = [_text(i.get("text")) for i in d.get("additionalInformation", [])
              if i.get("type") == "INFO_TIMES" or "ffnungszeit" in (i.get("title") or "")]
    titel = d.get("title") or ""
    stelle = {
        "name": bereinige_titel(titel),
        "traeger": traeger,
        "rolle": (rolle or d.get("role") or {}).get("name"),
        "anschrift": haus[0] if haus else (adressen[0] if adressen else None),
        "weitere_anschriften": (haus[1:] if haus else adressen[1:]) or None,
        **_kommunikation(loc.get("communications", [])),
        "web": list(dict.fromkeys(web)) or None,
        "oeffnungszeiten": next((z for z in zeiten if z), None),
        "pvog_id": d.get("id"),
    }
    if stelle["name"] != titel.strip():
        stelle["titel_original"] = titel
    return {k: v for k, v in stelle.items() if v not in (None, [], "")}


def _onlinedienste(det: dict) -> list[dict]:
    out = []
    for o in det.get("onlineServiceLinks", []):
        if o.get("uri"):
            out.append({"titel": o.get("title"), "url": o["uri"]})
    return out


# --------------------------------------------------------------------------- #
# Abfrage
# --------------------------------------------------------------------------- #
def zustaendige_stellen(ars: str, leika_ids: list[str], max_stellen: int = MAX_STELLEN) -> dict | None:
    """
    Erste Leitleistung (in Reihenfolge von leika_ids), zu der PVOG im Gebiet `ars`
    Organisationseinheiten kennt -> {"leistung", "stellen", "onlinedienste", ...}.
    None, wenn keine der Leistungen im Gebiet eine Stelle hat.
    """
    if not re.fullmatch(r"\d{12}", ars or ""):
        raise ValueError(f"ARS muss 12-stellig sein, nicht '{ars}'.")
    versucht = []
    for leika in leika_ids:
        if not re.fullmatch(r"\d{14}", leika):
            raise ValueError(f"LeiKa-Schlüssel muss 14-stellig sein, nicht '{leika}'.")
        versucht.append(leika)
        treffer = _get("/v3/servicedescriptions/leikaid", leikaIds=leika, ars=ars, size=5)
        for lb in (treffer.get("content") or [])[:3] if isinstance(treffer, dict) else []:
            det = _get(f"/v6/servicedescriptions/{lb['id']}/detail", ars=ars)
            orgs = det.get("organisations") or [] if isinstance(det, dict) else []
            if not orgs:
                continue
            # "Allzuständigkeit ..." sind virtuelle Sammel-Einheiten (z. B. Hamburg), keine Anlaufstelle
            echte = [o for o in orgs if not (o.get("title") or "").startswith("Allzuständigkeit")] or orgs
            zustaendig = [o for o in echte if (o.get("role") or {}).get("code") == ROLLE_ZUSTAENDIG]
            auswahl = zustaendig or echte
            stellen, gesehen = [], set()
            for o in auswahl[:max_stellen]:
                d = _get("/v5/organisationunits/detail", q=o["id"], ars=ars, lbId=lb["id"])
                if not d:
                    continue
                s = stelle_aus_oe(d, o.get("role"))
                schluessel = (s.get("name"), (s.get("anschrift") or {}).get("strasse"))
                if schluessel not in gesehen:  # PVOG liefert manche Stellen doppelt
                    gesehen.add(schluessel)
                    stellen.append(s)
            if not stellen:
                continue
            portal = next((p.get("uri") for p in lb.get("sourcePortals", []) if p.get("uri")), None)
            return {
                "leistung": {"name": lb.get("name"), "leika": leika, "pvog_id": lb["id"], "portal_url": portal},
                "stellen": stellen,
                "nur_ansprechpunkte": not zustaendig,
                "weitere_stellen": max(0, len(auswahl) - max_stellen),
                "onlinedienste": _onlinedienste(det) or _onlinedienste(lb),
                "versuchte_leistungen": versucht,
            }
    return None
