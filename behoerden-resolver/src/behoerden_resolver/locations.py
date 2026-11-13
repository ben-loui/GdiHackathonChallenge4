"""Real office locations, always kept separate from jurisdiction polygons."""
import gzip
import json
import math
import re
from pathlib import Path
from collections import Counter
import xml.etree.ElementTree as ET
from shapely import STRtree
from shapely.geometry import Point,shape
from .catalog import resource
from .http import get,request_url
from .etl import digest
from .supplements import parent_snapshot,write_snapshot
from .wfs import GML,gml_point,validated_point


def point_record(s,category,key,name,geometry,properties,date=None,evidence=None):
    return {'source_id':s['id'],'source_key':str(key),'category':category,'kind':'authority_point',
            'authority_name':name,'geometry':validated_point(geometry),'geometry_repaired':False,
            'properties':properties,'scope':s['scope'],'source_date':date or s.get('source_date'),
            'evidence_url':evidence or s['documentation'],'name_rule':{'method':s['name_rule']}}


def import_th_locations(s,directory,fetch=get):
    data=fetch(s['download_url']);root=ET.fromstring(data);excluded=Counter()
    def records():
        for member in root.findall(GML+'featureMember'):
            f=member[0];name=f.findtext(GML+'name') or '';service=f.find('{*}serviceType')
            code=service.get('{http://www.w3.org/1999/xlink}href','').rsplit('/',1)[-1]
            if code=='administrationForSocialProtection':category='jugendamt'
            elif code=='administrationForHealth':
                if re.search('veterinär|lebensmittel',name,re.I):category='veterinaeramt'
                elif re.search('gesundheit',name,re.I):category='gesundheitsamt'
                else:excluded['unclassified_health_administration']+=1;continue
            else:excluded['not_one_of_the_three_authority_categories']+=1;continue
            geom=f.find('.//{*}serviceLocationByGeometry')
            if not name or geom is None:raise ValueError('Amtlicher Standort unvollständig')
            props={'source_record_xml':ET.tostring(f,encoding='unicode'),'service_type':code,
                   'source_quality':'official','geometry_completeness':'location_only_no_jurisdiction_polygon'}
            yield point_record(s,category,f.get(GML+'id'),name,gml_point(geom,s['request_crs']),props)
    audit={'excluded_records':excluded,'note':'Original office locations; hospitals excluded. Social protection records in this specific dataset are the advertised Jugendämter.'}
    # Counter must be serialisable after the iterator has finished.
    return write_snapshot(s,directory,records(),{'classification_audit':audit},[('source',s['download_url'],data)])


PATTERNS={
 'finanzamt':r'\bfinanzamt\b',
 'stadtverwaltung':r'\b(?:stadtverwaltung|gemeindeverwaltung|rathaus|bürgermeisteramt)\b',
 'ordnungsamt':r'\bordnungs(?:amt|behörde)\b',
 'buergeramt':r'bürger(?:amt|büro|service)|einwohnermeldeamt',
 'standesamt':r'\bstandesamt\b',
 'auslaenderbehoerde':r'ausländer(?:behörde|amt)|einwanderungsamt|landesamt für einwanderung',
 'amtsgericht':r'\bamtsgericht\b', 'landgericht':r'\blandgericht\b',
 'verwaltungsgericht':r'\bverwaltungsgericht\b',
 'staatsanwaltschaft':r'\bstaatsanwaltschaft\b',
 'zoll':r'\b(?:hauptzollamt|zollamt|zoll)\b',
 'jugendamt':r'\b(?:kreis|stadt)?jugendamt\b',
 'sozialamt':r'\bsozialamt\b|amt für (?:soziales|soziale leistungen)',
 'jobcenter':r'\bjobcenter\b',
 'arbeitsagentur':r'agentur für arbeit|arbeitsagentur|arbeitsamt',
 'familienkasse':r'\bfamilienkasse\b',
 'wohngeldstelle':r'wohngeld(?:stelle|behörde)|amt für wohngeld',
 'bauamt':r'\bbauamt\b|bauaufsicht|bauordnungsamt|amt für baurecht',
 'strassenverkehrsbehoerde':r'straßenverkehrs(?:amt|behörde)|fahrerlaubnis|führerscheinstelle',
 'zulassungsstelle':r'kfz.{0,12}zulassung|zulassungs(?:stelle|behörde)',
 'gesundheitsamt':r'\b(?:kreis|stadt)?gesundheitsamt\b|fachdienst gesundheit|amt für gesundheit',
 'veterinaeramt':r'veterinär(?:amt|wesen)|veterinär.{0,30}lebensmittel',
 'umweltamt':r'\bumweltamt\b|amt für umwelt|umwelt- und naturschutzamt|untere (?:naturschutz|wasser)behörde',
 'gewerbeamt':r'\bgewerbeamt\b|gewerbemelde(?:stelle|amt)',
 'ihk':r'industrie.{0,6}und handelskammer|\bihk\b',
 'handwerkskammer':r'handwerkskammer|\bhwk\b',
 'rentenversicherung':r'deutsche rentenversicherung',
 'krankenkasse':r'\b(?:aok|barmer|dak|kkh|ikk)\b|techniker krankenkasse|knappschaft',
 'pflegekasse':r'\bpflegekasse\b',
 'bafoegamt':r'bafög|bafoeg|ausbildungsförderung',
 'schulamt':r'\bschulamt\b|schulaufsicht|landesschulbehörde',
 'kreisverwaltung':r'\blandratsamt\b|\bkreisverwaltung\b|landkreisverwaltung',
 'regierungsprs':r'regierungspräsidium|bezirksregierung|\bregierung von\b|\blandesverwaltungsamt\b',
 'bundesamt_migration':r'bundesamt für migration und flüchtlinge|\bbamf\b',
 'bundesverwaltungsamt':r'\bbundesverwaltungsamt\b',
}


