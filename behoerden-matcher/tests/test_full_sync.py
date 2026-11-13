import json
from pathlib import Path

import pytest

from authority_matcher.catalog import AuthorityTaxonomy
from authority_matcher import full_sync

T = AuthorityTaxonomy(Path(__file__).resolve().parents[1] / 'data/categories.json')


def test_full_crawl_sources_and_unmapped_retained(monkeypatch, tmp_path):
    requests = []
    def mock(*args, executable='fim-portal'):
        requests.append(args)
        if args[:2] == ('service-profiles', 'search'):
            return {'items': [{'leistungsschluessel': '99000001', 'titel': 'Stammleistung'}]}
        if args[:2] == ('service-profiles', 'get'):
            return {'leistungsschluessel': '99000001', 'titel': 'Stammleistung'}
        if args[:2] == ('service-texts', 'search'):
            source = args[args.index('--source') + 1]
            return {'items': [{'redaktionId': 'B001', 'leistungId': '88', 'source': source}]}
        if args[:2] == ('service-texts', 'get'):
            return {'redaktionId': 'B001', 'leistungId': '88', 'titel': 'Hundesteuer anmelden',
                    'zuständige Stelle': 'Stadtverwaltung'}
        raise AssertionError(args)
    monkeypatch.setattr(full_sync, 'call_fim', mock)
    db = tmp_path / 'fim.sqlite'
    report = full_sync.sync_catalog(db, T, pause=0, printer=lambda _: None)
    assert report['total_records'] == 4
    assert report['unmapped'] == 1
    assert report['with_authority'] == 3
    assert report['all_sources_complete']
    out = tmp_path / 'index.jsonl'
    assert full_sync.export_jsonl(db, out) == 4
    docs = [json.loads(row) for row in out.read_text().splitlines()]
    assert {x['quelle'] for x in docs} == {'fim:service-profiles', 'fim:leika', 'fim:landesredaktion', 'fim:pvog'}
    assert any(not x['behoerdenkategorien'] for x in docs)
    before = len(requests)
    full_sync.sync_catalog(db, T, pause=0, printer=lambda _: None)
    assert len(requests) == before
    assert all('ars' not in ' '.join(req).lower() for req in requests)


def test_resume_after_failure(monkeypatch, tmp_path):
    attempts = {'gets': 0}
    def flaky(*args, executable='fim-portal'):
        if args[:2] == ('service-texts', 'search'):
            return {'items': [
                {'redaktionId': 'B1', 'leistungId': '1'},
                {'redaktionId': 'B1', 'leistungId': '2'}]}
        if args[:2] == ('service-texts', 'get'):
            attempts['gets'] += 1
            if args[3] == '2' and attempts['gets'] == 2:
                raise RuntimeError('temporary unavailable')
            return {'redaktionId': 'B1', 'leistungId': args[3], 'titel': 'Schenkung anzeigen',
                    'zuständige Stelle': 'Finanzamt'}
        raise AssertionError(args)
    monkeypatch.setattr(full_sync, 'call_fim', flaky)
    db = tmp_path / 'resumable.sqlite'
    first = full_sync.sync_catalog(db, T, sources=('leika',), pause=0, printer=lambda _: None)
    assert first['sources']['leika']['processed'] == 2
    assert first['sources']['leika']['finished']
    assert first['missing_details'] == 1
    assert first['with_authority'] == 1
    assert not first['all_sources_complete']
    next_pass = full_sync.sync_catalog(db, T, sources=('leika',), force_retry=True, pause=0, printer=lambda _: None)
    assert next_pass['missing_details'] == 0
    assert next_pass['total_records'] == 2
    assert next_pass['with_authority'] == 2
    assert next_pass['sources']['leika']['processed'] == 2


def test_limit_cannot_complete_source(monkeypatch, tmp_path):
    def mock(*args, executable='fim-portal'):
        if args[:2] == ('service-profiles', 'search'):
            return {'items': [{'leistungsschluessel': '123', 'titel': 'Steckbrief'}]}
        if args[:2] == ('service-profiles', 'get'):
            return {'leistungsschluessel': '123', 'titel': 'Steckbrief'}
        raise AssertionError(args)
    monkeypatch.setattr(full_sync, 'call_fim', mock)
    status = full_sync.sync_catalog(tmp_path / 'limit.sqlite', T, sources=('service-profiles',),
                                    max_records=1, pause=0, printer=lambda _: None)
    assert not status['sources']['service-profiles']['finished']


