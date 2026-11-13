import gzip
import json
import os
from pathlib import Path
import pytest
from psycopg.conninfo import conninfo_to_dict
from behoerden_resolver import db,resolver
from behoerden_resolver.catalog import source
from behoerden_resolver.etl import digest
from behoerden_resolver.locations import osm_categories


def test_polygon_match_always_prevents_point_fallback(monkeypatch):
    polygon={'type':'MultiPolygon','coordinates':[[[[8,49],[9,49],[9,50],[8,50],[8,49]]]]}
    monkeypatch.setattr(resolver,'_resolve_areas',lambda *a,**k:{'category':'gesundheitsamt','status':'candidate','matches':[{'authority_name':'TEST AREA','geometry':polygon}]})
    monkeypatch.setattr(db,'nearby',lambda *a,**k:pytest.fail('A matching polygon has strict priority'))
    r=resolver.resolve('gesundheitsamt',8.5,49.5)
    assert r['fallback_used'] is False and r['matches'][0]['match_type']=='polygon_cover'


def test_osm_names_need_relevant_office_tags_and_exclude_wrong_authority_kind():
    assert osm_categories({'name':'Finanzamt Restaurant'})==[]
    assert osm_categories({'office':'government','name':'Finanzamt TEST'})==['finanzamt']
    assert 'bauamt' not in osm_categories({'office':'government','name':'Staatliches Bauamt TEST'})
    assert 'amtsgericht' not in osm_categories({'office':'government','name':'Oberlandesgericht TEST'})
    assert 'ihk' in osm_categories({'office':'association','name':'Industrie- und Handelskammer TEST'})
    assert osm_categories({'amenity':'police','name':'TEST','disused':'yes'})==[]


@pytest.mark.integration
def test_geodesic_radius_category_filter_order_and_documented_point_fallback(tmp_path):
    dsn=os.environ.get('TEST_DATABASE_URL')
    if not dsn:pytest.skip('TEST_DATABASE_URL not set')
    assert conninfo_to_dict(dsn)['dbname'].endswith('_test')
    db.init(dsn)
    s=source('th_health_locations');path=tmp_path/'locations';path.mkdir()
    rows=[]
    for key,lat,category in [('close',50.01,'gesundheitsamt'),('second',50.03,'gesundheitsamt'),('far',51,'gesundheitsamt'),('other-category',50.001,'veterinaeramt')]:
        rows.append({'source_id':s['id'],'source_key':key,'category':category,'kind':'authority_point','authority_name':'SYNTHETIC '+key,
                     'geometry':{'type':'Point','coordinates':[8,lat]},'properties':{'test_fixture':True},'scope':'TEST','source_date':None,
                     'evidence_url':'https://example.invalid/synthetic-test','name_rule':{}})
    with gzip.open(path/'records.jsonl.gz','wt') as f:
        for row in rows:f.write(json.dumps(row)+'\n')
    m={'format_version':1,'layer_fetch_complete':True,'source':s,'completed_at':'2026-01-01T00:00:00Z','records_per_category':{'gesundheitsamt':3,'veterinaeramt':1},'records_sha256':digest((path/'records.jsonl.gz').read_bytes())}
    (path/'manifest.json').write_text(json.dumps(m))
    db.load_snapshot(path,dsn)
    near=db.nearby('gesundheitsamt',8,50,radius_km=2,dsn=dsn)
    assert len(near)==1 and near[0]['source_key']=='close'
    assert 1100<near[0]['distance_m']<1120
    assert near[0]['geometry']['type']=='Point' and near[0]['jurisdiction_verified'] is False
    assert [r['source_key'] for r in db.nearby('gesundheitsamt',8,50,radius_km=10,dsn=dsn)]==['close','second']
    result=resolver.resolve('gesundheitsamt',8,50,dsn,backend='local',radius_km=2)
    assert result['fallback_used'] is True and result['status']=='nearby_candidate'
    assert result['matches'][0]['geometry']['type']=='Point'
    assert result['point_search']['radius_km']==2 and result['warning']
    assert not resolver.resolve('gesundheitsamt',8,50,dsn,backend='local',point_fallback=False)['matches']
    assert not resolver.resolve('gesundheitsamt',8,50,dsn,backend='local',radius_km=0.1)['matches']


