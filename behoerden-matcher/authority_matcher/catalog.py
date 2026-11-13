"""FIM-Normalisierung und konservative Behörden-Taxonomie.

Keine Ableitung aus 'fachlich freigegeben durch' oder 'Herausgeber'. Nur
explizite Angaben zur zuständigen Stelle gelten als Zuordnungsbeleg.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from pathlib import Path

WS = re.compile(r"\s+")
HTML = re.compile(r"<[^>]+>")
KEY_PATTERN = re.compile(r"[^a-z0-9]")


def clean(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        # XZuFi Sprachtext-Objekte: Vorzugsweise deutscher Inhalt
        for key in ("text", "value", "wert", "inhalt", "name", "bezeichnung", "label"):
            if key in value and isinstance(value[key], str):
                return clean(value[key])
        return ""
    if isinstance(value, list):
        return "; ".join(x for x in (clean(item) for item in value) if x)
    if not isinstance(value, (str, int, float)):
        return ""
    s = html.unescape(HTML.sub(" ", str(value)))
    return WS.sub(" ", s).strip()


def key_norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold().replace("ß", "ss"))
    s = "".join(x for x in s if not unicodedata.combining(x))
    return KEY_PATTERN.sub("", s)


def first(obj: dict, keys: tuple[str, ...]) -> object:
    target = {key_norm(k) for k in keys}
    for key, value in obj.items():
        if key_norm(key) in target and clean(value):
            return value
    # Some FIM responses wrap the actual object in e.g. "data", "leistung", "detail"
    for wrapper in ("data", "leistung", "service", "detail", "stammtext"):
        nested = obj.get(wrapper)
        if isinstance(nested, dict):
            val = first(nested, keys)
            if val is not None:
                return val
    return None


def source_fields(obj: object, *, max_depth: int = 7) -> list[str]:
    """Nur explizite Zuständigkeitsfelder erfassen, nicht Autoren/Freigaben.

    Strukturierte Organisationseinheiten werden NUR mit Rolle 'zuständige Stelle'
    ausgewertet. Ein generischer 'Ansprechpunkt' ist keine zuständige Stelle.
    """
    fields = []
    names = {key_norm(x) for x in (
        "zuständige Stelle", "zustaendige_stelle", "zustaendigeStelle",
        "zuständige Behörden", "zustaendige_behoerden", "zustaendigkeitStelle",
        "competentAuthority", "competent_authority",
    )}
    def walk(o: object, level: int) -> None:
        if level > max_depth:
            return
        if isinstance(o, dict):
            role = clean(first_shallow(o, ("rolle", "role", "zustaendigkeitRolle", "organisationseinheitRolle")))
            if role and key_norm(role) in {"zustandigestelle", "zustaendigestelle", "competentauthority", "zustaendig"}:
                label = clean(first_shallow(o, ("bezeichnung", "name", "organisationseinheit", "titel")))
                if label:
                    fields.append(label)
            for k, v in o.items():
                if key_norm(k) in names:
                    if isinstance(v, list):
                        for el in v:
                            label = clean(el) or (clean(first_shallow(el, ("bezeichnung", "name"))) if isinstance(el, dict) else "")
                            if label:
                                fields.append(label)
                    else:
                        label = clean(v)
                        if label:
                            fields.append(label)
                elif isinstance(v, (dict, list)):
                    walk(v, level + 1)
        elif isinstance(o, list):
            for v in o:
                walk(v, level + 1)
    walk(obj, 0)
    return list(dict.fromkeys(fields))


def first_shallow(obj: object, keys: tuple[str, ...]) -> object:
    if not isinstance(obj, dict):
        return None
    wanted = {key_norm(k) for k in keys}
    for k, v in obj.items():
        if key_norm(k) in wanted:
            return v
    return None


class AuthorityTaxonomy:
    def __init__(self, path: Path):
        self.items = json.loads(path.read_text(encoding="utf-8"))
        self.by_id = {x["id"]: x["label"] for x in self.items}
        # Match longest alias first; require token boundaries, not just arbitrary substrings
        self.aliases = []
        for item in self.items:
            for alias in [item["label"], *item["aliases"]]:
                norm = norm_words(alias)
                if norm:
                    self.aliases.append((len(norm), norm, item["id"]))
        self.aliases.sort(reverse=True)

    def categorize(self, source_text: str) -> list[str]:
        text = f" {norm_words(source_text)} "
        matches = []
        for _, alias, cat in self.aliases:
            if f" {alias} " in text and cat not in matches:
                matches.append(cat)
        # Einige Amtsbezeichnungen sind regional unter dem Stadt-/Kreisamt angesiedelt.
        # Bei explizit mehreren Zuständigkeiten NICHT zu einer reduzieren.
        return matches


def norm_words(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.casefold().replace("ß", "ss"))
    s = "".join(x for x in s if not unicodedata.combining(x))
    return WS.sub(" ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def normalize_record(raw: dict, taxonomy: AuthorityTaxonomy, *, origin: str = "fim") -> dict | None:
    """Normalize a FIM service text (or a clearly labelled demo example)."""
    if not isinstance(raw, dict):
        return None
    title = clean(first(raw, ("title", "titel", "leistungsbezeichnungII", "leistungsbezeichnung2", "leistungsbezeichnungI", "leistungsbezeichnung", "name", "bezeichnung")))
    if not title:
        return None
    key = clean(first(raw, ("leistungsschluessel", "leistungsschlüssel", "leika_id", "leikaSchluessel", "service_key")))
    ident = clean(first(raw, ("id", "leistungId", "leistungsId", "fim_id")))
    red = clean(first(raw, ("redaktionId", "redaktion_id")))
    ident = key or f"{red}:{ident}" if red and not key else (key or ident)
    if not ident:
        return None
    raw_syn = first(raw, ("synonyms", "synonyme", "begriffeImKontext", "begriffe_im_kontext", "stichworte", "stichwörter"))
    syn = []
    if isinstance(raw_syn, list):
        for s in raw_syn:
            val = clean(s)
            if val:
                syn.append(val)
    elif raw_syn:
        syn = [clean(raw_syn)]
    desc = clean(first(raw, ("description", "beschreibung", "volltext", "teaser", "kurztext")))
    # Import-Pfad ist vertrauenswürdiger als Datensatzfelder: Nutzer können "origin" nicht
    # verwenden, um künstlich offizielle Zuordnungen zu erlangen.
    fields = source_fields(raw)
    authority = []
    for field in fields:
        authority.extend(taxonomy.categorize(field))
    authority = list(dict.fromkeys(authority))
    if origin == "demo":
        status = "demo" if authority else "nicht_zugeordnet"
    elif not fields:
        status = "kein_zustaendigkeitsfeld"
    elif not authority:
        status = "nicht_zugeordnet"
    elif len(authority) > 1:
        status = "mehrdeutig"
    else:
        status = "aus_zustaendigkeitsfeld"
    return {
        "id": str(ident), "leistungsschluessel": key or None,
        "titel": title, "synonyme": syn, "beschreibung": desc,
        "zustaendige_stelle_original": fields,
        "behoerdenkategorien": authority,
        "mapping_status": status, "quelle": origin,
    }
