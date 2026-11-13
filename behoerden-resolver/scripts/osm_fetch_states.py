"""Fetch the OSM office export for all 16 Bundesländer, one Overpass request per state.

The national query times out on public Overpass servers; per-state queries are small enough.
Every state must succeed (no `remark`, timestamp present). Each raw response is cached, so a
failed run can simply be repeated. Output is accepted by:

    behoerden-resolver sync --source osm_states_locations --input data/osm_states.json

Usage: python scripts/osm_fetch_states.py [--out data/osm_states.json] [--cache-dir data/osm_cache]
       [--endpoint https://overpass-api.de/api/interpreter] [--pause 15] [--state DE-BW ...]
Respect the usage policy of the Overpass instance; use your own instance or an extract for regular runs.
"""
import argparse
import json
import sys
import time
from pathlib import Path
from behoerden_resolver.catalog import resource
from behoerden_resolver.http import get, request_url

STATES = ["DE-BW", "DE-BY", "DE-BE", "DE-BB", "DE-HB", "DE-HH", "DE-HE", "DE-MV",
          "DE-NI", "DE-NW", "DE-RP", "DE-SL", "DE-SN", "DE-ST", "DE-SH", "DE-TH"]


def validate(obj, state):
    if obj.get("remark"):
        raise ValueError(f"{state}: unvollständiger Overpass-Abzug: {obj['remark']}")
    if not isinstance(obj.get("elements"), list) or not obj.get("osm3s", {}).get("timestamp_osm_base"):
        raise ValueError(f"{state}: kein vollständiger OSM-Export")
    return obj


def merge(parts):
    """parts: {state: validated response}. Elements are deduplicated by (type, id)."""
    elements, seen = [], set()
    for state in sorted(parts):
        for e in parts[state]["elements"]:
            key = (e.get("type"), e.get("id"))
            if key in seen:
                continue
            seen.add(key)
            elements.append(e)
    # The oldest state timestamp is the honest data date for the merged file.
    stamp = min(p["osm3s"]["timestamp_osm_base"] for p in parts.values())
    return {"version": 0.6, "generator": "scripts/osm_fetch_states.py",
            "osm3s": {"timestamp_osm_base": stamp, "copyright": "© OpenStreetMap-Mitwirkende, ODbL 1.0"},
            "states": {s: len(p["elements"]) for s, p in sorted(parts.items())}, "elements": elements}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=Path("data/osm_states.json"))
    ap.add_argument("--cache-dir", type=Path, default=Path("data/osm_cache"))
    ap.add_argument("--endpoint", default="https://overpass-api.de/api/interpreter")
    ap.add_argument("--pause", type=float, default=15, help="Sekunden zwischen Abfragen")
    ap.add_argument("--state", action="append", choices=STATES, help="Nur diese Länder (Ergebnis dann unvollständig, nicht importieren)")
    args = ap.parse_args(argv)
    template = resource("osm_states.overpass").read_text(encoding="utf-8")
    states = args.state or STATES
    args.cache_dir.mkdir(parents=True, exist_ok=True)
    parts = {}
    for i, state in enumerate(states):
        cache = args.cache_dir / f"{state}.json"
        if cache.exists():
            data = cache.read_bytes()
        else:
            if i:
                time.sleep(args.pause)
            print(f"Lade {state} …", file=sys.stderr, flush=True)
            data = get(request_url(args.endpoint, {"data": template.replace("{STATE}", state)}), attempts=3)
        parts[state] = validate(json.loads(data), state)
        cache.write_bytes(data)  # only validated responses are cached
    merged = merge(parts)
    if not args.state:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(merged, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{len(merged['elements'])} Elemente aus {len(parts)} Ländern -> {args.out}", file=sys.stderr)
    else:
        print("Teilabzug: keine Ausgabedatei geschrieben (alle 16 Länder sind Pflicht).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