def osm_categories(tags):
    # Only records returned for relevant office/amenity tags are considered;
    # a matching place name on an unrelated shop is not enough.
    if tags.get('office') not in ('government','insurance','association') and tags.get('amenity') not in ('police','courthouse','townhall'):
        return []
    if tags.get('disused')=='yes' or tags.get('abandoned')=='yes' or tags.get('access')=='private' and not tags.get('name'):
        return []
    text=' '.join(tags.get(k,'') for k in ('official_name','name','operator'))
    categories=[code for code,pattern in PATTERNS.items() if re.search(pattern,text,re.I)]
    if tags.get('amenity')=='police':categories.append('polizei')
    if tags.get('amenity')=='townhall':categories.append('stadtverwaltung')
    if 'bauamt' in categories and re.search(r'staatliches bauamt|straßenbauamt',text,re.I):categories.remove('bauamt')
    return sorted(set(categories))


def import_osm(s,directory,input_path=None):
    query=resource(s.get('query_file','osm_query.overpass')).read_text(encoding='utf-8')
    if digest(query.encode())!=s['query_sha256']:raise ValueError('OSM-Abfrage geändert; Quellenmanifest und Abdeckung aktualisieren')
    if s.get('requires_input') and not input_path:raise ValueError('Diese OSM-Quelle benötigt --input mit dem Export von scripts/osm_fetch_states.py')
    if input_path:data=Path(input_path).read_bytes()
    else:
        data=get(request_url(s['endpoint'],{'data':query}),attempts=1)
    obj=json.loads(data)
    if obj.get('remark'):raise ValueError('Unvollständiger Overpass-Abzug: '+obj['remark'])
    if not isinstance(obj.get('elements'),list) or not obj.get('osm3s',{}).get('timestamp_osm_base'):
        raise ValueError('Kein vollständiger OSM-Export')
    parent,pm=parent_snapshot(directory,'vg25_krs')
    with gzip.open(parent/'records.jsonl.gz','rt',encoding='utf-8') as f:
        tree=STRtree([shape(json.loads(line)['geometry']) for line in f])
    audit=Counter();seen=set()
    def records():
        for e in obj['elements']:
            key=e.get('type','')+'/'+str(e.get('id'))
            if key in seen:raise ValueError('Doppeltes OSM-Element')
            seen.add(key);tags=e.get('tags',{});name=tags.get('official_name') or tags.get('name')
            if not name:audit['no_office_name']+=1;continue
            coords=e if e.get('type')=='node' else e.get('center',{})
            if 'lon' not in coords or 'lat' not in coords:audit['missing_location']+=1;continue
            point=Point(float(coords['lon']),float(coords['lat']))
            if tags.get('addr:country','DE')!='DE' or not len(tree.query(point,predicate='covered_by')):
                audit['outside_official_germany_mask']+=1;continue
            codes=osm_categories(tags)
            if not codes:audit['category_not_supported_by_tags_or_name']+=1;continue
            for category in codes:
                props={'osm_tags':tags,'osm_type':e['type'],'osm_id':e['id'],
                       'source_quality':'community','classification_basis':'Conservative name patterns and explicit office/amenity tags; not an official category register',
                       'location_method':'OSM node' if e['type']=='node' else 'OSM element bounding-box centre, not necessarily a public entrance',
                       'geometry_completeness':'location_only_no_jurisdiction_polygon'}
                yield point_record(s,category,key,name,{'type':'Point','coordinates':[point.x,point.y]},props,
                                   date=obj['osm3s']['timestamp_osm_base'],evidence='https://www.openstreetmap.org/'+key)
    return write_snapshot(s,directory,records(),{'classification_audit':audit,'osm_base_timestamp':obj['osm3s']['timestamp_osm_base'],
                         'source_request_method':'GET','source_query':query,'germany_mask_records_sha256':pm['records_sha256'],
                         'source_input':'downloaded export' if input_path else 'live Overpass response'},[('source',s['endpoint'],data)])
