"""Synthetic geometries only, in a dedicated *_test database. Never user data."""
import gzip
import json
import os
from pathlib import Path
import pytest
from psycopg.conninfo import conninfo_to_dict
from behoerden_resolver import db
from behoerden_resolver.catalog import source
from behoerden_resolver.etl import digest

pytestmark=pytest.mark.integration


@pytest.fixture(scope='module')
def dsn():
    value=os.environ.get('TEST_DATABASE_URL')
    if not value:
        pytest.skip('TEST_DATABASE_URL not set')
    if not conninfo_to_dict(value).get('dbname','').endswith('_test'):
        pytest.fail('Integration tests require a database name ending in _test')
    db.init(value)
    return value


def snapshot(tmp_path,records):
    path=tmp_path/'fixture';path.mkdir(exist_ok=True)
    with gzip.open(path/'records.jsonl.gz','wt') as stream:
        for record in records:stream.write(json.dumps(record)+'\n')
    (path/'manifest.json').write_text(json.dumps({'format_version':1,'source':source('bzb_jobcenter'),'layer_fetch_complete':True,'completed_at':'2026-01-01T00:00:00Z','records_per_category':{'jobcenter':len(records)},'records_sha256':digest((path/'records.jsonl.gz').read_bytes())}))
    return path


def record(key,name,coordinates):
    return dict(category='jobcenter',source_id='bzb_jobcenter',source_key=key,authority_name=name,kind='authority',geometry={'type':'MultiPolygon','coordinates':[coordinates]},geometry_repaired=False,properties={'test_fixture':True},scope='TEST',source_date=None,evidence_url='https://example.invalid/synthetic-test',name_rule={})


def records():
    return [record('left','SYNTHETIC LEFT',[[[8,49],[9,49],[9,50],[8,50],[8,49]],[[8.2,49.2],[8.4,49.2],[8.4,49.4],[8.2,49.4],[8.2,49.2]]]),
            record('right','SYNTHETIC RIGHT',[[[9,49],[10,49],[10,50],[9,50],[9,49]]])]


def test_partitions_spatial_query_holes_and_boundary_ambiguity(dsn,tmp_path):
    path=snapshot(tmp_path,records())
    db.load_snapshot(path,dsn)
    assert db.resolve('jobcenter',8.5,49.5,dsn)['status']=='candidate'
    assert db.resolve('jobcenter',8.3,49.3,dsn)['matches']==[] # hole
    boundary=db.resolve('jobcenter',9,49.5,dsn)
    assert boundary['status']=='ambiguous' and len(boundary['matches'])==2
    assert all(r['on_boundary'] for r in boundary['matches'])
    assert db.resolve('jobcenter',7,49.5,dsn)['status']=='no_coverage_at_point'
    with db.connect(dsn) as conn:
        assert conn.execute("SELECT count(*) AS n FROM pg_inherits WHERE inhparent='behoerden.authorities'::regclass").fetchone()['n']==36
        assert conn.execute('SELECT count(*) AS n FROM behoerden.jobcenter').fetchone()['n']==2
    db.load_snapshot(path,dsn)  # replacement, never duplicated
    assert len(db.resolve('jobcenter',9,49.5,dsn)['matches'])==2
    # Historical rows must retain the licence/attribution of their actual
    # import, even if the current source catalogue is subsequently updated.
    with db.connect(dsn) as conn:
        conn.execute("UPDATE behoerden.sources SET metadata=jsonb_set(metadata,'{license}','\"CHANGED CATALOGUE\"') WHERE id='bzb_jobcenter'")
    try:
        assert db.resolve('jobcenter',8.5,49.5,dsn)['matches'][0]['license']==source('bzb_jobcenter')['license']
    finally:
        db.init(dsn)


def test_failed_import_preserves_previous_complete_source(dsn,tmp_path):
    good=records()
    db.load_snapshot(snapshot(tmp_path,good),dsn)
    invalid=record('bad','SYNTHETIC BAD',[[[8,49],[9,49],[9,50],[8,50],[8,49]]])
    invalid['geometry']={'type':'Point','coordinates':[8,49]}
    path=snapshot(tmp_path,[invalid])
    with pytest.raises(Exception):db.load_snapshot(path,dsn)
    assert len(db.resolve('jobcenter',9,49.5,dsn)['matches'])==2
    corrupt=records();corrupt[0]['category']='amtsgericht'
    with pytest.raises(ValueError,match="Quelle/Kategorie"):
        db.load_snapshot(snapshot(tmp_path,corrupt),dsn)
    assert len(db.resolve('jobcenter',9,49.5,dsn)['matches'])==2
