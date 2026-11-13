"""Download complete source layers into atomic, checksummed offline snapshots."""
import gzip
import hashlib
import json
import os
import shutil
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from .http import get, request_url
from .wfs import feature_params, parse_page, validated_geometry, validated_point, verify_source


def now():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def normalise_feature(s, feature):
    props = feature.get("properties")
    if not isinstance(props, dict) or feature.get("id") is None:
        raise ValueError("Fehlende Eigenschaften oder stabile Feature-ID")
    if s['kind']=='authority_point':geometry,repaired=validated_point(feature.get('geometry')),False
    else:geometry, repaired = validated_geometry(feature.get("geometry"))
    for route in s["routes"]:
        if any(props.get(field) not in values for field, values in route.get("filter", {}).items()):
            continue
        name = props.get(route["name_field"])
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Amtlicher Name fehlt: {s['id']} / {feature['id']}")
        prefix = props.get(route.get("name_prefix_field", ""))
        if route.get("name_prefix_field") and (not isinstance(prefix, str) or not prefix.strip()):
            raise ValueError("Amtlicher Namenszusatz fehlt; keine Namensvermutung erlaubt")
        if prefix and not name.startswith(prefix):
            name = prefix + " " + name
        if route.get("name_prefix_literal") and not name.startswith(route["name_prefix_literal"]):
            name = route["name_prefix_literal"] + name
        if route.get("name_suffix_literal") and not name.endswith(route["name_suffix_literal"]):
            name = name + route["name_suffix_literal"]
        for old,new in route.get("name_replace_prefix", {}).items():
            if name.startswith(old):
                name = new + name[len(old):]
                break
        yield {"source_id": s["id"], "source_key": str(feature["id"]),
               "category": route["category"], "kind": s["kind"],
               "authority_name": name.strip() if s["kind"] in ("authority","authority_point") else None,
               "area_name": name.strip() if s["kind"] == "boundary_reference" else None,
               "geometry": geometry, "geometry_repaired": repaired, "properties": props,
               "scope": s["scope"], "source_date": props.get("stand") or props.get("wsk") or props.get("beginn"),
               "evidence_url": props.get("bayernPortalUrl") or s["documentation"],
               "name_rule": {k: v for k, v in route.items() if k != "category"}}


def fetch_source(s, destination, page_size=100, fetch=get, progress=None):
    if not 1 <= page_size <= 1000:
        raise ValueError("Seitengröße muss zwischen 1 und 1000 liegen")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix=f".{s['id']}.", suffix=".tmp", dir=destination))
    started = now()
    files, seen, expected, groups, counts = [], set(), None, Counter(), Counter()
    last_page_empty = False

    def save(label, url, data):
        path = work / "raw" / (label + ".gz")
        path.parent.mkdir(exist_ok=True)
        with gzip.open(path, "wb") as stream:
            stream.write(data)
        files.append({"path": str(path.relative_to(work)), "request_url": url,
                      "retrieved_at": now(), "response_sha256": digest(data), "bytes": len(data)})

    try:
        for name, (url, data) in verify_source(s, fetch).items():
            save(name, url, data)
        offset = 0
        with gzip.open(work / "records.jsonl.gz", "wt", encoding="utf-8") as output:
            while True:
                url = request_url(s["endpoint"], feature_params(s, offset, page_size))
                data = fetch(url)
                save(f"page-{offset:06d}", url, data)
                page = parse_page(s, data)
                if page.matched is not None:
                    if expected is not None and expected != page.matched:
                        raise ValueError("numberMatched änderte sich während des Imports")
                    expected = page.matched
                if not page.features:
                    last_page_empty = True
                    break
                for feature in page.features:
                    key = str(feature.get("id"))
                    if feature.get("id") is None or key in seen:
                        raise ValueError("Fehlende/wiederholte Feature-ID: Paging nicht zuverlässig")
                    seen.add(key)
                    groups[str(feature.get("properties", {}).get("behoerdenUntergruppe", "n/a"))] += 1
                    for record in normalise_feature(s, feature):
                        counts[record["category"]] += 1
                        output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
                offset += len(page.features)
                if progress:
                    progress(f"{s['id']}: {offset}" + (f"/{expected}" if expected is not None else " (Gesamtzahl unbekannt)"))
                if expected is not None and offset >= expected:
                    if offset != expected:
                        raise ValueError("Mehr Features als numberMatched")
                    break
                # Never stop on a short page: a service may cap the requested count.
                if offset > 100000:
                    raise ValueError("Unplausibel viele Features; Import gestoppt")
        if expected is not None and len(seen) != expected:
            raise ValueError(f"Unvollständiger Layer: {len(seen)} statt {expected}")
        if not seen or any(not counts[r["category"]] for r in s["routes"]):
            raise ValueError("Leere Quelle oder keine Daten für eine konfigurierte Kategorie")
        records_path = work / "records.jsonl.gz"
        manifest = {"format_version": 1, "source": s, "started_at": started, "completed_at": now(),
                    "layer_fetch_complete": True, "observed_features": len(seen),
                    "expected_features": expected, "terminal_empty_page": last_page_empty,
                    "pagination_consistency": "unique IDs, stable sort and total/terminal-page checked; remote transactions are not guaranteed",
                    "records_per_category": dict(counts), "source_subgroups": dict(groups),
                    "records_sha256": digest(records_path.read_bytes()), "requests": files,
                    "national_authority_coverage_guaranteed": False}
        (work / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        target = destination / s["id"]
        # Keep previous valid snapshots until the new download has passed all checks.
        # Immutable versioned directories allow concurrent readers and repeat imports.
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = destination / f"{s['id']}--{stamp}"
        os.replace(work, target)
        return target
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise


def read_manifest(path):
    path = Path(path)
    m = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if m.get("format_version") != 1 or m.get("layer_fetch_complete") is not True:
        raise ValueError("Snapshot ist nicht vollständig oder Version unbekannt")
    if digest((path / "records.jsonl.gz").read_bytes()) != m.get("records_sha256"):
        raise ValueError("Snapshot-Prüfsumme stimmt nicht")
    return m


def latest_snapshots(directory):
    selected = {}
    for manifest in sorted(Path(directory).glob("*/manifest.json")):
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        key = metadata["source"]["id"]
        if key not in selected or metadata["completed_at"] > selected[key][0]:
            selected[key] = (metadata["completed_at"], manifest.parent)
    return [value[1] for _, value in sorted(selected.items())]
