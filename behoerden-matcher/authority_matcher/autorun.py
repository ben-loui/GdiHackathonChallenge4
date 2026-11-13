"""The one-command CLI. Reuses existing FIM SQLite; never starts a giant FIM download.

To acquire official category evidence, run `authority-matcher jzufi-import ...`
or `authority-matcher jzufi-fetch ...` first; missing evidence stays unknown.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from .catalog import AuthorityTaxonomy
from .cli import DEFAULT_TAXONOMY, show
from .index import es_client, index_elastic
from .jzufi import connect, import_files, mapping_stats
from .jzufi_fetch import get_jzufi, read_pairs
from .pvog_live import fetch_online_key, make_enricher, reference_regions
from .matcher import match_authority
from .pipeline import build_fim_documents, write_export

HOME = Path(os.environ.get('AUTHORITY_MATCHER_HOME', Path.home()/'.local/share/authority-matcher'))
DB = HOME/'fim_catalog.sqlite3'
EXPORT = HOME/'fim_jzufi_index.jsonl'
MANIFEST = HOME/'jzufi_index_manifest.json'
INDEX = os.environ.get('AUTHORITY_MATCHER_INDEX','fim-jzufi-v3')
ES_URL = os.environ.get('ELASTICSEARCH_URL','http://127.0.0.1:9200')
MODEL = 'intfloat/multilingual-e5-small'


def ensure_es(*, quiet: bool = False):
    from .autorun_legacy import ensure_es as legacy_ensure_es
    legacy_ensure_es(ES_URL, quiet=quiet)


def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog='authority-matcher',description='FIM -> JZuFi -> Behördenkategorie (ohne Nutzerstandort)')
    p.add_argument('--status',action='store_true',help='Abdeckung / Zustand der JZuFi-Verknüpfungen')
    p.add_argument('--json',action='store_true',help='JSON-Ausgabe (nur Kategorie und Score)')
    p.add_argument('--details','--debug',dest='details',action='store_true',help='Alle FIM-/PVOG-Belege und Diagnosedaten anzeigen')
    p.add_argument('--no-semantic',action='store_true',help='BM25 statt BM25+E5-Vektoren')
    p.add_argument('--reindex',action='store_true',help='Suchindex erneuern')
    p.add_argument('--no-live',action='store_true',help='Keine PVOG-Abfrage bei Suchanfragen (nur Cache)')
    p.add_argument('--reference-ars',help='Kommaseparierte Referenzgebiete nur für PVOG-Datenbeschaffung')
    p.add_argument('--live-top',type=int,default=3,help='Maximale Zahl unterschiedlicher LeiKa-Schlüssel pro Anfrage (Standard 3)')
    p.add_argument('--no-start-docker',action='store_true')
    p.add_argument('query',nargs='*',help='Anliegen oder Unterbefehl')
    return p


def status() -> dict:
    from .full_sync import sync_status
    if not DB.exists():
        return {'error':f'FIM-Datenbank nicht gefunden: {DB}'}
    con=connect(DB)
    try:
        x=mapping_stats(con)
        x['fim']=sync_status(DB)
        x['ready_for_mapping']=x['mapped_links']>0
        try:
            x['pvog_queries_cached']=con.execute('SELECT COUNT(*) FROM pvog_live_attempts').fetchone()[0]
        except Exception:
            x['pvog_queries_cached']=0
        if x['mapped_links']==0:
            x['hinweis']='JZuFi-Belege fehlen noch oder können nicht mit LeiKa-Schlüsseln verbunden werden.'
        return x
    finally:
        con.close()


def do_import(paths: list[str]) -> int:
    tax=AuthorityTaxonomy(DEFAULT_TAXONOMY)
    if not DB.exists():
        raise RuntimeError('Vorhandene FIM-DB fehlt. Erst FIM-Import starten bzw. AUTHORITY_MATCHER_HOME setzen.')
    files=[Path(x).expanduser().resolve() for x in paths]
    for f in files:
        if not f.is_file():
            raise FileNotFoundError(f)
    data=import_files(DB,tax,files)
    print(json.dumps(data,ensure_ascii=False,indent=2))
    print('JZuFi gespeichert. Nächster Schritt: authority-matcher --reindex',file=sys.stderr)
    return 0


def do_fetch(args: list[str]) -> int:
    p=argparse.ArgumentParser(prog='authority-matcher jzufi-fetch')
    p.add_argument('--lbid',help='PVOG LB-ID, z.B. L100012.LB.9413106')
    p.add_argument('--leika',help='Amtlicher 14-stelliger LeiKa-Schlüssel')
    p.add_argument('--ars',help='12-stelliger ARS der ABRUFREGION (nicht Bürgerstandort)')
    p.add_argument('--csv',type=Path,help='CSV-Datei mit Spalten lbid,ars')
    p.add_argument('--delay',type=float,default=.6)
    opt=p.parse_args(args)
    keys = {}
    if not DB.exists():
        raise FileNotFoundError(DB)
    tax=AuthorityTaxonomy(DEFAULT_TAXONOMY)
    if opt.leika and opt.ars:
        result=fetch_online_key(DB,tax,opt.leika,regions=(opt.ars,),force=True,delay=opt.delay)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        if not result['categories']:
            print('Keine belegte Kategorie in dieser Referenzregion; das ist kein Syntaxfehler. '
                  'Versuche weitere ARS über --reference-ars im Suchmodus.',file=sys.stderr)
        return 0 if result['categories'] else 2
    pairs=read_pairs(opt.csv) if opt.csv else ([(opt.lbid,opt.ars)] if opt.lbid and opt.ars else [])
    if not pairs:
        p.error('Bitte --leika und --ars, --lbid und --ars oder --csv angeben')
    result=get_jzufi(DB,tax,pairs,delay=opt.delay)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 1 if result['pairs_failed'] else 0


def get_index_docs(*, semantic: bool, force: bool, no_start_docker: bool, verbose: bool = False) -> dict:
    """Avoid repeating a 90k-document embedding pass on each CLI invocation."""
    if not no_start_docker:
        ensure_es(quiet=not verbose)
    client=es_client(ES_URL)
    if not client.ping():
        raise RuntimeError(f'Elasticsearch nicht erreichbar: {ES_URL}. Docker Desktop starten.')
    con=connect(DB)
    try:
        # Constant time-ish fingerprint based on data changes, not just count.
        row=con.execute('SELECT COUNT(*),MAX(imported_at) FROM records').fetchone()
    finally:
        con.close()
    # Query-time PVOG updates do not force a full re-embedding at next launch.
    settings={'fim_count':row[0], 'fim_last_modified':row[1],
              'index':INDEX,'semantic':semantic,'schema':5}
    old={}
    if MANIFEST.exists():
        try:
            old=json.loads(MANIFEST.read_text(encoding='utf-8'))
        except (OSError,json.JSONDecodeError):
            pass
    if not force and old==settings and client.indices.exists(index=INDEX):
        return {'already_indexed':True, **settings}
    docs,metrics=build_fim_documents(DB)
    if verbose:
        print(f'Indexaufbau: {len(docs)} FIM-Leistungen, davon {metrics["fim_with_jzufi_category"]} mit JZuFi-Zuordnung',
              file=sys.stderr)
    write_export(docs,EXPORT)
    result=index_elastic(docs,url=ES_URL,index_name=INDEX,embeddings=semantic,model_name=MODEL)
    MANIFEST.parent.mkdir(parents=True,exist_ok=True)
    temp=MANIFEST.with_suffix('.tmp')
    temp.write_text(json.dumps(settings),encoding='utf-8')
    temp.replace(MANIFEST)
    return {**result, **metrics}


def main(argv: list[str]|None=None) -> int:
    argv=list(argv if argv is not None else sys.argv[1:])
    try:
        if argv and argv[0] in ('jzufi-import','jzufi-fetch'):
            sub=argv.pop(0)
            if sub=='jzufi-import':
                if not argv:
                    raise ValueError('Datei(en) angeben, z.B. authority-matcher jzufi-import /pfad/zu/jzufi.jsonl')
                return do_import(argv)
            return do_fetch(argv)
        args=parser().parse_args(argv)
        if args.status:
            print(json.dumps(status(),ensure_ascii=False,indent=2))
            return 0
        if not DB.exists():
            raise FileNotFoundError(f'FIM-SQLite fehlt: {DB}. Vorhandenen Download bitte nicht löschen.')
        sem=not args.no_semantic
        if args.details:
            print('Prüfe Elasticsearch-Index und amtliche JZuFi-Verknüpfungen ...',file=sys.stderr)
        get_index_docs(semantic=sem,force=args.reindex,no_start_docker=args.no_start_docker,verbose=args.details)
        tax=AuthorityTaxonomy(DEFAULT_TAXONOMY)
        regions=reference_regions(args.reference_ars)
        if not (1 <= args.live_top <= 10):
            raise ValueError('--live-top muss zwischen 1 und 10 liegen')
        def ask(q: str):
            trace=[]
            enricher=None if args.no_live else make_enricher(
                DB,tax,regions=regions,max_keys=args.live_top,trace=trace)
            answer=match_authority(q,backend='elasticsearch',es_url=ES_URL,
                                   es_index=INDEX,semantic=sem,embedding_model=MODEL,
                                   enrich=enricher)
            if args.details and trace:
                answer['pvog_live']=[{'leika':x['leika'], 'regions':x['regions'],
                                     'categories':x['categories']} for x in trace]
            show(answer,tax,args.json,details=args.details)
            if args.details and not args.json and not answer.get('behoerdenkategorie') and trace:
                print('PVOG: keine eindeutige Behördenkategorie belegt. '
                      'Details mit --json; weitere Referenzgebiete mit --reference-ars.',file=sys.stderr)
        if args.query:
            ask(' '.join(args.query))
        else:
            print('Behörden-Matcher · Text eingeben, exit beendet')
            while True:
                try:
                    line=input('Anliegen> ').strip()
                except (EOFError,KeyboardInterrupt):
                    print()
                    break
                if line.casefold() in ('exit','quit','ende'):
                    break
                if line:
                    ask(line)
        return 0
    except (Exception) as exc:
        print('Fehler: '+str(exc),file=sys.stderr)
        return 1

if __name__=='__main__':
    raise SystemExit(main())
