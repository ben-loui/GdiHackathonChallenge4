import gzip
import json
from pathlib import Path
import pytest
from shapely.geometry import shape
from behoerden_resolver.catalog import resource, source
from behoerden_resolver.derive import build_courts
from behoerden_resolver.etl import digest, read_manifest


def regions(tmp_path, omit=None):
    path=tmp_path/'vg25_rbz--TEST';path.mkdir()
    names=['Oberbayern','Niederbayern','Oberpfalz','Oberfranken','Mittelfranken','Unterfranken','Schwaben']
    with gzip.open(path/'records.jsonl.gz','wt') as stream:
        for i,name in enumerate(names,1):
            if name==omit:continue
            x=8+i/10
            stream.write(json.dumps({'area_name':name,'source_key':str(i),'geometry_repaired':False,'properties':{'ars':f'09{i}'},'geometry':{'type':'Polygon','coordinates':[[[x,49],[x+0.1,49],[x+0.1,50],[x,50],[x,49]]]}})+'\n')
    (path/'manifest.json').write_text(json.dumps({'format_version':1,'layer_fetch_complete':True,'source':source('vg25_rbz'),'completed_at':'2026-01-01T00:00:00Z','records_sha256':digest((path/'records.jsonl.gz').read_bytes())}))


def test_explicit_assignment_unites_two_regions_and_retains_provenance(tmp_path):
    regions(tmp_path)
    path=build_courts(source('by_verwaltungsgericht_gesetz'),tmp_path)
    assert read_manifest(path)['records_per_category']=={'verwaltungsgericht':6}
    with gzip.open(path/'records.jsonl.gz','rt') as stream:rows=[json.loads(line) for line in stream]
    regensburg=next(r for r in rows if r['source_key']=='32')
    assert regensburg['properties']['region_ars']==['092','093']
    assert shape(regensburg['geometry']).area==pytest.approx(0.2)
    assert regensburg['evidence_url'].endswith('BayAGVwGO-1')
    assert regensburg['properties']['boundary_snapshot_completed_at']=='2026-01-01T00:00:00Z'


def test_missing_explicit_region_never_falls_back_to_nearest_court(tmp_path):
    regions(tmp_path,omit='Oberpfalz')
    with pytest.raises(ValueError,match='fehlt'):
        build_courts(source('by_verwaltungsgericht_gesetz'),tmp_path)
    assert len(list(tmp_path.iterdir()))==1
