import json
from urllib.parse import parse_qs, urlsplit
import pytest
from shapely.geometry import shape
from behoerden_resolver.catalog import source
from behoerden_resolver import resolver


def feature(key='one',coordinates=None,group=None):
    props={'name':'SYNTHETIC TEST AUTHORITY','extra_original_field':'preserved'}
    if group:props['behoerdenUntergruppe']=group
    return {'type':'Feature','id':key,'properties':props,'geometry':{'type':'Polygon','coordinates':coordinates or [[[8,49],[9,49],[9,50],[8,50],[8,49]]]}}


def service(pages,urls):
    def fetch(url):
        urls.append(url);p=parse_qs(urlsplit(url).query)
        fs,total=pages[int(p['startIndex'][0])]
        return json.dumps({'type':'FeatureCollection','features':fs,'numberMatched':total}).encode()
    return fetch


def test_live_bbox_and_full_geometry_no_database(monkeypatch):
    monkeypatch.setattr(resolver,'sources',lambda:[source('bzb_jobcenter')])
    monkeypatch.setattr(resolver.db,'resolve',lambda *a,**k:pytest.fail('Live WFS must not need PostGIS'))
    urls=[]
    r=resolver.resolve('jobcenter',8.5,49.5,backend='auto',fetch=service({0:([feature()],1)},urls))
    assert r['backend']=='wfs' and r['status']=='candidate'
    m=r['matches'][0]
    assert m['authority_name']=='SYNTHETIC TEST AUTHORITY'
    assert m['properties']['extra_original_field']=='preserved'
    assert shape(m['geometry']).area==1
    p=parse_qs(urlsplit(urls[0]).query)
    assert p['typeNames']==['bzb-open:ba_jobcenter']
    assert p['bbox'][0].endswith('urn:ogc:def:crs:OGC::CRS84')
    assert p['srsName']==['urn:ogc:def:crs:OGC::CRS84']
    assert r['wfs_queries'][0]['request_urls']==urls


def test_bbox_is_not_point_membership_and_holes_are_excluded():
    hole=feature(coordinates=[[[8,49],[9,49],[9,50],[8,50],[8,49]],[[8.2,49.2],[8.4,49.2],[8.4,49.4],[8.2,49.4],[8.2,49.2]]])
    rows,_=resolver.query_wfs(source('bzb_jobcenter'),'jobcenter',8.3,49.3,service({0:([hole],1)},[]))
    assert rows==[]
    rows,_=resolver.query_wfs(source('bzb_jobcenter'),'jobcenter',9,49.5,service({0:([feature()],1)},[]))
    assert len(rows)==1 and rows[0]['on_boundary']


def test_live_paging_checks_actual_counts_and_repeated_ids():
    urls=[]
    rows,trace=resolver.query_wfs(source('bzb_jobcenter'),'jobcenter',8.5,49.5,service({0:([feature('a')],'unknown'),1:([feature('b')],'unknown'),2:([],'unknown')},urls))
    assert len(rows)==2 and trace['candidate_count']==2 and len(urls)==3
    with pytest.raises(ValueError,match='wiederholte'):
        resolver.query_wfs(source('bzb_jobcenter'),'jobcenter',8.5,49.5,service({0:([feature()],2),1:([feature()],2)},[]))
    with pytest.raises(ValueError,match='Unvollständige'):
        resolver.query_wfs(source('bzb_jobcenter'),'jobcenter',8.5,49.5,service({0:([feature()],2),1:([],2)},[]))


def test_live_errors_never_silently_turn_into_old_cache(monkeypatch):
    monkeypatch.setattr(resolver,'sources',lambda:[source('bzb_jobcenter')])
    monkeypatch.setattr(resolver.db,'resolve',lambda *a,**k:pytest.fail('No implicit stale fallback'))
    def fail(url):raise OSError('service unavailable')
    with pytest.raises(RuntimeError,match='bzb_jobcenter'):
        resolver.resolve('jobcenter',8.5,49.5,fetch=fail)


def test_regional_wfs_does_not_block_local_nationwide_complement(monkeypatch):
    monkeypatch.setattr(resolver,'sources',lambda:[source('by_finanzamt'),source('hh_finanzamt'),source('gemfa_vg25')])
    def local(code,lon,lat,dsn=None,**kwargs):
        assert set(kwargs['exclude_sources'])=={'by_finanzamt','hh_finanzamt'}
        return {'category':code,'status':'candidate','matches':[{'authority_name':'SYNTHETIC LOCAL','geometry':feature()['geometry'],'properties':{'geometry_completeness':'verified_municipality_subset_of_jurisdiction'}}]}
    monkeypatch.setattr(resolver.db,'resolve',local)
    r=resolver.resolve('finanzamt',8.27,50,fetch=lambda url:pytest.fail('No Bavarian or Hamburg WFS query for Mainz'))
    assert r['backend']=='local' and r['matches'][0]['geometry_completeness']=='verified_municipality_subset_of_jurisdiction'
    assert r['wfs_queries']==[]


def test_boundary_references_and_excluded_layers_never_become_authority_wfs(monkeypatch):
    monkeypatch.setattr(resolver,'sources',lambda:[source('vg25_krs')])
    with pytest.raises(ValueError,match='Kein Behördengebiets'):
        resolver.resolve('kreisverwaltung',8.27,50,backend='wfs')
    with pytest.raises(ValueError,match='kein verwendbarer'):
        resolver.query_wfs(source('by_verwaltungsgericht'),'verwaltungsgericht',11.6,48.1)


def test_gml_bbox_uses_projected_xy_and_both_backends_reject_bad_inputs():
    values=resolver.point_bbox(source('by_finanzamt'),11.6,48.1).split(',')
    assert values[-1]=='EPSG:3857' and float(values[0])>1_000_000 and float(values[1])>6_000_000
    for backend in ['auto','local','wfs']:
        with pytest.raises(ValueError):resolver.resolve('jobcenter',float('nan'),50,backend=backend)
    assert resolver.resolve('krankenkasse',8,50)['status']=='non_spatial'
