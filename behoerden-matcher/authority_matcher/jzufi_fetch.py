"""Explicit public PVOG JZuFi fetching for known (LB-ID, ARS) pairs.

This is a *sampling/targeted* interface, not a complete nationwide export.
No user location is used during matching.
"""
from __future__ import annotations

import csv
import json
import os
import random
import time
import re
from pathlib import Path
from urllib.parse import quote

from .catalog import AuthorityTaxonomy
from .jzufi import import_payloads, identifier, relation_data

BASE = 'https://pvog.fitko.net/suchdienst/api'


def fetch_one(session, url: str, params: dict | None, *, retries=4) -> object:
    import requests
    last = None
    for attempt in range(retries):
        try:
            response = session.get(url, params=params, timeout=(8, 45),
                                   headers={'Accept':'application/json', 'Accept-Language':'de'})
            if response.status_code in (429,500,502,503,504):
                last = f'{response.status_code}: {response.text[:160]}'
                time.sleep(min(15, 1.5 * 2**attempt + random.random()))
                continue
            # Validation errors are not transient. Include the response body,
            # which usually explains invalid parameter combinations.
            if 400 <= response.status_code < 500 and response.status_code != 429:
                raise RuntimeError(
                    f'PVOG HTTP {response.status_code} ({response.url}): '
                    f'{response.text[:500]}')
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as exc:
            last = str(exc)
            if attempt < retries-1:
                time.sleep(min(15,1.5 * 2**attempt))
    raise RuntimeError(f'PVOG antwortet nicht stabil ({url}): {last}')


def get_jzufi(db: Path, taxonomy: AuthorityTaxonomy, pairs: list[tuple[str,str]], *,
               delay: float = 0.35, api_base: str = BASE,
               forced_leika: dict[str,str] | None = None) -> dict:
    """Fetch confirmed PVOG relations by LB ID and ARS; follow known OE IDs."""
    import requests
    if delay < .2:
        raise ValueError('Mindestens 0,2 s Anfrageabstand zum öffentlichen PVOG')
    session = requests.Session()
    session.headers['User-Agent'] = 'authority-matcher-hackathon/0.2 (offline-JZuFi-enrichment)'
    api_base = api_base.rstrip('/')
    if not api_base.startswith('https://'):
        raise ValueError('JZuFi-API muss HTTPS nutzen')
    stats = {'pairs_attempted':0, 'pairs_successful':0, 'pairs_failed':[], 'orgs_fetched':0}
    org_cache = set()
    forced_leika = forced_leika or {}
    for lbid, ars in pairs:
        if not lbid or not ars or not ars.isdigit() or len(ars) != 12:
            stats['pairs_failed'].append({'lbid':lbid,'ars':ars,'error':'LB-ID oder 12-stelliger ARS ungültig'})
            continue
        stats['pairs_attempted'] += 1
        try:
            service_url = api_base+'/v1/servicedescriptions/'+quote(lbid,safe='')+'/jzufi-2-3'
            svc = fetch_one(session,service_url,None)
            time.sleep(delay)
            relations = fetch_one(session,api_base+'/v1/relations/jzufi-2-3',{'lbids':lbid,'ars':ars})
            # The public response is a list of relation transfer objects.
            # Preserve a direct association of each known LB/ARS with the result.
            if not isinstance(relations, (list,dict)):
                raise RuntimeError('Unerwartete Antwortstruktur für relations')
            service_data = dict(svc) if isinstance(svc,dict) else {}
            if 'leistung' in service_data and isinstance(service_data['leistung'],dict):
                service_data = service_data['leistung']
            key = forced_leika.get(lbid)
            if key and not any(k in service_data for k in ('leistungsschluessel','leistungsschlüssel')):
                service_data['leistungsschluessel'] = [key]
            import_payloads(db,taxonomy,iter([{'_type':'service',**service_data, 'id':lbid}]),
                            source='pvog:jzufi-service')
            import_payloads(db,taxonomy,iter([{'relations':relations if isinstance(relations,list) else [relations]}]),
                            source='pvog:jzufi-relations')
            org_ids = set()
            candidates = relations if isinstance(relations,list) else [relations]
            for rel in candidates:
                if isinstance(rel,dict):
                    for item in relation_data(rel):
                        if item['lb_id'] == lbid:
                            org_ids.add(item['org_id'])
            for org in sorted(org_ids - org_cache):
                time.sleep(delay)
                try:
                    raw = fetch_one(session, api_base+'/v1/organisationunits/'+quote(org,safe='')+'/jzufi-2-3',None)
                    if isinstance(raw,dict):
                        if isinstance(raw.get('organisationseinheit'),dict):
                            raw = raw['organisationseinheit']
                        import_payloads(db,taxonomy,iter([{'_type':'org',**raw,'id':org}]),source='pvog:jzufi-organisation')
                        stats['orgs_fetched'] += 1
                        org_cache.add(org)
                except Exception as exc:
                    stats['pairs_failed'].append({'lbid':lbid,'ars':ars,'org':org,'error':str(exc)[:240]})
            stats['pairs_successful'] += 1
        except Exception as exc:
            stats['pairs_failed'].append({'lbid':lbid,'ars':ars,'error':str(exc)[:240]})
        time.sleep(delay)
    return stats


def read_pairs(csv_path: Path) -> list[tuple[str,str]]:
    with csv_path.open(newline='',encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or not {'lbid','ars'}.issubset(set(reader.fieldnames)):
            raise ValueError('CSV braucht Spalten lbid,ars (z.B. L100012.LB.9413106,073150000000)')
        return [(r['lbid'].strip(),r['ars'].strip()) for r in reader]


def resolve_leika(leika: str, ars: str, *, delay: float = .6, api_base: str = BASE, session=None) -> list[str]:
    """Use PVOG's official LeiKa-key lookup to get request-scoped LB IDs.

    A regional request is required by the PUBLIC Search API. This does not
    ask for a citizen's location or make the query phase location-dependent.
    """
    import requests
    if not re.fullmatch(r'\d{14}',leika) or not re.fullmatch(r'\d{12}',ars):
        raise ValueError('LeiKa-Schlüssel muss 14- und ARS 12-stellig sein')
    session=session or requests.Session()
    from datetime import date
    response=fetch_one(session, api_base.rstrip('/')+'/v3/servicedescriptions/leikaid',
                       {'leikaIds':leika, 'ars':ars, 'useArsHierarchy':'true',
                        'withOrgIds':'true', 'size':100, 'page':0, 'validDate':date.today().isoformat()})
    found=set()
    def visit(obj):
        if isinstance(obj,list):
            for item in obj: visit(item)
        elif isinstance(obj,dict):
            for k,v in obj.items():
                if k in ('id','lbId','lbid') and isinstance(v,str) and re.fullmatch(r'L[^.]+\.LB\..+',v):
                    found.add(v)
                elif isinstance(v,(list,dict)):
                    visit(v)
    visit(response)
    return sorted(found)
