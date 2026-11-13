import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from . import db
from .catalog import categories, plan, source, sources
from .etl import fetch_source, latest_snapshots, now
from .derive import build_courts
from .wfs import verify_source
from .resolver import resolve
from .supplements import import_gemfa, import_mapping, import_inspire
from .locations import import_th_locations, import_osm
from .point_imports import import_points
from .regional import import_by_wohngeld,import_nw_bau
from .registries import import_bb
from .inspire_govserv import import_inspire_govserv


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def selected(args, default_only=False):
    if getattr(args, "source", None):
        return [source(name) for name in dict.fromkeys(args.source)]
    return [s for s in sources() if (not default_only or s.get("active") is not False)
            and (not default_only or getattr(args, "all", False) or s["default_import"])]


def main(argv=None):
    parser = argparse.ArgumentParser(description="Belegte Behördengebiete; keine pauschale Kreis-/Gemeindezuordnung")
    parser.add_argument("--dsn", help="PostgreSQL-Verbindung, sonst DATABASE_URL oder lokaler Standard")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("categories", help="Alle 36 Kategorien samt Abdeckung und Einschränkungen")
    sub.add_parser("sources", help="Importierbare Quellen mit Qualität und Lizenzmanifest")
    p = sub.add_parser("plan", help="WFS-Endpunkt/Layer und lokale Tabelle für Kategorie")
    p.add_argument("category")
    p = sub.add_parser("verify", help="Live: Capabilities, DescribeFeatureType und echte Feature-Abfrage")
    p.add_argument("--source", action="append")
    p.add_argument("--output", type=Path)
    sub.add_parser("init-db", help="PostGIS-Schema und 36 Kategoriepartitionen anlegen")
    sub.add_parser("coverage", help="Tatsächlich importierte Abdeckung und leere Kategorien")
    for command in ("fetch", "sync"):
        p = sub.add_parser(command, help="Vollständige konfigurierte Layer laden" + (" und in PostGIS importieren" if command == "sync" else " (keine Datenbank nötig)"))
        p.add_argument("--source", action="append")
        p.add_argument("--all", action="store_true", help="Auch optionale Quellen einschließlich OSM laden")
        p.add_argument("--page-size", type=int, default=100)
        p.add_argument('--input',type=Path,help='Bereits geladener Rohabzug für OSM oder Brandenburg-CSV-Verzeichnisse')
        p.add_argument("--snapshot-dir", type=Path, default=Path(os.environ.get("RESOLVER_DATA_DIR", "data/snapshots")))
    p = sub.add_parser("load", help="Offline-Snapshots atomar in PostGIS importieren")
    p.add_argument("paths", nargs="*", type=Path)
    p.add_argument("--snapshot-dir", type=Path, default=Path(os.environ.get("RESOLVER_DATA_DIR", "data/snapshots")))
    p = sub.add_parser("resolve", help="Kategorie + Punkt: vollständige Behördentreffer samt Polygon aus WFS/PostGIS")
    p.add_argument("category")
    p.add_argument("--lon", type=float, required=True)
    p.add_argument("--lat", type=float, required=True)
    p.add_argument("--backend", choices=["auto","local","wfs"], default="auto", help="Flächensuche: auto kombiniert WFS und lokale Ergänzungen; local nur PostGIS; wfs nur Live-Flächen. Standort-Fallback nutzt den lokalen Index.")
    p.add_argument('--no-point-fallback',action='store_true',help='Nur Zuständigkeitsflächen, keine Standortvorschläge')
    p.add_argument('--radius-km',type=float,help='Maximale Entfernung für Standortvorschläge; sonst Kategorie-Vorgabe')
    p.add_argument('--point-limit',type=int,default=3,help='Höchstens so viele nahe Standorte, Standard 3')
    p.add_argument("--geometry", action="store_true", help=argparse.SUPPRESS) # accepted for previous CLI calls; geometry is always returned
    args = parser.parse_args(argv)
    try:
        if args.command == "categories":
            emit(categories())
        elif args.command == "sources":
            emit(sources())
        elif args.command == "plan":
            emit(plan(args.category))
        elif args.command == "init-db":
            db.init(args.dsn)
            emit({"status": "ready", "categories": 36, "schema": "behoerden"})
        elif args.command == "coverage":
            emit(db.coverage(args.dsn))
        elif args.command == "resolve":
            emit(resolve(args.category, args.lon, args.lat, args.dsn, backend=args.backend,
                         point_fallback=not args.no_point_fallback,radius_km=args.radius_km,point_limit=args.point_limit))
        elif args.command == "verify":
            report = {"verified_at": now(), "sources": []}
            for s in selected(args):
                if s["format"] not in ("geojson", "gml"):
                    continue
                print(f"Prüfe {s['id']} …", file=sys.stderr, flush=True)
                entry = {"source_id": s["id"], "endpoint": s["endpoint"], "layer": s["layer"]}
                try:
                    evidence = verify_source(s)
                    entry.update(status="verified", checks={k: {"url": url, "sha256": hashlib.sha256(data).hexdigest()} for k, (url, data) in evidence.items()})
                    if s.get("active") is False:
                        entry.update(status="excluded", reason=s["exclusion_reason"])
                except Exception as exc:
                    entry.update(status="failed", error=str(exc))
                report["sources"].append(entry)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            emit(report)
            return 0 if all(s["status"] in ("verified", "excluded") for s in report["sources"]) else 2
        elif args.command == "load":
            paths = args.paths or latest_snapshots(args.snapshot_dir)
            if not paths:
                raise ValueError("Keine Snapshots vorhanden. Zuerst fetch ausführen.")
            db.init(args.dsn)
            emit([db.load_snapshot(path, args.dsn) for path in paths])
        elif args.command in ("fetch", "sync"):
            if args.command == "sync":
                db.init(args.dsn)
            results = []
            for s in selected(args, default_only=True):
                print(f"Lade {s['id']} …", file=sys.stderr, flush=True)
                try:
                    if s.get("active") is False:
                        raise ValueError(s["exclusion_reason"])
                    if s["format"] in ("bb_registry_points","bb_kommunal_points","bb_kommunal_areas"):
                        path=import_bb(s,args.snapshot_dir,args.input)
                    elif s["format"] == "statutory_by_wohngeld":
                        path=import_by_wohngeld(s,args.snapshot_dir)
                    elif s["format"] == "statutory_nw_bau":
                        path=import_nw_bau(s,args.snapshot_dir)
                    elif s["format"] == "derived":
                        path = build_courts(s, args.snapshot_dir)
                    elif s["format"] == "gemfa":
                        path = import_gemfa(s,args.snapshot_dir)
                    elif s["format"] == "csv_mapping":
                        path = import_mapping(s,args.snapshot_dir)
                    elif s["format"] == "inspire_gml_file":
                        path = import_inspire(s,args.snapshot_dir)
                    elif s['format']=='inspire_point_file':
                        path=import_th_locations(s,args.snapshot_dir)
                    elif s['format'] in ('geojson_points','arcgis_points'):
                        path=import_points(s,args.snapshot_dir)
                    elif s['format'] in ('inspire_govserv_areas','inspire_govserv_points'):
                        path=import_inspire_govserv(s,args.snapshot_dir)
                    elif s['format']=='osm':
                        path=import_osm(s,args.snapshot_dir,args.input)
                    else:
                        path = fetch_source(s, args.snapshot_dir, args.page_size,
                                            progress=lambda message: print(message, file=sys.stderr, flush=True))
                    entry = {"source_id": s["id"], "snapshot": str(path), "status": "downloaded"}
                    if args.command == "sync":
                        entry.update(db.load_snapshot(path, args.dsn), status="imported")
                except Exception as exc:
                    entry = {"source_id": s["id"], "status": "failed", "error": str(exc)}
                    print(f"FEHLER {s['id']}: {exc}", file=sys.stderr, flush=True)
                results.append(entry)
            emit(results)
            return 0 if all(r["status"] != "failed" for r in results) else 2
    except (Exception, KeyboardInterrupt) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 130 if isinstance(exc, KeyboardInterrupt) else 2
    return 0