def test_live_only_option_cannot_hide_a_local_polygon_from_point_fallback(monkeypatch):
    monkeypatch.setattr(resolver,'_resolve_areas',lambda *a,**k:{'category':'finanzamt','status':'no_coverage_at_point','matches':[]})
    monkeypatch.setattr(db,'resolve',lambda *a,**k:{'category':'finanzamt','status':'candidate','matches':[{'authority_name':'TEST LOCAL AREA','properties':{},'geometry':{'type':'MultiPolygon','coordinates':[]}}]})
    monkeypatch.setattr(db,'nearby',lambda *a,**k:pytest.fail('A local polygon supplement takes priority over any point'))
    r=resolver.resolve('finanzamt',8.5,49.5,backend='wfs')
    assert r['fallback_used'] is False and r['fallback_area_check'] is True
    assert r['matches'][0]['authority_name']=='TEST LOCAL AREA'


def test_nonspatial_status_survives_a_nearby_contact_suggestion(monkeypatch):
    monkeypatch.setattr(resolver,'sources',lambda:[{'kind':'authority_point','routes':[{'category':'krankenkasse'}]}])
    monkeypatch.setattr(db,'nearby',lambda *a,**k:[{'authority_name':'TEST CONTACT','jurisdiction_verified':False,'geometry':{'type':'Point','coordinates':[8,50]}}])
    result=resolver.resolve('krankenkasse',8,50)
    assert result['status']=='non_spatial' and result['fallback_used'] is True
    assert result['required_context'] and result['matches'][0]['jurisdiction_verified'] is False


def test_osm_snapshot_rejects_incomplete_data_masks_foreign_points_and_keeps_centres(tmp_path,monkeypatch):
    from behoerden_resolver import locations
    from behoerden_resolver.etl import read_manifest
    s=source('osm_locations');raw=tmp_path/'export.json'
    raw.write_text(json.dumps({'remark':'Query timed out','elements':[]}))
    with pytest.raises(ValueError,match='Unvollständiger'):
        locations.import_osm(s,tmp_path/'snapshots',raw)
    parent=tmp_path/'mask';parent.mkdir()
    geom={'type':'Polygon','coordinates':[[[8,49.9],[8.2,49.9],[8.2,50.2],[8,50.2],[8,49.9]]]}
    with gzip.open(parent/'records.jsonl.gz','wt') as f:f.write(json.dumps({'geometry':geom})+'\n')
    monkeypatch.setattr(locations,'parent_snapshot',lambda *a:(parent,{'records_sha256':'test-mask'}))
    obj={'osm3s':{'timestamp_osm_base':'2026-01-01T00:00:00Z'},'elements':[
      {'type':'node','id':1,'lat':50,'lon':8.1,'tags':{'office':'government','name':'Finanzamt TEST'}},
      {'type':'node','id':2,'lat':50,'lon':9,'tags':{'office':'government','name':'Finanzamt OUTSIDE'}},
      {'type':'way','id':3,'center':{'lat':50.1,'lon':8.1},'tags':{'office':'government','name':'Standesamt TEST'}}]}
    raw.write_text(json.dumps(obj));path=locations.import_osm(s,tmp_path/'snapshots',raw)
    manifest=read_manifest(path)
    assert manifest['source']['license']=='ODbL-1.0' and manifest['classification_audit']['outside_official_germany_mask']==1
    with gzip.open(path/'records.jsonl.gz','rt') as f:rows=[json.loads(line) for line in f]
    assert len(rows)==2 and all(r['geometry']['type']=='Point' for r in rows)
    assert 'bounding-box centre' in next(r for r in rows if r['source_key']=='way/3')['properties']['location_method']


def test_osm_states_source_needs_the_per_state_export_and_merge_is_strict(tmp_path):
    from behoerden_resolver import locations
    import importlib.util
    s=source('osm_states_locations')
    with pytest.raises(ValueError,match='--input'):
        locations.import_osm(s,tmp_path)
    spec=importlib.util.spec_from_file_location('osm_fetch_states',Path(__file__).parents[1]/'scripts/osm_fetch_states.py')
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    ok=lambda stamp,*ids:{'osm3s':{'timestamp_osm_base':stamp},'elements':[{'type':'node','id':i} for i in ids]}
    merged=mod.merge({'DE-BE':ok('2026-01-02T00:00:00Z',1,2),'DE-BB':ok('2026-01-01T00:00:00Z',2,3)})
    assert [e['id'] for e in merged['elements']]==[2,3,1]
    assert merged['osm3s']['timestamp_osm_base']=='2026-01-01T00:00:00Z'
    with pytest.raises(ValueError,match='unvollständig'):
        mod.validate({'remark':'runtime error','elements':[]},'DE-BE')
