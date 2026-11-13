"""Reviewed statutory transfers and official building authority directory."""
import csv,gzip,io,json,re
from collections import Counter,defaultdict
from html import unescape
from .catalog import resource
from .etl import digest
from .http import get
from .supplements import parent_snapshot,write_snapshot,base_record
from .tabular import xlsx_sheets
from shapely import union_all
from shapely.geometry import shape,mapping


def parents(directory,sid):
    path,m=parent_snapshot(directory,sid)
    with gzip.open(path/'records.jsonl.gz','rt',encoding='utf-8') as f:rows=[json.loads(line) for line in f]
    return rows,m


def import_by_wohngeld(s,directory,fetch=get):
    data=fetch(s['legal_basis']);text=unescape(re.sub('<[^>]+>',' ',data.decode('utf-8')))
    text=' '.join(text.split())
    if s['required_legal_clause'] not in text:raise ValueError('Wohngeld-Zuständigkeitsregel geändert; erneute Prüfung erforderlich')
    rows,pm=parents(directory,'by_kreis')
    if len(rows)!=96:raise ValueError('Bayerische Kreisbehördenliste verändert; fachliche Prüfung nötig')
    def records():
        for r in rows:
            props={'original_authority_record':r['properties'],'parent_source_key':r['source_key'],
                   'legal_basis':s['legal_basis'],'legal_reviewed_at':s['source_date'],
                   'responsibility_subject':'Wohngeld, Miet- oder Lastenzuschuss für Wohnraum innerhalb des Gebiets',
                   'name_scope':'Existing named institution acting as Wohngeldbehörde; no invented department name',
                   'geometry_completeness':'general_territorial_district','boundary_snapshot_sha256':pm['records_sha256']}
            yield base_record(s,r['source_key'],r['authority_name'],r['geometry'],props,evidence=s['legal_basis'],repaired=r['geometry_repaired'])
    return write_snapshot(s,directory,records(),{'parent_records_sha256':pm['records_sha256'],'statutory_assignment_reviewed':True},[('law',s['legal_basis'],data)])


def import_nw_bau(s,directory,fetch=get):
    data=fetch(s['download_url']);law=fetch(s['legal_basis']);citylaw=fetch(s['city_status_url'])
    text=' '.join(unescape(re.sub('<[^>]+>',' ',law.decode('utf-8'))).split())
    if s['required_legal_clause'] not in text:raise ValueError('Bauaufsichts-Zuständigkeitsregel geändert; erneute Prüfung erforderlich')
    sheets=xlsx_sheets(data);csvdata=resource(s['mapping_file']).read_bytes()
    if digest(csvdata)!=s['mapping_sha256']:raise ValueError('Geänderte NRW-Gebietszuordnung')
    assignment=list(csv.DictReader(io.StringIO(csvdata.decode())))
    towns,pm=parents(directory,'vg25_gem');districts,dm=parents(directory,'vg25_krs')
    towns=[r for r in towns if r['properties'].get('sn_l')=='05'];groups=defaultdict(list)
    for r in towns:groups[r['properties']['ags']].append(r)
    ds={r['properties']['ars'] for r in districts if r['properties'].get('sn_l')=='05'}
    rows_by_sheet={sh:dict(rows) for sh,rows in sheets.items()}
    mapped={(r['sheet'],int(r['row'])) for r in assignment}
    actual={(sh,n) for sh,rows in sheets.items() for n,r in rows if n>=14 and r.get('A') and r['A']!='Name der Kommune'}
    if mapped!=actual:raise ValueError('NRW-Verzeichniszeilen geändert; neue explizite Zuordnung erforderlich')
    citycsv=resource(s['city_status_file']).read_bytes()
    if digest(citycsv)!=s['city_status_sha256']:raise ValueError('Geänderte NRW-Städtestatus-Zuordnung')
    statusrows=list(csv.DictReader(io.StringIO(citycsv.decode())))
    plain=' '.join(unescape(re.sub('<[^>]+>',' ',citylaw.decode())).split())
    expected={(r['kind'],r['source_name']) for r in statusrows}
    observed=set()
    for typ in ['Große','Mittlere']:
        m=re.search('Die nachfolgend aufgezählten Gemeinden nehmen als '+typ+r' kreisangehörige Städte.*? wahr: (.*?)\. Link kopiert',plain)
        if not m:raise ValueError('Geänderte NRW-Städtestatus-Rechtsquelle')
        observed.update((typ,name) for name in m[1].split(', '))
    if observed!=expected:raise ValueError('Gesetzliche NRW-Städteliste geändert; erneute Zuordnungsprüfung nötig')
    own={r['region_key'] for r in assignment if r['sheet']=='Liste Städte'}
    if len(own)!=sum(r['sheet']=='Liste Städte' for r in assignment):raise ValueError('Doppelte Stadtbehörde')
    # Exclude current autonomous cities even when the older contact directory
    # omitted them. Their area must never fall back to a county by accident.
    excluded_own=own|{r['ags'] for r in statusrows}|{r['properties']['ags'] for r in towns if r['properties'].get('bem')=='kreisfrei'}
    covered=set();audit={'source_advertised_count':212,'actual_directory_rows':len(assignment),'source_file_date':'2024-07 (inside spreadsheet)','covered_municipalities':0}
    def records():
        for a in assignment:
            row=rows_by_sheet[a['sheet']][int(a['row'])]
            if row.get('A')!=a['organisation_name']:raise ValueError('Behördenname in NRW-Verzeichnis geändert')
            region=a['region_key']
            if a['sheet']=='Liste Städte':ags=[region]
            else:
                if region not in ds:raise ValueError('Amtlicher Kreis fehlt')
                ags=sorted(k for k in groups if k.startswith(region) and k not in excluded_own)
            if not ags or any(k not in groups for k in ags):raise ValueError('Fehlende oder leere belegte Bauaufsichtsfläche')
            if covered.intersection(ags):raise ValueError('Überlappende NRW-Gemeindezuordnungen')
            covered.update(ags);parts=[r for k in ags for r in groups[k]]
            name=row['A']+(' – '+' '.join(row['B'].split()) if row.get('B') else '')
            props={'directory_sheet':a['sheet'],'directory_row':int(a['row']),'original_directory_record':row,'gemeinde_ags':ags,
                   'responsibility_subject':'Allgemeine örtliche untere Bauaufsicht; Sonderbauten und besondere Verfahren gesondert prüfen',
                   'legal_basis':s['legal_basis'],'legal_reviewed_at':s['mapping_reviewed_at'],
                   'geometry_completeness':'general_territorial_district','boundary_snapshot_sha256':pm['records_sha256']}
            yield base_record(s,a['sheet']+'-'+a['row'],name,mapping(union_all([shape(r['geometry']) for r in parts])),props,evidence=row.get('I') or s['documentation'],repaired=any(r['geometry_repaired'] for r in parts))
        audit['covered_municipalities']=len(covered);audit['uncovered_ags']=sorted(set(groups)-covered)
        # Do not silently assign a missing directory city to its county. The
        # delivered 2024 file has fewer rows than advertised in portal metadata.
        audit['note']='Missing current autonomous cities stay uncovered, never assigned to counties. Directory metadata and actual row counts differ.'
    return write_snapshot(s,directory,records(),{'assignment_audit':audit,'mapping_sha256':digest(csvdata),'parent_records_sha256':pm['records_sha256']},[('directory',s['download_url'],data),('legal_basis',s['legal_basis'],law),('city_status',s['city_status_url'],citylaw)])
