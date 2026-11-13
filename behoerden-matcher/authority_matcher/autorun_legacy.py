"""`authority-matcher` : auto-sync (FIM), auto-index (Elasticsearch), interactive queries.

No demo fallback and no silent 'complete' status if one of the FIM sources
could not be fully retrieved. User data stays under ~/.local/share/authority-matcher.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from .catalog import AuthorityTaxonomy
from .cli import DEFAULT_TAXONOMY, show
from .full_sync import SOURCES, export_jsonl, sync_catalog, sync_status
from .index import es_client, index_elastic, load_catalog
from .matcher import match_authority

ROOT = Path(__file__).resolve().parent.parent
DATA_HOME = Path(os.environ.get("AUTHORITY_MATCHER_HOME", Path.home() / ".local/share/authority-matcher"))
DB_PATH = DATA_HOME / "fim_catalog.sqlite3"
EXPORT_PATH = DATA_HOME / "fim_catalog.jsonl"
INDEX = "fim-fachbehoerden-v2"
MODEL = "intfloat/multilingual-e5-small"
ES_URL = os.environ.get("ELASTICSEARCH_URL", "http://127.0.0.1:9200")


def ensure_es(url: str, *, quiet: bool = False) -> None:
    try:
        if es_client(url).ping():
            return
    except Exception:
        pass
    if url != "http://127.0.0.1:9200" and url != "http://localhost:9200":
        raise RuntimeError("Eigener Elasticsearch-Server nicht erreichbar: " + url)
    if shutil.which("docker") is None:
        raise RuntimeError("Elasticsearch ist nicht erreichbar und 'docker' fehlt. Docker Desktop installieren und starten.")
    compose = ROOT / "compose.yaml"
    try:
        subprocess.run(["docker", "compose", "-f", str(compose), "up", "-d"],
                       check=True, timeout=120, capture_output=quiet, text=quiet)
    except (subprocess.CalledProcessError, OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("Docker Compose konnte Elasticsearch nicht starten; Docker Desktop bitte prüfen") from exc
    for _ in range(90):
        try:
            if es_client(url).ping():
                return
        except Exception:
            pass
        time.sleep(2)
    raise RuntimeError("Elasticsearch antwortet noch nicht auf " + url)


def cli_args(argv: list[str] | None = None):
    p = argparse.ArgumentParser(prog="authority-matcher", description="Freitext → fachliche deutsche Behördenart auf Grundlage des FIM-Katalogs")
    p.add_argument("--refresh", action="store_true", help="Unvollständige Quellen weiterladen und Index neu erstellen")
    p.add_argument("--status", action="store_true", help="FIM-Importstatus anzeigen")
    p.add_argument("--json", action="store_true", help="Ergebnisse als JSON ausgeben")
    p.add_argument("--no-semantic", action="store_true", help="Nur Elasticsearch-Volltextsuche (keine Embeddings)")
    p.add_argument("--max-records", type=int, default=None, help="Nur Entwicklungsmodus: Import begrenzen; nie als vollständig behandeln")
    p.add_argument("--workers", type=int, default=4, help="Parallele FIM-Detailabrufe (Standard: 4, maximal 12)")
    p.add_argument("--max-rps", type=float, default=5.0, help="Maximale gestartete Detailabfragen/Sekunde (Standard: 5; bei 429 senken)")
    p.add_argument("--sources", nargs="+", choices=SOURCES, default=list(SOURCES), help="FIM-Quellen (Standard: alle)")
    p.add_argument("--no-start-docker", action="store_true", help="Elasticsearch nicht selbst starten")
    p.add_argument("query", nargs="*", help="Optional direkt eine einzelne Anfrage")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = cli_args(argv)
    taxonomy = AuthorityTaxonomy(DEFAULT_TAXONOMY)
    try:
        if args.status:
            print(json.dumps(sync_status(DB_PATH), ensure_ascii=False, indent=2))
            return 0
        status = sync_status(DB_PATH)
        if args.refresh:
            print("Vorhandene FIM-Synchronisation wird fortgesetzt; abgeschlossene Quellen bleiben erhalten.", file=sys.stderr)
        sources = tuple(args.sources)
        incomplete = [s for s in sources if not status["sources"].get(s, {}).get("finished", False)]
        if incomplete or status["missing_details"] or args.refresh:
            if not shutil.which("fim-portal"):
                raise RuntimeError("FIM-Client 'fim-portal' fehlt. Installation: npm install -g @maschinenlesbar.org/fim-portal-cli")
            print("Erster Start: FIM-Katalog wird offiziell synchronisiert und aufbewahrt.", file=sys.stderr)
            sync_catalog(DB_PATH, taxonomy, sources=sources,
                         max_records=args.max_records, force_retry=args.refresh,
                         workers=args.workers, max_rps=args.max_rps)
            status = sync_status(DB_PATH)
        if not status["total_records"]:
            raise RuntimeError("Der FIM-Import hat keine Verwaltungsleistungen geliefert. Es wird KEINE Demo verwendet.")
        if args.max_records is None and any(not status["sources"].get(s, {}).get("finished", False) for s in sources):
            raise RuntimeError("FIM-Import noch unvollständig; beim nächsten Aufruf wird fortgesetzt.")
        if status["missing_details"]:
            print(f"ACHTUNG: {status['missing_details']} FIM-Detailabrufe noch fehlgeschlagen. "
                  "Katalog ist nicht vollständig; fehlende Details werden später erneut versucht. "
                  "Mit --refresh sofort erneut versuchen.", file=sys.stderr)
        print(f"FIM: {status['total_records']} Dokumente, "
              f"{status['with_authority']} davon mit erkennbarer Behördenart.", file=sys.stderr)
        ensure_es(ES_URL) if not args.no_start_docker else None
        client = es_client(ES_URL)
        if not client.ping():
            raise RuntimeError("Elasticsearch nicht erreichbar: " + ES_URL)
        manifest_path = DATA_HOME / "index_manifest.json"
        semantic = not args.no_semantic
        settings = {"count": status["total_records"], "semantic": semantic,
                    "index": INDEX, "model": MODEL if semantic else None}
        old = {}
        if manifest_path.exists():
            try:
                old = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                pass
        index_exists = bool(client.indices.exists(index=INDEX))
        if args.refresh or old != settings or not index_exists:
            print("Elasticsearch-Index wird erstellt ...", file=sys.stderr)
            count = export_jsonl(DB_PATH, EXPORT_PATH)
            docs = load_catalog(EXPORT_PATH, taxonomy)
            if count != len(docs):
                raise RuntimeError("Katalogzählung und Indexdokumente weichen ab; Import kontrollieren")
            info = index_elastic(docs, url=ES_URL, index_name=INDEX,
                                 embeddings=semantic, model_name=MODEL)
            print("Index: " + json.dumps(info, ensure_ascii=False), file=sys.stderr)
            tmp = manifest_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(settings), encoding="utf-8")
            tmp.replace(manifest_path)
        if args.max_records is not None:
            print("ACHTUNG: Import mit --max-records ist nur ein TEILBESTAND.", file=sys.stderr)
        def search(text: str) -> None:
            result = match_authority(text, backend="elasticsearch", es_url=ES_URL,
                                     es_index=INDEX, semantic=semantic, embedding_model=MODEL)
            show(result, taxonomy, args.json)
        if args.query:
            search(" ".join(args.query))
        else:
            print("\nBehörden-Matcher · Anliegen eingeben (exit zum Beenden)")
            while True:
                try:
                    q = input("Anliegen> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    break
                if q.lower() in {"exit", "quit", "ende"}:
                    break
                if q:
                    search(q)
        return 0
    except Exception as exc:
        print("Fehler: " + str(exc), file=sys.stderr)
        return 1
