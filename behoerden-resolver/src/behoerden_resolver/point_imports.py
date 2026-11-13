"""Complete public GeoJSON and ArcGIS office locations with explicit source routes."""
import json
from collections import Counter
import xml.etree.ElementTree as ET
from .http import get,request_url
from .etl import normalise_feature
from .supplements import write_snapshot


def import_points(s,directory,fetch=get):
    raw=[]
    def read(label,url):
        b=fetch(url);raw.append((label,url,b));return json.loads(b)
    if s['format']=='arcgis_points':
        meta=read('metadata',request_url(s['endpoint'],{'f':'json'}))
        if meta.get('geometryType')!='esriGeometryPoint':raise ValueError('ArcGIS-Layer ist kein Standortpunktlayer')
        ids=read('ids',request_url(s['endpoint']+'/query',{'where':'1=1','returnIdsOnly':'true','f':'json'}))
        keys=ids.get('objectIds')
        if not isinstance(keys,list) or not keys or len(set(keys))!=len(keys):raise ValueError('ArcGIS-IDs fehlen oder sind doppelt')
        keyfield=ids['objectIdFieldName'];features=[]
        for i in range(0,len(keys),200):
            o=read('page-'+str(i),request_url(s['endpoint']+'/query',{'objectIds':','.join(map(str,sorted(keys)[i:i+200])), 'outFields':'*','outSR':4326,'f':'geojson'}))
            if o.get('error') or o.get('exceededTransferLimit'):raise ValueError('Unvollständige ArcGIS-Seite')
            features.extend(o.get('features',[]))
        if {f['properties'].get(keyfield) for f in features}!=set(keys) or len(features)!=len(keys):raise ValueError('ArcGIS-Ergebnis entspricht nicht den angekündigten IDs')
    else:
        obj=read('source',s['download_url'])
        if obj.get('type')!='FeatureCollection':raise ValueError('Keine GeoJSON FeatureCollection')
        crs=obj.get('crs',{}).get('properties',{}).get('name')
        if crs and crs not in ('urn:ogc:def:crs:OGC:1.3:CRS84','urn:ogc:def:crs:EPSG::4326','EPSG:4326'):raise ValueError('Unbekanntes GeoJSON-CRS')
        features=obj.get('features');keyfield=s['id_field']
        if not isinstance(features,list) or not features:raise ValueError('Leere Standortdatei')
        if s.get('count_url'):
            b=fetch(s['count_url']);raw.append(('count',s['count_url'],b));root=ET.fromstring(b)
            count=root.get('numberMatched') or root.get('numberOfFeatures')
            if count is None or not count.isdigit() or int(count)!=len(features):raise ValueError('Standortdatei und amtlicher WFS-Zähler widersprechen sich')
    seen=set();audit=Counter()
    def records():
        for f in features:
            props=f.get('properties',{});key=props.get(keyfield)
            if key is None or str(key) in seen:raise ValueError('Fehlende oder doppelte Standort-ID')
            seen.add(str(key));f={**f,'id':str(key)}
            rows=list(normalise_feature(s,f))
            if not rows:audit['excluded_unrelated_authority_kind']+=1
            for r in rows:
                r['properties']={**r['properties'],'source_quality':'official','geometry_completeness':'location_only_no_jurisdiction_polygon'}
                r['source_date']=s.get('source_date')
                r['name_rule']['classification_basis']='Explicit category routes for this named official source; no jurisdiction inferred from office location'
                yield r
    return write_snapshot(s,directory,records(),{'observed_features':len(features),'classification_audit':audit,'location_coverage_only':True},raw)
