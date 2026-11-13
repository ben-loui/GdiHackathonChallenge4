"""Persistent, auditable JZuFi evidence graph: Leistung -> OE -> taxon.

The public search API is request-scoped, NOT a nationwide dump. Importing a
full JSON/JZuFi data export is the preferred reproducible bulk data path.
Only *explicit* administrative relationships are used; no classification of
services from their names and no fabricated default mappings.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile
import sqlite3
from pathlib import Path
from typing import Iterator

from .catalog import AuthorityTaxonomy, clean

SQL = """
CREATE TABLE IF NOT EXISTS jzufi_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jzufi_services(
  lb_id TEXT PRIMARY KEY, keys_json TEXT NOT NULL, title TEXT NOT NULL,
  raw_json TEXT NOT NULL, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jzufi_orgs(
  org_id TEXT PRIMARY KEY, name TEXT NOT NULL, categories TEXT NOT NULL,
  raw_json TEXT NOT NULL, source TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS jzufi_links(
  link_id TEXT PRIMARY KEY, lb_id TEXT NOT NULL, org_id TEXT NOT NULL,
  role TEXT NOT NULL, ars TEXT NOT NULL, raw_json TEXT NOT NULL, source TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS jzufi_links_lb ON jzufi_links(lb_id);
CREATE INDEX IF NOT EXISTS jzufi_links_oe ON jzufi_links(org_id);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path, timeout=15)
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=10000")
    con.executescript(SQL)
    return con


def values(v: object) -> list[object]:
    if v is None:
        return []
    return v if isinstance(v, list) else [v]


def identifier(v: object) -> str:
    """Only explicit identifiers, never arbitrary descriptive text."""
    if isinstance(v, (str, int)):
        return str(v).strip()
    if isinstance(v, dict):
        agency = v.get('schemeAgencyID') or v.get('@schemeAgencyID')
        if agency and any(k in v for k in ('value','text','#text')):
            short = identifier(v.get('value') or v.get('text') or v.get('#text'))
            return f'{agency}:{short}' if short else ''
        for k in ('value', 'wert', 'id', 'identifier', 'identifikator', '#text', 'text', '_text'):
            if k in v:
                result = identifier(v[k])
                if result:
                    return result
    return ''


def pvog_id(value: object, kind: str) -> str:
    """Normalize XZuFi schemeAgencyID + local ID to a PVOG LB/OE ID.

    JZuFi identifiers are often {"schemeAgencyID":"L100039", "value":"8966482"},
    while PVOG lookup IDs are L100039.LB.8966482.  Using the generic
    identifier() produced L100039:8966482, so joins silently failed.
    Only this *typed* helper may add LB/OE; generic identifiers must not.
    """
    if kind not in ('LB', 'OE'):
        raise ValueError('Unexpected PVOG object type')
    if isinstance(value, dict):
        agency = str(value.get('schemeAgencyID') or value.get('@schemeAgencyID') or '').strip()
        raw = value.get('value', value.get('#text', value.get('text', value.get('wert'))))
        short = identifier(raw)
        if agency and short:
            if short.startswith(agency + '.' + kind + '.'):
                return short
            if re.fullmatch(r'[A-Za-z][A-Za-z0-9]{4,12}', agency):
                return f'{agency}.{kind}.{short}'
    raw_id = identifier(value)
    if re.fullmatch(r'[A-Za-z][A-Za-z0-9]{4,12}:[^:]+', raw_id):
        agency, short = raw_id.split(':', 1)
        return f'{agency}.{kind}.{short}'
    return raw_id


def find(obj: dict, *names: str) -> object:
    for n in names:
        if n in obj:
            return obj[n]
    return None


def service_keys(obj: dict) -> list[str]:
    raw = find(obj, 'leistungsschluessel', 'leistungsschlüssel',
               'leistungsschluessel', 'leistungsschluesselListe',
               'leistungsschluesselListe', 'leikaSchluessel', 'leika_key')
    keys: list[str] = []
    for item in values(raw):
        s = identifier(item)
        if re.fullmatch(r'\d{14}', s) and s not in keys:
            keys.append(s)
    # FIM detail objects sometimes carry associations only in steckbriefe.
    for entry in values(obj.get('steckbriefe')):
        s = identifier(entry[0]) if isinstance(entry, list) and entry else ''
        if re.fullmatch(r'\d{14}', s) and s not in keys:
            keys.append(s)
    for nested_name in ('leistung','leistungsbeschreibung','daten','service'):
        nested=obj.get(nested_name)
        if isinstance(nested,dict):
            for key in service_keys(nested):
                if key not in keys: keys.append(key)
    return keys


def official_name(obj: dict) -> str:
    # An OE's own name, not contact persons, publisher or another linked agency.
    for name in ('name', 'bezeichnung', 'kurzbezeichnung', 'titel',
                 'organisationsname', 'organisationseinheitsname'):
        v = obj.get(name)
        if isinstance(v, str):
            if clean(v):
                return clean(v)
        if isinstance(v, list):
            for item in v:
                n = (clean(item) or official_name(item)) if isinstance(item, dict) else clean(item)
                if n:
                    return n
        if isinstance(v, dict):
            for field in ('text', 'value', 'wert', 'name', 'de', 'inhalt'):
                if clean(v.get(field)):
                    return clean(v[field])
    return ''


def role_code(obj: dict) -> str:
    role = find(obj, 'rolle', 'role', 'zustaendigkeitsrolle')
    if role is None:
        return 'unspezifiziert'
    if isinstance(role, list):
        codes = [role_code({'rolle': entry}) for entry in role]
        # XZuFi 2.3.1 permits multiple roles. One responsible role is enough.
        if '01' in codes:
            return '01'
        if '02' in codes:
            return '02'
        return '03' if '03' in codes else 'unbekannt'
    if isinstance(role, dict):
        for field in ('code', 'value', 'wert'):
            if field in role:
                return str(role[field]).strip()
        name = role.get('name', '')
        if isinstance(name, str) and 'zuständig' in name.casefold():
            return '02'
        return 'unbekannt'
    return str(role).strip()


def relation_data(obj: dict) -> list[dict]:
    """Recognize explicit XZuFi Zuständigkeit links; never guess via title."""
    content = obj.get('zustaendigkeit') or obj.get('zuständigkeit')
    if content and isinstance(content, dict):
        base = content
    else:
        base = obj
    lbids = [pvog_id(x, 'LB') for x in values(find(base, 'leistungID','leistungId','leistungs_id', 'lb_id', 'lbId', 'lbids'))]
    lbids = [s for s in lbids if s]
    # A relation explicitly associated with an OE (XZuFi OE wrapper or transfer).
    oe_candidates = values(find(base, 'organisationseinheitID', 'organisationseinheitId',
                                'organisationseinheitsID', 'organisationseinheitsId',
                                'org_id', 'orgId', 'organisationunitId', 'organisationseinheit'))
    oe = [pvog_id(x, 'OE') for x in oe_candidates if identifier(x)]
    if not oe:
        oe = [pvog_id(x, 'OE') for x in values(find(obj, 'organisationseinheitID', 'organisationseinheitId',
                                                'org_id','orgId', 'organisationunitId')) if identifier(x)]
    if not oe and isinstance(obj.get('_org_id'), str) and obj['_org_id'].strip():
        oe = [pvog_id(obj['_org_id'], 'OE')]
    # Incomplete transfer objects are not evidence that any real agency is
    # responsible. Earlier versions accidentally stored org_id=''.
    oe = [name for name in oe if name.strip()]
    ars = [identifier(x.get('value') or x.get('wert') or x.get('#text')) if isinstance(x, dict)
           and (x.get('value') or x.get('wert') or x.get('#text')) else identifier(x)
           for x in values(find(base,'gebietID', 'gebietId', 'ars', 'region'))]
    ars = [a for a in ars if a]
    role = role_code(base)
    if role not in ('01','02','unspezifiziert'):
        return []
    return [{'lb_id': l, 'org_id': o, 'role': role, 'ars': ars}
            for l in lbids for o in oe]


def classify(obj: dict) -> str | None:
    kind = str(obj.get('_type', obj.get('type', ''))).lower()
    if kind in ('service', 'leistung', 'leistungsbeschreibung'):
        return 'service'
    if kind in ('organisationseinheit', 'organisation', 'org', 'organization'):
        return 'org'
    if kind in ('relation', 'zustaendigkeit', 'zuständigkeit'):
        return 'relation'
    # Directly identifiable XZuFi objects
    if 'zustaendigkeit' in obj and ('name' in obj or 'bezeichnung' in obj or 'organisationseinheit' in obj):
        return 'org'
    if 'leistungID' in obj and ('organisationseinheitID' in obj or 'org_id' in obj):
        return 'relation'
    if 'organisationseinheitID' in obj and 'leistungID' in obj:
        return 'relation'
    if 'leistungsschluessel' in obj or 'leistungsschlüssel' in obj or 'steckbriefe' in obj:
        return 'service'
    if ('name' in obj or 'bezeichnung' in obj) and ('id' in obj or 'organisationseinheitId' in obj):
        return 'org'
    return None


def objects(blob: object) -> Iterator[dict]:
    """Handle a single object, a list, and explicitly named transfer collections."""
    if isinstance(blob, list):
        for item in blob:
            yield from objects(item)
    elif isinstance(blob, dict):
        if isinstance(blob.get('zustaendigkeit'), list) and not official_name(blob):
            # Some PVOG transfer envelopes group several Zuständigkeiten
            # under one organisationseinheit reference, without OE names.
            parent_id = pvog_id(find(blob, 'organisationseinheitID', 'organisationseinheitId',
                                     'organisationseinheit', 'org_id', 'id'), 'OE')
            for relation in blob['zustaendigkeit']:
                if isinstance(relation,dict):
                    yield {'_type':'relation', '_org_id':parent_id, **relation}
            return
        if classify(blob):
            yield blob
            return
        found = False
        for key, typ in (('leistungen','service'), ('leistungsbeschreibungen','service'),
                         ('servicedescriptions','service'), ('organisationseinheiten','org'),
                         ('organisationunits','org'), ('zustaendigkeiten','relation'),
                         ('zuständigkeiten','relation'), ('relations','relation'),
                         ('zustaendigkeitTransferObjekte','relation')):
            if key in blob:
                found = True
                for child in values(blob[key]):
                    if isinstance(child, dict):
                        yield {'_type': typ, **child}
        if not found:
            for key in ('items','data','results','content','payload','leistung',
                        'organisationseinheit','leistungsbeschreibung', 'zustaendigkeitTransferObjekt'):
                if key in blob:
                    yield from objects(blob[key])
                    break


def _tag(x: str) -> str:
    return x.rsplit('}',1)[-1]


def _xml_node(el: ET.Element) -> object:
    """Limited XZuFi XML -> JZuFi-style objects, namespace agnostic."""
    children=list(el)
    if not children:
        value=(el.text or '').strip()
        return {'value':value,**el.attrib} if el.attrib else value
    obj={}
    for c in children:
        name=_tag(c.tag)
        val=_xml_node(c)
        if name in obj:
            if not isinstance(obj[name],list):
                obj[name]=[obj[name]]
            obj[name].append(val)
        else:
            obj[name]=val
    return obj


def iterable_xml(path: Path) -> Iterator[object]:
    # Prefer direct XML transfer files; each top-level Leistung/OE is imported.
    root=ET.parse(path).getroot()
    def visit(el, parent=None):
        tag=_tag(el.tag).lower()
        if tag in ('leistung','organisationseinheit','zustaendigkeit'):
            kind={'leistung':'service','organisationseinheit':'org','zustaendigkeit':'relation'}[tag]
            if tag=='zustaendigkeit' and parent!='organisationseinheit':
                return
            if tag!='zustaendigkeit':
                obj=_xml_node(el)
                if isinstance(obj,dict):
                    yield {'_type':kind,**obj}
                return
        for child in el:
            yield from visit(child,tag)
    yield from visit(root)


def iterable_json(path: Path) -> Iterator[object]:
    if path.suffix.lower() == '.jsonl':
        with path.open(encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                if line.strip():
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ValueError(f'{path}:{i}: JSON ungültig: {exc}') from exc
    elif path.suffix.lower() == '.json':
        yield json.loads(path.read_text(encoding='utf-8'))
    elif path.suffix.lower() == '.xml':
        yield from iterable_xml(path)
    elif path.suffix.lower() == '.zip':
        with ZipFile(path) as z:
            for member in z.infolist():
                if member.is_dir() or not member.filename.lower().endswith(('.json','.jsonl','.xml')):
                    continue
                if member.file_size > 50_000_000:
                    raise ValueError(f'ZIP-Eintrag zu groß: {member.filename}')
                from tempfile import TemporaryDirectory
                with TemporaryDirectory() as directory:
                    target=Path(directory)/('payload'+Path(member.filename).suffix.lower())
                    target.write_bytes(z.read(member))
                    yield from iterable_json(target)
    else:
        raise ValueError('Unterstützt: .json, .jsonl, .xml, .zip (XZuFi/JZuFi)')


def import_payloads(db: Path, taxonomy: AuthorityTaxonomy, payloads: Iterator[object],
                    *, source: str) -> dict:
    con = connect(db)
    stats = {'services': 0, 'organisations': 0, 'links': 0, 'unrecognized': 0}
    try:
        for payload in payloads:
            saw = False
            for obj in objects(payload):
                saw = True
                typ = classify(obj)
                if typ == 'service':
                    item_id = pvog_id(find(obj,'id','leistungID','leistungId','lb_id','lbId'), 'LB')
                    # Need a *PVOG* id so that relations can join on it; raw LeiKa key alone insufficient.
                    if not item_id:
                        stats['unrecognized'] += 1
                        continue
                    keys = service_keys(obj)
                    con.execute('INSERT OR REPLACE INTO jzufi_services VALUES(?,?,?,?,?)',
                                (item_id,json.dumps(keys), clean(find(obj,'title','titel','bezeichnung')),
                                 json.dumps(obj,ensure_ascii=False),source))
                    stats['services'] += 1
                elif typ == 'org':
                    org_id = pvog_id(find(obj,'id','organisationseinheitID','organisationseinheitId','org_id'), 'OE')
                    name = official_name(obj)
                    if not org_id or not name:
                        stats['unrecognized'] += 1
                        continue
                    cats = taxonomy.categorize(name)
                    con.execute('INSERT OR REPLACE INTO jzufi_orgs VALUES(?,?,?,?,?)',
                                (org_id,name,json.dumps(cats),json.dumps(obj,ensure_ascii=False),source))
                    stats['organisations'] += 1
                    # In XZuFi 2.2, explicit Zuständigkeit can be nested in OE.
                    for rel in values(obj.get('zustaendigkeit')):
                        if isinstance(rel, dict):
                            add_rel(con, {'_org_id': org_id, **rel}, source, stats)
                elif typ == 'relation':
                    add_rel(con, obj, source, stats)
                else:
                    stats['unrecognized'] += 1
            if not saw:
                stats['unrecognized'] += 1
        con.execute("INSERT INTO jzufi_meta(key,value) VALUES('revision', '1') ON CONFLICT(key) DO UPDATE SET value=CAST(CAST(value AS INTEGER)+1 AS TEXT)")
        con.commit()
        return {**stats, **mapping_stats(con)}
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def add_rel(con: sqlite3.Connection, obj: dict, source: str, stats: dict) -> None:
    for rel in relation_data(obj):
        key = hashlib.sha256(json.dumps([rel['lb_id'],rel['org_id'],rel['role'],rel['ars']],
                                        ensure_ascii=False,sort_keys=True).encode()).hexdigest()
        con.execute('INSERT OR REPLACE INTO jzufi_links VALUES(?,?,?,?,?,?,?)',
                    (key,rel['lb_id'],rel['org_id'],rel['role'],json.dumps(rel['ars']),
                     json.dumps(obj,ensure_ascii=False),source))
        stats['links'] += 1


def mapping_stats(con: sqlite3.Connection) -> dict:
    stats = {}
    for table, name in (('jzufi_services','services_total'),('jzufi_orgs','organisations_total'),('jzufi_links','links_total')):
        stats[name] = con.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    stats['linked_to_service'] = con.execute('''SELECT COUNT(*) FROM jzufi_links l
            JOIN jzufi_services s ON l.lb_id=s.lb_id''').fetchone()[0]
    stats['mapped_links'] = con.execute('''SELECT COUNT(*) FROM jzufi_links l
        JOIN jzufi_services s ON l.lb_id=s.lb_id
        JOIN jzufi_orgs o ON o.org_id=l.org_id
        WHERE o.categories NOT IN ('[]','null') AND l.role IN ('01','02')''').fetchone()[0]
    return stats


def evidence_by_key(con: sqlite3.Connection) -> dict[str, list[dict]]:
    """Only exact LeiKa keys via a PVOG service -> org relation -> OE name."""
    result: dict[str,list[dict]] = {}
    cur = con.execute('''SELECT s.keys_json, l.lb_id,l.org_id,l.role,l.ars,o.name,o.categories,l.source
       FROM jzufi_links l
       JOIN jzufi_services s ON s.lb_id=l.lb_id
       JOIN jzufi_orgs o ON o.org_id=l.org_id
       WHERE o.categories NOT IN ('[]','null') AND l.role IN ('01','02')''')
    seen = set()
    for keys, lb, org, role, ars, name, categories, source in cur:
        for key in json.loads(keys):
            for category in json.loads(categories):
                distinct = (key,lb,org,category)
                if distinct in seen:
                    continue
                seen.add(distinct)
                result.setdefault(key,[]).append({
                    'category': category, 'organisation': name, 'org_id': org,
                    'lb_id': lb, 'rolle': role, 'gebiete': json.loads(ars),
                    'quelle': source})
    return result


def import_files(db: Path, taxonomy: AuthorityTaxonomy, paths: list[Path]) -> dict:
    combined = {'services':0, 'organisations':0,'links':0,'unrecognized':0}
    for path in paths:
        count = import_payloads(db,taxonomy,iterable_json(path),source=f'file:{path.name}')
        for k in combined:
            combined[k] += count[k]
    con = connect(db)
    try:
        return {**combined, **mapping_stats(con)}
    finally:
        con.close()
