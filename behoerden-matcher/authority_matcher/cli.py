"""behoerden-match: import → index → match, ohne Standort."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from .catalog import AuthorityTaxonomy
from .fim_import import collect_fim
from .index import index_elastic, load_catalog
from .matcher import LocalMatcher, compact_result, match_authority

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TAXONOMY = ROOT / "data/categories.json"
DEMO = ROOT / "data/demo_services.jsonl"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="behoerden-match", description="Freitext → fachliche Behördenkategorie (ohne Standort)")
    p.add_argument("--taxonomy", type=Path, default=DEFAULT_TAXONOMY)
    subs = p.add_subparsers(dest="command", required=True)

    demo = subs.add_parser("seed-demo", help="Kennzeichnete Beispieldaten exportieren (NICHT amtlich)")
    demo.add_argument("--output", type=Path, default=Path("data/demo.jsonl"))

    imp = subs.add_parser("fim-import", help="Echte Stammtexte über FIM-API/CLI laden und normalisieren")
    imp.add_argument("--output", type=Path, default=Path("data/fim.jsonl"))
    imp.add_argument("--limit", type=int, default=300)
    imp.add_argument("--source", choices=["leika", "landesredaktion"], default="leika")
    imp.add_argument("--fim-executable", default="fim-portal")

    prep = subs.add_parser("prepare", help="Raw JSONL/JSON FIM-Stammtexte in einheitliches JSONL umwandeln")
    prep.add_argument("--input", type=Path, required=True)
    prep.add_argument("--output", type=Path, required=True)

    ind = subs.add_parser("index", help="Elasticsearch-Index aufbauen")
    ind.add_argument("--input", type=Path, required=True)
    ind.add_argument("--url", default=os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"))
    ind.add_argument("--index", default="fim-authorities-v1")
    ind.add_argument("--semantic", action="store_true", help="SentenceTransformer-Embeddings indexieren")
    ind.add_argument("--model", default="intfloat/multilingual-e5-small")

    for name in ("query", "repl"):
        q = subs.add_parser(name, help="Einzelanfrage" if name == "query" else "Interaktiv im Terminal")
        if name == "query":
            q.add_argument("text", nargs="+", help="Freie natürlichsprachliche Anfrage")
        q.add_argument("--input", type=Path, default=Path("data/demo_services.jsonl"))
        q.add_argument("--backend", choices=["local", "elasticsearch"], default="local")
        q.add_argument("--url", default=os.environ.get("ELASTICSEARCH_URL", "http://localhost:9200"))
        q.add_argument("--index", default="fim-authorities-v1")
        q.add_argument("--semantic", action="store_true")
        q.add_argument("--model", default="intfloat/multilingual-e5-small")
        q.add_argument("--json", action="store_true", help="Maschinenlesbares JSON ausgeben")
        q.add_argument("--details", "--debug", action="store_true", help="Detaillierte Leistungs- und Behördenbelege anzeigen")
    return p


def show(result: dict, taxonomy: AuthorityTaxonomy, as_json: bool, *, details: bool = False):
    """Show only category and score, unless explicit debugging is requested."""
    if not details:
        public = compact_result(result)
        if as_json:
            print(json.dumps(public, ensure_ascii=False, indent=2))
        else:
            category = public["behoerdenkategorie"] or "null"
            score = public["score"]
            print(f"{category} (Score: {score:.5f})" if score is not None else f"{category} (Score: null)")
        return
    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    state = result["status"]
    cat = result.get("top_kategorie") or result.get("behoerdenkategorie")
    # The top-level score uses the same aggregated category ranking scale as
    # alternatives[].score; it is not a calibrated confidence probability.
    top_score = result.get("score")
    score_label = f" (Ranking-Score: {top_score:.5f})" if isinstance(top_score, (int, float)) else ""
    if state == "vorschlag":
        print("Behördenkategorie:", str(taxonomy.by_id.get(cat, cat)) + score_label)
    elif state == "mehrdeutig":
        print("Mehrdeutig, mögliche Kategorie:", str(taxonomy.by_id.get(cat, cat)) + score_label)
    else:
        print("Keine sichere Kategorie:", state)
    for candidate in result.get("leistungen", [])[:3]:
        label = ", ".join(taxonomy.by_id.get(x, x) for x in candidate["behoerdenkategorien"])
        print(f"  · {candidate['titel']} → {label} [{candidate['quelle']} / {candidate['mapping_status']}]")
    if result.get("alternativen"):
        print("Weitere mögliche Kategorien:", ", ".join(taxonomy.by_id.get(x["id"], x["id"]) for x in result["alternativen"]))
    if any(c["quelle"] == "demo" for c in result.get("leistungen", [])):
        print("Hinweis: Demo-Beispieldaten – keine amtlich verifizierte Zuständigkeit.")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        taxonomy = AuthorityTaxonomy(args.taxonomy)
        if args.command == "seed-demo":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(DEMO.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"DEMO exportiert: {args.output} (nicht amtlich)")
        elif args.command == "fim-import":
            if args.limit < 1:
                raise ValueError("--limit muss positiv sein")
            stats = collect_fim(args.output, taxonomy, source=args.source,
                                limit=args.limit, executable=args.fim_executable)
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        elif args.command == "prepare":
            docs = load_catalog(args.input, taxonomy)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("w", encoding="utf-8") as fh:
                for d in docs:
                    fh.write(json.dumps(d, ensure_ascii=False) + "\n")
            print(f"{len(docs)} Leistungen normalisiert; {sum(bool(x['behoerdenkategorien']) for x in docs)} mit Kategorie")
        elif args.command == "index":
            docs = load_catalog(args.input, taxonomy)
            info = index_elastic(docs, url=args.url, index_name=args.index,
                                 embeddings=args.semantic, model_name=args.model)
            print(json.dumps(info, ensure_ascii=False, indent=2))
        else:
            local = LocalMatcher(load_catalog(args.input, taxonomy)) if args.backend == "local" else None
            def do_query(text: str):
                result = match_authority(text, local=local, backend=args.backend,
                                         es_url=args.url, es_index=args.index,
                                         semantic=args.semantic, embedding_model=args.model)
                show(result, taxonomy, args.json, details=args.details)
            if args.command == "query":
                do_query(" ".join(args.text))
            else:
                print("Text eingeben; mit 'exit' oder Strg+D beenden")
                while True:
                    try:
                        query = input("Anliegen> ").strip()
                    except (EOFError, KeyboardInterrupt):
                        print()
                        break
                    if query.casefold() in ("exit", "quit", "ende"):
                        break
                    if query:
                        do_query(query)
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"Fehler: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
