"""Explicit statutory assignment table + official VG25 regions, no spatial guess."""
import csv
import gzip
import io
import json
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from shapely import union_all
from shapely.geometry import shape, mapping
from .catalog import resource, source
from .etl import digest, latest_snapshots, now, read_manifest
from .wfs import validated_geometry


def build_courts(s, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    parents = [p for p in latest_snapshots(destination) if read_manifest(p)["source"]["id"] == "vg25_rbz"]
    if not parents:
        raise ValueError("Für die gesetzliche Gerichtszuordnung zuerst vg25_rbz vollständig abrufen")
    parent = parents[0]
    metadata = read_manifest(parent)
    if metadata["source"] != source("vg25_rbz"):
        raise ValueError("VG25-Quellkonfiguration geändert; zuerst neuen geprüften Snapshot abrufen")
    with gzip.open(parent / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
        regions = [json.loads(line) for line in stream]
    table = resource("by_courts.csv").read_bytes()
    if digest(table) != s["mapping_sha256"]:
        raise ValueError("Zuordnungstabelle wurde geändert; Quellenprüfung und Manifest aktualisieren")
    rows = list(csv.DictReader(io.StringIO(table.decode("utf-8"))))
    if len(rows) != 6 or set("|".join(r["ars"] for r in rows).split("|")) != {"091","092","093","094","095","096","097"}:
        raise ValueError("Unvollständige gesetzliche Zuordnungstabelle")
    work = Path(tempfile.mkdtemp(prefix=".derived-courts.", suffix=".tmp", dir=destination))
    try:
        with gzip.open(work / "records.jsonl.gz", "wt", encoding="utf-8") as output:
            for row in rows:
                polygons, source_keys, repaired = [], [], False
                for ars, expected_name in zip(row["ars"].split("|"), row["region_names"].split("|"), strict=True):
                    parts = [r for r in regions if r["properties"].get("ars") == ars]
                    if not parts or any(r["area_name"] != expected_name for r in parts):
                        raise ValueError(f"VG25-Region {ars}/{expected_name} fehlt oder wurde geändert")
                    polygons.extend(shape(r["geometry"]) for r in parts)
                    source_keys.extend(r["source_key"] for r in parts)
                    repaired |= any(r["geometry_repaired"] for r in parts)
                geom, union_repaired = validated_geometry(mapping(union_all(polygons)))
                record = {"source_id": s["id"], "source_key": row["source_key"], "category": "verwaltungsgericht",
                          "kind": "authority", "authority_name": row["authority_name"], "area_name": None,
                          "geometry": geom, "geometry_repaired": repaired or union_repaired,
                          "scope": "DE-BY", "source_date": s["mapping_reviewed_at"],
                          "evidence_url": s["legal_basis"],
                          "name_rule": {"method": "explicit official name in reviewed CSV; statutory region assignment"},
                          "properties": {"court_evidence_url": row["evidence_url"], "region_ars": row["ars"].split("|"),
                              "legal_basis": s["legal_basis"], "mapping_sha256": digest(table),
                              "mapping_reviewed_at": s["mapping_reviewed_at"],
                              "boundary_source": "vg25_rbz", "boundary_source_keys": source_keys,
                              "boundary_snapshot_completed_at": metadata["completed_at"],
                              "boundary_snapshot_records_sha256": metadata["records_sha256"]}}
                output.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")
        manifest = {"format_version": 1, "source": s, "completed_at": now(),
                    "layer_fetch_complete": True, "derivation_complete": True,
                    "observed_features": 6, "expected_features": 6,
                    "records_per_category": {"verwaltungsgericht": 6},
                    "records_sha256": digest((work / "records.jsonl.gz").read_bytes()),
                    "mapping_sha256": digest(table), "mapping_reviewed_at": s["mapping_reviewed_at"],
                    "parent_snapshot": {"directory": parent.name, "records_sha256": metadata["records_sha256"],
                                        "completed_at": metadata["completed_at"]},
                    "national_authority_coverage_guaranteed": False,
                    "note": "Derived locally; completion date is not a fresh legal or name-source verification"}
        (work / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        target = destination / (s["id"] + "--" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
        os.replace(work, target)
        return target
    except BaseException:
        shutil.rmtree(work, ignore_errors=True)
        raise
