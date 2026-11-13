"""Official Brandenburg CSV registries; institutional territories and office points."""
import csv,io,json,gzip,sys,subprocess
from collections import Counter,defaultdict
from pyproj import Transformer
from shapely import union_all
from shapely.geometry import shape,mapping
from .catalog import resource
from .http import get
from .etl import normalise_feature
from .locations import point_record
from .supplements import parent_snapshot,write_snapshot,base_record


def download(url):
    # The macOS system client validates certificates with the OS trust store,
    # including its managed roots. Verification is never disabled.
    if sys.platform=='darwin':
        return subprocess.run(['/usr/bin/curl','--fail','--silent','--show-error','--location','--proto','=https','--proto-redir','=https','--max-time','120',url],capture_output=True,check=True).stdout
    return get(url)


def csv_rows(data):
    text=data.decode('utf-8-sig').lstrip('\ufeff')
    rows=list(csv.DictReader(io.StringIO(text),delimiter=';'))
    if not rows:raise ValueError('Leeres amtliches CSV-Verzeichnis')
    return rows


def import_bb(s,directory,input_path=None,fetch=download):
    from pathlib import Path
    data=Path(input_path).read_bytes() if input_path else fetch(s['download_url'])
    rows=csv_rows(data);seen=set();audit=Counter();invalid_coordinates=[]
    is_local=s['format'] in ('bb_kommunal_points','bb_kommunal_areas')
    if s['format']=='bb_kommunal_areas':
        boundaries={}
        pms={}
        for sid in ['vg25_gem','vg25_krs']:
            path,pm=parent_snapshot(directory,sid);groups=defaultdict(list)
            with gzip.open(path/'records.jsonl.gz','rt',encoding='utf-8') as f:
                for line in f:
                    b=json.loads(line);prop=b['properties']
                    if prop.get('sn_l')=='12':groups[prop['ars']].append(b)
            boundaries[sid]=groups;pms[sid]=pm['records_sha256']
    transform=Transformer.from_crs(s.get('request_crs','EPSG:25833'),'EPSG:4326',always_xy=True)
    def records():
        for row in rows:
            if is_local:
                key=row['regionalschluessel'];name=row['bezeichnung_2'] or row['bezeichnung'];typ=row['organisationsart']
            else:
                key=row.get('INSPIRE_ID');name=row['BEHOERDENBEZEICHNUNG'];typ=row['ORGANISATIONSART'].strip()
            if not key:audit['missing_stable_identifier']+=1;continue
            if key in seen:raise ValueError('Doppelte amtliche Behörden-ID')
            seen.add(key)
            if s['format']=='bb_kommunal_areas':
                if typ=='Landkreis':category='kreisverwaltung';sid='vg25_krs'
                elif typ in ('kreisfreie Stadt','Landeshauptstadt'):category='stadtverwaltung';sid='vg25_krs'
                elif typ=='amtsfreie Gemeinde':category='stadtverwaltung';sid='vg25_gem'
                else:audit['excluded_amts_or_shared_administration_not_inferred']+=1;continue
                parts=boundaries[sid].get(key)
                if not parts:audit['unmatched_current_region_key']+=1;continue
                props={'original_directory_record':row,'region_ars':key,'boundary_source':sid,'boundary_records_sha256':pms[sid],
                       'responsibility_subject':'Institutional territory of the explicitly identified Landkreis or independent municipal administration; no specialist task inferred',
                       'geometry_completeness':'institutional_administrative_territory'}
                r=base_record(s,key,name,mapping(union_all([shape(b['geometry']) for b in parts])),props,repaired=any(b['geometry_repaired'] for b in parts))
                r['category']=category;yield r
            else:
                if is_local:
                    category='kreisverwaltung' if typ=='Landkreis' else 'stadtverwaltung'
                    if typ not in ('Landkreis','amtsfreie Gemeinde','kreisfreie Stadt','Landeshauptstadt'):
                        audit['excluded_shared_municipal_office_role']+=1;continue
                    categories=[category];east=row.get('utm_ostwert');north=row.get('utm_nordwert')
                else:
                    categories=[r['category'] for r in s['routes'] if key in r.get('ids',[])]
                    east=row.get('UTM_OSTWERT');north=row.get('UTM_NORDWERT')
                if not categories:audit['excluded_other_institution_type']+=1;continue
                if not east or not north:audit['missing_original_coordinates']+=1;continue
                try:
                    x,y=transform.transform(float(east.replace(',','.')),float(north.replace(',','.')))
                    if not (5<=x<=16 and 47<=y<=56):raise ValueError('Outside plausible German location range')
                except (ValueError,OverflowError):
                    audit['invalid_original_coordinate']+=1
                    invalid_coordinates.append({'source_key':key,'east':east,'north':north})
                    continue
                for category in categories:
                    props={'original_directory_record':row,'source_quality':'official',
                           'geometry_completeness':'location_only_no_jurisdiction_polygon',
                           'coordinate_crs':s['request_crs'],'coordinate_crs_evidence':s['coordinate_crs_evidence']}
                    if category=='auslaenderbehoerde':props['institution_scope']='Zentrale Ausländerbehörde; specialised central office, not a universal local immigration jurisdiction'
                    yield point_record(s,category,key,name,{'type':'Point','coordinates':[x,y]},props)
    return write_snapshot(s,directory,records(),{'observed_directory_rows':len(rows),'classification_audit':audit,'invalid_coordinate_rows':invalid_coordinates,
                          'source_input':'user-supplied cached official CSV' if input_path else 'verified HTTPS download',
                          'national_authority_coverage_guaranteed':False},[('source',s['download_url'],data)])
