import json
from pathlib import Path
from authority_matcher.catalog import AuthorityTaxonomy
from authority_matcher import fim_import

ROOT = Path(__file__).resolve().parents[1]


def test_import_pages_and_detail_without_location(monkeypatch, tmp_path):
    calls = []
    def mock(*args, executable='fim-portal'):
        calls.append(args)
        if args[:2] == ('service-texts', 'search'):
            if '--offset' in args and args[args.index('--offset') + 1] == '0':
                return {'items': [{'redaktion_id': 'B1', 'leistung_id': 111, 'source': 'leika'}]}
            return {'items': []}
        if args[:2] == ('service-texts', 'get'):
            return {'redaktion_id': 'B1', 'leistung_id': 111,
                    'leistungsbezeichnungI': 'Erbschein erteilen',
                    'zuständige Stelle': 'Nachlassgericht'}
        raise AssertionError(args)
    monkeypatch.setattr(fim_import, 'call_fim', mock)
    file = tmp_path / 'fim.jsonl'
    stats = fim_import.collect_fim(file, AuthorityTaxonomy(ROOT / 'data/categories.json'), limit=1)
    doc = json.loads(file.read_text(encoding='utf-8').strip())
    assert stats['normalized'] == 1
    assert doc['behoerdenkategorien'] == ['amtsgericht']
    assert doc['quelle'] == 'fim:leika'
    assert doc['mapping_status'] == 'aus_zustaendigkeitsfeld'
    assert not any('ars' in ' '.join(c).lower() for c in calls)
