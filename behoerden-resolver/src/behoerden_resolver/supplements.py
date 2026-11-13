"""Explicit non-WFS assignment imports; no nearest-office or county guesses."""
import csv
import gzip
import io
import json
import os
import re
import shutil
import tempfile
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET
from shapely import union_all
from shapely.geometry import mapping, shape
from .catalog import resource, source
from .etl import digest, latest_snapshots, now, read_manifest
from .http import get
from .wfs import GML, gml_geometry, validated_geometry


def parent_snapshot(directory, source_id):
    matches = [p for p in latest_snapshots(directory) if read_manifest(p)["source"]["id"]==source_id]
    if not matches:
        raise ValueError(f"Zuerst {source_id} vollständig abrufen")
    path=matches[0]; manifest=read_manifest(path)
    if manifest["source"] != source(source_id):
        raise ValueError(f"Geänderte Quellkonfiguration für {source_id}; erneut abrufen")
    return path,manifest


def write_snapshot(s, directory, records, metadata, raw=()):
    directory=Path(directory);directory.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='.'+s['id']+'.',suffix='.tmp',dir=directory))
    counts=Counter();requests=[]
    try:
        for label,url,data in raw:
            (work/'raw').mkdir(exist_ok=True)
            path=work/'raw'/(label+'.gz')
            with gzip.open(path,'wb') as f:f.write(data)
            requests.append({'path':str(path.relative_to(work)),'request_url':url,'retrieved_at':now(),'response_sha256':digest(data),'bytes':len(data)})
        with gzip.open(work/'records.jsonl.gz','wt',encoding='utf-8') as f:
            for r in records:
                if r['source_id']!=s['id']:raise ValueError('Falsche Quelle im Ergänzungsimport')
                counts[r['category']]+=1
                f.write(json.dumps(r,ensure_ascii=False,separators=(',',':'))+'\n')
        if not counts:raise ValueError('Keine belegten Flächen erzeugt')
        manifest={'format_version':1,'source':s,'completed_at':now(),'layer_fetch_complete':True,
                  'records_per_category':dict(counts),'records_sha256':digest((work/'records.jsonl.gz').read_bytes()),
                  'requests':requests,'national_authority_coverage_guaranteed':False,**metadata}
        (work/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        target=directory/(s['id']+'--'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'))
        os.replace(work,target)
        return target
    except BaseException:
        shutil.rmtree(work,ignore_errors=True)
        raise


def base_record(s,key,name,geometry,props,evidence=None,repaired=False):
    geom,fixed=validated_geometry(geometry)
    return {'source_id':s['id'],'source_key':str(key),'category':s['routes'][0]['category'],'kind':'authority',
            'authority_name':name,'geometry':geom,'geometry_repaired':repaired or fixed,
            'properties':props,'scope':s['scope'],'source_date':s.get('source_date'),
            'evidence_url':evidence or s['documentation'],'name_rule':{'method':s['name_rule']}}


def gemfa_assignments(data):
    root=ET.fromstring(data)
    if root.tag!='{http://www.itzbund.de/GEMFA/Export/01}GemfaExport':raise ValueError('Unbekanntes GEMFA-Schema')
    towns={g.get('GemeindeId'):g for g in root.findall('{*}BundeslandListe/{*}Bundesland/{*}GemeindeListe/{*}Gemeinde')}
    offices={f.get('FinanzbehoerdeId'):f for f in root.findall('{*}FinanzamtListe/{*}Finanzamt')}
    refs=defaultdict(set);exceptions=defaultdict(set)
    for key,office in offices.items():
        for g in office.findall('{*}GemeindeListe/{*}Gemeinde'):
            if g.get('GemeindeRef') not in towns:raise ValueError('Nicht auflösbare GEMFA-Gemeindereferenz')
            refs[g.get('GemeindeRef')].add(key)
    for e in root.findall('{*}AdressezustaendigkeitListe/*'):
        exceptions[e.get('PLZ')].add(e.get('FinanzamtRef'))
    safe,excluded={},{}
    for key,g in towns.items():
        ags=g.get('AGS');choices=refs[key]
        if not ags or len(ags)!=8 or not ags.isdigit():raise ValueError('Ungültiger GEMFA-AGS')
        if len(choices)!=1:
            excluded[ags]='missing_or_multiple_municipality_assignment';continue
        office=next(iter(choices))
        plzs={g.get('PLZ')}|{e.get('PLZ') for e in g.findall('{*}OrtListe/{*}Ort')}
        if any(exceptions[p]-{office} for p in plzs):
            excluded[ags]='contradicting_address_exception';continue
        safe[ags]=office
    return towns,offices,safe,excluded


def import_gemfa(s,directory,fetch=get):
    parent,pm=parent_snapshot(directory,'vg25_gem')
    zipdata=fetch(s['download_url']);schema=fetch(s['schema_url'])
    with zipfile.ZipFile(io.BytesIO(zipdata)) as z:
        members=[i for i in z.infolist() if i.filename.lower().endswith('.xml')]
        if len(members)!=1 or members[0].file_size>100_000_000:raise ValueError('Unerwarteter GEMFA-Export')
        filename=members[0].filename;data=z.read(filename)
    towns,offices,safe,excluded=gemfa_assignments(data)
    date_match=re.search(r'Export_(\d{4})(\d{2})(\d{2})_',filename)
    export_date='-'.join(date_match.groups()) if date_match else None
    by_ags={g.get('AGS'):g for g in towns.values()}
    summary={'gemfa_file':filename,'gemeinden_total':len(towns),'offices_in_export':len(offices),
             'eligible_municipalities':len(safe),'excluded_municipalities':excluded,
             'boundary_snapshot_sha256':pm['records_sha256']}
    groups=defaultdict(list);joined=defaultdict(set);repaired_offices=set();seen_ags=set()
    def records():
        with gzip.open(parent/'records.jsonl.gz','rt',encoding='utf-8') as f:
            for line in f:
                boundary=json.loads(line);ags=boundary['properties'].get('ags')
                if ags not in by_ags:continue
                seen_ags.add(ags);town=by_ags[ags]
                if ags in safe:
                    key=safe[ags];groups[key].append(shape(boundary['geometry']));joined[key].add(ags)
                    if boundary['geometry_repaired']:repaired_offices.add(key)
                # Anrede is explicitly municipal administration only in these
                # cases. Never rename a tax office/association as the municipality.
                if town.get('Anrede') in ('Stadtverwaltung','Gemeindeverwaltung'):
                    name=town.get('Anrede')+' '+town.get('Name')
                    props={'gemfa_municipality':dict(town.attrib),'address':[dict(e.attrib) for e in town.findall('{*}Adresse')],
                           'ags':ags,'geometry_completeness':'municipality_boundary',
                           'boundary_snapshot_sha256':pm['records_sha256']}
                    r=base_record(s,'municipality-'+boundary['source_key'],name,boundary['geometry'],props,repaired=boundary['geometry_repaired'])
                    r['category']='stadtverwaltung';r['name_rule']={'method':'Explicit GEMFA Anrede Stadtverwaltung/Gemeindeverwaltung + Name; same AGS in VG25'}
                    r['source_date']=export_date
                    yield r
        for key,parts in groups.items():
            office=offices[key];name=office.get('Name','').strip()
            if not name:raise ValueError('Finanzamtsname fehlt')
            if not name.startswith('Finanzamt'):name='Finanzamt '+name
            props={'gemfa_office':dict(office.attrib),'gemeinde_ags':sorted(joined[key]),
                   'geometry_completeness':'verified_municipality_subset_of_jurisdiction',
                   'source_record_xml':ET.tostring(office,encoding='unicode'),
                   'boundary_snapshot_sha256':pm['records_sha256'],
                   'note':'Only unambiguous whole-municipality assignments, excluding contradicting address exceptions; not all special tax competences.'}
            record=base_record(s,key,name,mapping(union_all(parts)),props,repaired=key in repaired_offices)
            record['source_date']=export_date
            yield record
        summary['matched_municipalities']=len(set(safe)&seen_ags)
        summary['missing_vg25_ags']=sorted(set(safe)-seen_ags)
        summary['joined_ags_by_state']=dict(Counter(ags[:2] for ags in set(safe)&seen_ags))
    return write_snapshot(s,directory,records(),{'assignment_audit':summary},
                          [('gemfa',s['download_url'],zipdata),('schema',s['schema_url'],schema)])


def import_mapping(s,directory):
    parent,pm=parent_snapshot(directory,s['boundary_source'])
    table=resource(s['mapping_file']).read_bytes()
    if digest(table)!=s['mapping_sha256']:raise ValueError('Zuordnungstabelle nicht mehr geprüft')
    with gzip.open(parent/'records.jsonl.gz','rt',encoding='utf-8') as f:boundaries=[json.loads(line) for line in f]
    def records():
        for row in csv.DictReader(io.StringIO(table.decode('utf-8'))):
            parts=[]
            for ars in row['ars'].split('|'):
                found=[b for b in boundaries if b['properties'].get('ars')==ars]
                if not found:raise ValueError('Explizit zugeordnetes Gebiet fehlt: '+ars)
                parts.extend(found)
            props={'region_ars':row['ars'].split('|'),'mapping_reviewed_at':s['source_date'],
                   'boundary_snapshot_sha256':pm['records_sha256'],'geometry_completeness':'general_territorial_district',
                   'assignment_evidence_url':row['evidence_url']}
            yield base_record(s,row['key'],row['authority_name'],mapping(union_all([shape(p['geometry']) for p in parts])),props,
                              evidence=row['evidence_url'],repaired=any(p['geometry_repaired'] for p in parts))
    return write_snapshot(s,directory,records(),{'derivation_complete':True,'mapping_sha256':digest(table),'parent_snapshot':parent.name})


def import_inspire(s,directory,fetch=get):
    data=fetch(s['download_url']);root=ET.fromstring(data)
    members=root.findall(GML+'featureMember')
    def records():
        for member in members:
            if len(member)!=1:raise ValueError('Ungültiger INSPIRE-Datensatz')
            item=member[0];name=item.findtext(GML+'name');key=item.get(GML+'id')
            geometry=item.find('.//{*}serviceLocationByGeometry')
            if not key or not name or geometry is None:raise ValueError('INSPIRE-Datensatz unvollständig')
            value=gml_geometry(geometry,s['request_crs'])
            yield base_record(s,key,name,value,{'source_record_xml':ET.tostring(item,encoding='unicode'),
                                               'geometry_completeness':'official_source_polygon'})
    return write_snapshot(s,directory,records(),{'observed_features':len(members)},[('source',s['download_url'],data)])
