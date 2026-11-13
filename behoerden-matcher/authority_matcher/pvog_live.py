"""Public PVOG lookup for a LeiKa key; no XZuFi export and no citizen location.

Only official associations are converted to categories. The ARS arguments are
*reference locations for evidence collection*, not the end user's address.
The PVOG REST API is public; its location-scoped search is not an exhaustive
nationwide data dump. All result objects used are saved for auditing.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from .catalog import AuthorityTaxonomy
from .jzufi import connect, evidence_by_key, import_payloads, role_code, service_keys
from .jzufi_fetch import BASE, fetch_one, resolve_leika

# A deliberately small, varied reference sample. Not a representative survey.
DEFAULT_REFERENCE_ARS = ('110000000000', '020000000000', '073150000000')


def reference_regions(text: str | None = None) -> tuple[str, ...]:
    text = text if text is not None else os.environ.get('AUTHORITY_MATCHER_REFERENCE_ARS')
    regions = tuple(dict.fromkeys(x.strip() for x in text.split(','))) if text else DEFAULT_REFERENCE_ARS
    if not regions or any(not re.fullmatch(r'\d{12}', a) for a in regions):
        raise ValueError('Referenz-ARS: kommaseparierte Liste von 12-stelligen Schlüsseln erforderlich')
    return regions


def initialize(db: Path) -> None:
    con=connect(db)
    try:
        con.execute('''CREATE TABLE IF NOT EXISTS pvog_live_attempts (
          leika TEXT NOT NULL, ars TEXT NOT NULL, checked_at TEXT NOT NULL,
          outcome TEXT NOT NULL, details TEXT NOT NULL, PRIMARY KEY(leika,ars))''')
        # Old versions stored empty organisation identifiers as if they were
        # real JZuFi links. These cannot be used to prove responsibility.
        con.execute("DELETE FROM jzufi_links WHERE TRIM(org_id) = '' OR TRIM(lb_id) = ''")
        con.commit()
    finally:
        con.close()


def _recent_attempt(db: Path, key: str, ars: str) -> dict | None:
    con=connect(db)
    try:
        row=con.execute('SELECT checked_at,outcome,details FROM pvog_live_attempts WHERE leika=? AND ars=?',(key,ars)).fetchone()
    finally:
        con.close()
    if not row:
        return None
    # v3 mistakenly marked a request 'success' when it had relations but
    # no organisation names. Invalidate those old caches on upgrade.
    if row[1] == 'success':
        try:
            counts = json.loads(row[2]).get('counts', {})
            if counts.get('jzufi_relations', 0) and not (
                counts.get('orgs', 0) or counts.get('titles_links', 0)):
                return None
        except (ValueError, TypeError, AttributeError):
            pass
    checked=datetime.fromisoformat(row[0])
    if checked.tzinfo is None:
        checked=checked.replace(tzinfo=timezone.utc)
    # Partial and error replies must be retried, rather than hiding code fixes
    # behind a time-to-live. Empty *searches* are cached for one day.
    if row[1] in ('error','partial'):
        return None
    ttl=timedelta(hours=24) if row[1]=='empty' else timedelta(days=7)
    if datetime.now(timezone.utc)-checked >= ttl:
        return None
    return {'ars':ars,'outcome':row[1],'details':row[2],'cached':True}


def _record_attempt(db: Path, key: str, ars: str, outcome: str, details: str) -> None:
    con=connect(db)
    try:
        con.execute('''INSERT INTO pvog_live_attempts VALUES(?,?,?,?,?)
          ON CONFLICT(leika,ars) DO UPDATE SET checked_at=excluded.checked_at,
            outcome=excluded.outcome,details=excluded.details''',
            (key,ars,datetime.now(timezone.utc).isoformat(),outcome,details[:4000]))
        con.commit()
    finally:
        con.close()


def _titles(payload: object) -> list[dict]:
    """The documented response is an array; accept a `content` wrapper too."""
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x,dict)]
    if isinstance(payload,dict):
        for key in ('content','items','organisationseinheiten','organisationUnits',
                    'organisations','data','results'):
            if isinstance(payload.get(key),list):
                return _titles(payload[key])
    return []


def _accepted_role(obj: dict) -> str | None:
    role = obj.get('role',obj.get('rolle'))
    if role is None:
        # FITKO documents that missing role may be returned. It is not proof
        # of a particular responsible agency; do not promote it automatically.
        return None
    code = role_code({'rolle':role})
    return code if code in ('01','02') else None


def fetch_online_key(db: Path, taxonomy: AuthorityTaxonomy, leika: str,
                     *, regions: tuple[str,...] | None = None,
                     force: bool = False, delay: float = 0.4,
                     api_base: str = BASE,
                     session=None) -> dict:
    """Fetch/caches official LeiKa->LB->OE links for a few reference regions.

    For robustness, uses the documented `organisationunits/titles` as a
    supplementary source of official OE roles/names. JZuFi details and
    relations are also queried; failures of one endpoint do not erase valid
    results from another. Never infer a relation from a service's title.
    """
    import requests
    if not re.fullmatch(r'\d{14}',leika):
        raise ValueError('LeiKa-Schlüssel muss 14-stellig sein')
    if delay < .2:
        raise ValueError('Mindestens 0,2 Sekunden Anfrageabstand')
    if not api_base.startswith('https://'):
        raise ValueError('PVOG muss per HTTPS abgerufen werden')
    regions=regions if regions is not None else reference_regions()
    if any(not re.fullmatch(r'\d{12}',x) for x in regions):
        raise ValueError('Referenz-ARS müssen 12-stellig sein')
    initialize(db)
    session=session or requests.Session()
    session.headers.update({'User-Agent':'authority-matcher-hackathon/0.3',
                            'Accept-Language':'de'})
    api_base=api_base.rstrip('/')
    diagnostics=[]
    for ars in regions:
        cached=None if force else _recent_attempt(db,leika,ars)
        if cached:
            diagnostics.append(cached)
            continue
        counts={'lbids':0,'jzufi_relations':0,'titles_links':0,'orgs':0}
        endpoint_errors=[]
        try:
            # Resolve LeiKa key to region-specific PVOG service IDs.
            ids=resolve_leika(leika,ars,api_base=api_base,session=session)
            counts['lbids']=len(ids)
            for lbid in ids[:40]:  # per-region safety bound
                # JZuFi service: the canonical bridge to 14-digit LeiKa keys.
                svc={'id':lbid,'leistungsschluessel':[leika], 'name':''}
                try:
                    time.sleep(delay)
                    raw=fetch_one(session, api_base+'/v1/servicedescriptions/'+quote(lbid,safe='')+'/jzufi-2-3',None)
                    if isinstance(raw,dict):
                        svc={'_type':'service', **raw, 'id':lbid}
                        svc['leistungsschluessel']=sorted(set(service_keys(svc)+[leika]))
                except Exception as exc:
                    endpoint_errors.append(f'service {lbid}: {str(exc)[:650]}')
                import_payloads(db,taxonomy,iter([{'_type':'service',**svc, 'id':lbid}]),source='pvog:live-jzufi-service')
                # JZuFi relations, including OE IDs, roles and areas.
                try:
                    time.sleep(delay)
                    rels=fetch_one(session, api_base+'/v1/relations/jzufi-2-3',{'lbids':lbid,'ars':ars})
                    stats=import_payloads(db,taxonomy,iter([rels]),source='pvog:live-jzufi-relations')
                    counts['jzufi_relations']+=stats['links']
                except Exception as exc:
                    endpoint_errors.append(f'relations {lbid}: {str(exc)[:650]}')
                # Resolve the OE IDs from the relations just stored. JZuFi
                # relations alone do not provide an OE name, so they cannot
                # produce a usable category without this lookup.
                con = connect(db)
                try:
                    oe_ids = [row[0] for row in con.execute(
                        "SELECT DISTINCT org_id FROM jzufi_links WHERE lb_id=? AND TRIM(org_id) <> ''",
                        (lbid,)).fetchall()]
                    already = {row[0] for row in con.execute(
                        'SELECT org_id FROM jzufi_orgs WHERE org_id IN (' +
                        ','.join('?' for _ in oe_ids) + ')', oe_ids).fetchall()} if oe_ids else set()
                finally:
                    con.close()
                for oeid in oe_ids[:40]:
                    # Only fetch IDs already returned by an official JZuFi
                    # relation; never invent an OE from the service title.
                    if oeid in already:
                        continue
                    if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', oeid):
                        endpoint_errors.append(f'organisation invalid ID {oeid[:80]}')
                        continue
                    try:
                        time.sleep(delay)
                        raw_org = fetch_one(
                            session, api_base+'/v1/organisationunits/'+quote(oeid,safe='')+'/jzufi-2-3', None)
                        if not isinstance(raw_org, dict):
                            raise ValueError('Unerwartete JZuFi-Organisationsantwort')
                        org_data = raw_org.get('organisationseinheit')
                        if not isinstance(org_data, dict):
                            org_data = raw_org
                        imported = import_payloads(db, taxonomy,
                            iter([{'_type':'org', **org_data, 'id':oeid}]),
                            source='pvog:live-jzufi-organisation')
                        counts['orgs'] += imported['organisations']
                        if imported['organisations'] == 0:
                            endpoint_errors.append(f'organisation {oeid}: kein amtlicher Name extrahiert')
                    except Exception as exc:
                        endpoint_errors.append(f'organisation {oeid}: {str(exc)[:180]}')
                # Authoritative *name+role* endpoint. Useful if the JZuFi
                # relation envelope differs from the local parser's schema.
                try:
                    # A fetched OE name is not sufficient when its JZuFi
                    # relation has no responsible role. The title endpoint
                    # can still provide a verified role for the same LB.
                    con = connect(db)
                    try:
                        lb_has_mapping = any(
                            ev.get('lb_id') == lbid
                            for ev in evidence_by_key(con).get(leika, []))
                    finally:
                        con.close()
                    if lb_has_mapping:
                        continue
                    time.sleep(delay)
                    titles=_titles(fetch_one(session, api_base+'/v2/organisationunits/titles',
                                           {'lbId':lbid,'ars':ars,
                                            'validDate':datetime.now(timezone.utc).date().isoformat()}))
                    for org in titles:
                        oeid=str(org.get('id') or '').strip()
                        name=org.get('title') or org.get('name') or ''
                        code=_accepted_role(org)
                        if not oeid or not name or not code:
                            continue
                        # Keep criteria in raw relation for later audit.
                        p={'organisationseinheiten':[{'id':oeid,'name':name}],
                           'zustaendigkeiten':[{'leistungID':lbid,
                               'organisationseinheitID':oeid,'rolle':{'code':code},
                               'gebietID':ars,'criteria':org.get('criteria'),
                               'official_source':'v2/organisationunits/titles'}]}
                        imp=import_payloads(db,taxonomy,iter([p]),source='pvog:live-titles')
                        counts['titles_links']+=imp['links']
                        counts['orgs']+=imp['organisations']
                except Exception as exc:
                    endpoint_errors.append(f'titles {lbid}: {str(exc)[:650]}')
            con = connect(db)
            try:
                # Do not mistake a different region's result for success of
                # the current request. All categories are still returned at
                # the end of this function as consolidated key evidence.
                has_evidence = any(
                    ev.get('lb_id') in ids
                    for ev in evidence_by_key(con).get(leika, []))
            finally:
                con.close()
            if not ids:
                outcome='empty'
            elif has_evidence:
                outcome='success'
            elif counts['jzufi_relations'] or counts['titles_links']:
                outcome='partial'  # relations exist, but no categorized OE name
            else:
                outcome='error' if endpoint_errors else 'empty'
            details=json.dumps({'counts':counts,'errors':endpoint_errors[:6]},ensure_ascii=False)
            _record_attempt(db,leika,ars,outcome,details)
            diagnostics.append({'ars':ars,'outcome':outcome,'details':details,'cached':False})
        except Exception as exc:
            details=str(exc)[:900]
            _record_attempt(db,leika,ars,'error',details)
            diagnostics.append({'ars':ars,'outcome':'error','details':details,'cached':False})
    con=connect(db)
    try:
        evidence=evidence_by_key(con).get(leika,[])
    finally:
        con.close()
    return {'leika':leika,'regions':diagnostics, 'evidence':evidence,
            'categories':sorted({x['category'] for x in evidence}),
            'found_official_mapping':bool(evidence)}


def make_enricher(db: Path, taxonomy: AuthorityTaxonomy, *, regions: tuple[str,...],
                  max_keys: int = 3, trace: list[dict] | None = None):
    """Called once per Elasticsearch query, never sends citizen text to PVOG."""
    def enrich(rows: list[tuple[dict,float]]) -> list[tuple[dict,float]]:
        keys=[]
        for doc,_ in rows:
            key=doc.get('leistungsschluessel')
            if isinstance(key,str) and re.fullmatch(r'\d{14}',key) and key not in keys:
                keys.append(key)
            if len(keys)>=max_keys:
                break
        con=connect(db)
        try:
            evidence=evidence_by_key(con)
        finally:
            con.close()
        for key in keys:
            if evidence.get(key):
                continue
            report=fetch_online_key(db,taxonomy,key,regions=regions)
            if trace is not None:
                trace.append(report)
            evidence[key]=report['evidence']
        enriched=[]
        for doc,score in rows:
            doc=dict(doc)
            items=evidence.get(doc.get('leistungsschluessel'),[])
            if items:
                doc['behoerdenkategorien']=sorted({e['category'] for e in items})
                doc['mapping_status']='jzufi_live_belegt' if len(doc['behoerdenkategorien'])==1 else 'jzufi_live_mehrdeutig'
                doc['zuordnung_belege']=items
            enriched.append((doc,score))
        return enriched
    return enrich