def test_propagate_mapping_only_from_matching_real_fim_key(tmp_path):
    from authority_matcher.index import load_catalog
    data = [
        {'id': 'profile:1', 'leistungsschluessel': '111', 'titel': 'Erbschein', 'synonyme': [],
         'beschreibung': '', 'behoerdenkategorien': [], 'mapping_status': 'kein_zustaendigkeitsfeld',
         'zustaendige_stelle_original': [], 'quelle': 'fim:service-profiles'},
        {'id': 'text:1', 'leistungsschluessel': '111', 'titel': 'Erbschein erteilen', 'synonyme': [],
         'beschreibung': '', 'behoerdenkategorien': ['amtsgericht'], 'mapping_status': 'aus_zustaendigkeitsfeld',
         'zustaendige_stelle_original': ['Nachlassgericht'], 'quelle': 'fim:leika'},
        {'id': 'profile:2', 'leistungsschluessel': '222', 'titel': 'Hundesteuer', 'synonyme': [],
         'beschreibung': '', 'behoerdenkategorien': [], 'mapping_status': 'kein_zustaendigkeitsfeld',
         'zustaendige_stelle_original': [], 'quelle': 'fim:service-profiles'},
    ]
    source = tmp_path / 'records.jsonl'
    source.write_text('\n'.join(json.dumps(d) for d in data))
    docs = {d['id']: d for d in load_catalog(source, T)}
    assert docs['profile:1']['behoerdenkategorien'] == ['amtsgericht']
    assert docs['profile:1']['mapping_status'] == 'aus_anderem_fim_stammtext'
    assert docs['profile:2']['behoerdenkategorien'] == []


def test_upgrade_existing_database_and_skip_one_bad_profile(monkeypatch, tmp_path):
    db = tmp_path / 'from_previous_install.sqlite3'
    connection = full_sync.connect_db(db)
    full_sync.set_progress(connection, 'service-profiles', 319)
    connection.close()
    requested = []

    def mock(*args, executable='fim-portal'):
        requested.append(args)
        if args[:2] == ('service-profiles', 'search'):
            assert args[args.index('--offset') + 1] == '200'
            return {'items': [{'leistungsschluessel': str(i), 'titel': f'Leistung {i}'}
                              for i in range(201, 326)], 'total_count': 325}
        if args[:2] == ('service-profiles', 'get'):
            if args[2] == '320':
                raise RuntimeError('502: invalid upstream record')
            return {'leistungsschluessel': args[2], 'titel': f'Leistung {args[2]}'}
        raise AssertionError(args)

    monkeypatch.setattr(full_sync, 'call_fim', mock)
    status = full_sync.sync_catalog(db, T, sources=('service-profiles',), pause=0, printer=lambda _: None)
    assert status['sources']['service-profiles']['processed'] == 325
    assert status['sources']['service-profiles']['finished']
    assert status['missing_details'] == 1
    assert status['total_records'] == 6  # 320 as summary, 321-325 as full details
    assert not status['all_sources_complete']
    assert ('service-profiles', 'get', '319') not in requested
    assert ('service-profiles', 'get', '321') in requested

    def recovered(*args, executable='fim-portal'):
        assert args == ('service-profiles', 'get', '320')
        return {'leistungsschluessel': '320', 'titel': 'Leistung 320'}

    monkeypatch.setattr(full_sync, 'call_fim', recovered)
    status = full_sync.sync_catalog(db, T, sources=('service-profiles',), pause=0,
                                    force_retry=True, printer=lambda _: None)
    assert status['missing_details'] == 0
    assert status['total_records'] == 6


