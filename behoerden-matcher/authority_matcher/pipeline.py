"""Build provenance-carrying search documents from a *preexisting* FIM SQLite.
Does not mutate users' FIM tables or start additional FIM downloads.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

from .jzufi import connect, evidence_by_key, mapping_stats


def fim_key(doc: dict) -> str | None:
    key = doc.get('leistungsschluessel')
    if isinstance(key,str) and re.fullmatch(r'\d{14}',key):
        return key
    record_key = doc.get('fim_source_key',doc.get('id',''))
    if isinstance(record_key,str) and record_key.startswith('profile:'):
        key = record_key[8:]
        if re.fullmatch(r'\d{14}',key):
            return key
    return None


def build_fim_documents(db: Path) -> tuple[list[dict],dict]:
    if not db.exists():
        raise FileNotFoundError(f'FIM-Datenbank fehlt: {db}')
    con = connect(db)
    try:
        evidence = evidence_by_key(con)
        summary = mapping_stats(con)
        results=[]
        fim_count=0
        linked=0
        unmapped=0
        unknown_key=0
        for (raw,) in con.execute('SELECT document FROM records'):
            fim_count += 1
            doc=json.loads(raw)
            key=fim_key(doc)
            if not key:
                unknown_key += 1
            doc['leistungsschluessel'] = key
            ev = evidence.get(key,[]) if key else []
            cats = sorted({e['category'] for e in ev})
            # Never carry over weak/unproven label-derived mappings from old parser.
            doc['behoerdenkategorien'] = cats
            doc['mapping_status'] = ('jzufi_belegt' if len(cats)==1 else
                                     'jzufi_mehrdeutig' if len(cats)>1 else 'ohne_jzufi_zuordnung')
            doc['zuordnung_belege'] = ev[:75]  # keep evidence bounded per index document
            if cats: linked += 1
            else: unmapped += 1
            results.append(doc)
        if fim_count == 0:
            raise RuntimeError('FIM-Datenbank enthält keine records – bisheriger Download fehlt')
        return results, {'fim_records':fim_count,'fim_without_key':unknown_key,
                         'fim_with_jzufi_category':linked,'fim_without_jzufi_category':unmapped,
                         **summary}
    finally:
        con.close()


def write_export(documents: list[dict], output: Path) -> None:
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.jsonl.tmp')
    with temp.open('w',encoding='utf-8') as f:
        for d in documents:
            f.write(json.dumps(d,ensure_ascii=False)+'\n')
    temp.replace(output)
