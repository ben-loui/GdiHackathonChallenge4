import json
import unicodedata
from importlib.resources import files


def resource(name):
    return files("behoerden_resolver").joinpath("resources", name)


def categories():
    return json.loads(resource("categories.json").read_text(encoding="utf-8"))


def sources():
    return json.loads(resource("sources.json").read_text(encoding="utf-8"))


def normalise(value):
    value = value.lower().replace("ß", "ss")
    for a, b in [("ä", "ae"), ("ö", "oe"), ("ü", "ue")]:
        value = value.replace(a, b)
    return "".join(c for c in unicodedata.normalize("NFKD", value) if c.isalnum())


def category(value):
    matches = [c for c in categories() if normalise(value) in
               {normalise(s) for s in [c["id"], c["label"], *c["aliases"]]}]
    if len(matches) != 1:
        raise ValueError(f"Unbekannte oder mehrdeutige Kategorie: {value}")
    return matches[0]


def source(value):
    for s in sources():
        if s["id"] == value:
            return s
    raise ValueError(f"Unbekannte Quelle: {value}")


def plan(value):
    c = category(value)
    verification_file = resource("verification.json")
    verification = json.loads(verification_file.read_text(encoding="utf-8")) if verification_file.is_file() else {}
    verified = {r["source_id"]: r for r in verification.get("sources", [])}
    routes = []
    derivations = []
    for s in sources():
        if s.get("active") is False:
            continue
        for route in s["routes"]:
            if route["category"] == c["id"]:
                if s["format"] not in ("geojson", "gml"):
                    derivations.append(s)
                    continue
                routes.append({"source_id": s["id"], "endpoint": s["endpoint"],
                               "layer": s["layer"], "scope": s["scope"],
                               "semantics": s["kind"], "filter": route.get("filter"),
                               "license": s["license"], "documentation": s["documentation"],
                               "verification": {"checked_at": verification.get("verified_at"),
                                   "status": verified.get(s["id"], {}).get("status", "not_verified"),
                                   "checks": verified.get(s["id"], {}).get("checks", {})}})
    return {**c, "wfs": routes, "local_derivations": derivations, "local_table": f"behoerden.{c['id']}",
            "national_coverage_guaranteed": False}