def test_cli_retries_temporary_network_failures(monkeypatch):
    import subprocess
    from authority_matcher.fim_import import call_fim
    responses = [subprocess.CompletedProcess([], 1, '', 'network timeout'),
                 subprocess.CompletedProcess([], 0, '{"items":[]}', '')]
    seen = []

    def fake_run(cmd, **kwargs):
        seen.append(cmd)
        return responses.pop(0)

    monkeypatch.setattr(subprocess, 'run', fake_run)
    monkeypatch.setattr('authority_matcher.fim_import.time.sleep', lambda _: None)
    assert call_fim('service-profiles', 'get', '123') == {'items': []}
    assert len(seen) == 2
    assert seen[0][1:5] == ['--timeout', '60000', '--max-retries', '4']


def test_parallel_fetch_preserves_checkpoint_and_missing_records(monkeypatch, tmp_path):
    """Network work overlaps, but records, offsets and failed IDs remain ordered."""
    import threading
    import time

    lock = threading.Lock()
    activity = {'active': 0, 'peak': 0}
    items = [{'redaktionId': 'L1', 'leistungId': str(i), 'titel': f'Leistung {i}'} for i in range(1, 9)]

    def mock(*args, executable='fim-portal'):
        if args[:2] == ('service-texts', 'search'):
            return {'items': items, 'total_count': 8}
        if args[:2] == ('service-texts', 'get'):
            with lock:
                activity['active'] += 1
                activity['peak'] = max(activity['peak'], activity['active'])
            try:
                time.sleep(.01 * (9 - int(args[3])))  # Finish in the opposite order.
                if args[3] == '4':
                    raise RuntimeError('Temporary FIM 503')
                return {'titel': f'Leistung {args[3]}', 'zuständige Stelle': 'Finanzamt'}
            finally:
                with lock:
                    activity['active'] -= 1
        raise AssertionError(args)

    monkeypatch.setattr(full_sync, 'call_fim', mock)
    db = tmp_path / 'parallel.sqlite'
    report = full_sync.sync_catalog(db, T, sources=('landesredaktion',),
                                    workers=4, max_rps=None, pause=0,
                                    printer=lambda _: None)
    assert activity['peak'] > 1
    assert report['sources']['landesredaktion']['processed'] == 8
    assert report['sources']['landesredaktion']['finished']
    assert report['total_records'] == 8
    assert report['missing_details'] == 1
    conn = full_sync.connect_db(db)
    try:
        assert [row[0] for row in conn.execute('SELECT record_key FROM records ORDER BY record_key')] == [
            f'text:L1:{i}:landesredaktion' for i in range(1, 9)]
        record = conn.execute("SELECT document FROM records WHERE record_key='text:L1:4:landesredaktion'").fetchone()
        assert json.loads(record[0])['retrieval_status'] == 'summary_only'
    finally:
        conn.close()


def test_parallel_resume_does_not_start_at_zero(monkeypatch, tmp_path):
    items = [{'redaktionId': 'L1', 'leistungId': str(i), 'titel': f'Leistung {i}'} for i in range(1, 9)]
    requests = []

    def mock(*args, executable='fim-portal'):
        if args[:2] == ('service-texts', 'search'):
            return {'items': items, 'total_count': 8}
        if args[:2] == ('service-texts', 'get'):
            requests.append(args[3])
            return {'titel': 'Beratung', 'zuständige Stelle': 'Finanzamt'}
        raise AssertionError(args)

    monkeypatch.setattr(full_sync, 'call_fim', mock)
    db = tmp_path / 'resume.sqlite'
    first = full_sync.sync_catalog(db, T, sources=('pvog',), workers=3,
                                   max_records=3, pause=0, printer=lambda _: None)
    assert first['sources']['pvog']['processed'] == 3
    assert first['total_records'] == 3
    requests.clear()
    second = full_sync.sync_catalog(db, T, sources=('pvog',), workers=3,
                                    pause=0, printer=lambda _: None)
    assert second['sources']['pvog']['processed'] == 8
    assert second['sources']['pvog']['finished']
    assert second['total_records'] == 8
    assert set(requests) == {str(i) for i in range(4, 9)}


def test_worker_limits_are_checked(tmp_path):
    import pytest
    for workers, rps in [(0, 5), (13, 5), (4, 0), (4, -1)]:
        with pytest.raises(ValueError):
            full_sync.sync_catalog(tmp_path / 'invalid.sqlite', T, workers=workers,
                                   max_rps=rps, printer=lambda _: None)
