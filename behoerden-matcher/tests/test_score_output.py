"""Top-level category score is surfaced in both JSON and terminal output."""
import json

from authority_matcher.catalog import AuthorityTaxonomy
from authority_matcher.cli import show
from authority_matcher.matcher import match_authority
from pathlib import Path

TAX = AuthorityTaxonomy(Path(__file__).resolve().parents[1] / 'data/categories.json')


def doc(name, categories):
    return {
        'id': name, 'titel': name, 'leistungsschluessel': '99115005070000',
        'behoerdenkategorien': categories, 'mapping_status': 'jzufi_live_belegt',
        'quelle': 'fim:landesredaktion'
    }


def test_top_level_score_matches_aggregated_category_ranking(monkeypatch):
    rows = [
        (doc('Wohnsitz abmelden A', ['buergeramt', 'stadtverwaltung']), .01639),
        (doc('Wohnsitz abmelden B', ['buergeramt']), .01613),
        (doc('Wohnsitz abmelden C', ['buergeramt']), .01587),
    ]
    monkeypatch.setattr('authority_matcher.matcher.es_search', lambda *a, **kw: rows)
    result = match_authority('Ich möchte meinen Wohnsitz abmelden', backend='elasticsearch')
    expected = round(.01639 * .6 + .01613 / 1.35 + .01587 / 1.70, 5)
    assert result['status'] == 'vorschlag'
    assert result['behoerdenkategorie'] == 'buergeramt'
    assert result['score'] == expected
    assert result['alternativen'][0] == {'id': 'stadtverwaltung', 'score': round(.01639 * .6, 5)}
    assert result['leistungen'][0]['score'] == .01639


def test_json_displays_score(monkeypatch, capsys):
    monkeypatch.setattr('authority_matcher.matcher.es_search', lambda *a, **kw: [(doc('Wohnsitz abmelden', ['buergeramt']), .01639)])
    result = match_authority('Wohnsitz abmelden', backend='elasticsearch')
    show(result, TAX, as_json=True)
    rendered = json.loads(capsys.readouterr().out)
    assert rendered == {'behoerdenkategorie': 'buergeramt', 'score': .01639}


def test_terminal_displays_score(monkeypatch, capsys):
    monkeypatch.setattr('authority_matcher.matcher.es_search', lambda *a, **kw: [(doc('Wohnsitz abmelden', ['buergeramt']), .01639)])
    result = match_authority('Wohnsitz abmelden', backend='elasticsearch')
    show(result, TAX, as_json=False)
    assert capsys.readouterr().out == 'buergeramt (Score: 0.01639)\n'


def test_unknown_category_has_null_score(monkeypatch):
    monkeypatch.setattr('authority_matcher.matcher.es_search', lambda *a, **kw: [(doc('Wohnsitz abmelden', []), .01639)])
    result = match_authority('Wohnsitz abmelden', backend='elasticsearch')
    assert result['behoerdenkategorie'] is None
    assert result['score'] is None


def test_ambiguous_response_preserves_top_ranked_score(monkeypatch):
    monkeypatch.setattr('authority_matcher.matcher.es_search', lambda *a, **kw: [(doc('Antrag', ['buergeramt', 'stadtverwaltung']), .01639)])
    result = match_authority('Wohnsitz abmelden', backend='elasticsearch')
    assert result['status'] == 'mehrdeutig'
    assert result['behoerdenkategorie'] is None
    assert result['top_kategorie'] in ('buergeramt', 'stadtverwaltung')
    assert result['score'] == round(.01639 * .6, 5)


def test_compact_json_has_no_organisations_or_other_fields(capsys):
    """Prevent PVOG organisation names from leaking into default CLI output."""
    result = {
        'status': 'vorschlag', 'behoerdenkategorie': 'buergeramt', 'score': .04621,
        'top_kategorie': 'buergeramt',
        'alternativen': [{'id': 'stadtverwaltung', 'score': .0123}],
        'leistungen': [{'titel': 'Wohnsitz abmelden',
                       'behoerdenkategorien': ['buergeramt'],
                       'zuordnung_belege': [{'organisation': 'Bürgeramt Berlin'}]}],
        'pvog_live': [{'regions': ['110000000000']}],
    }
    show(result, TAX, as_json=True)
    out = capsys.readouterr().out
    assert json.loads(out) == {'behoerdenkategorie': 'buergeramt', 'score': .04621}
    assert 'Berlin' not in out
    assert 'leistungen' not in out
    assert 'alternativen' not in out
    show(result, TAX, as_json=True, details=True)
    assert 'Bürgeramt Berlin' in capsys.readouterr().out


def test_compact_ambiguous_has_null_score(capsys):
    result = {'status': 'mehrdeutig', 'behoerdenkategorie': None, 'score': .01234,
              'top_kategorie': 'buergeramt', 'leistungen': [], 'alternativen': []}
    show(result, TAX, as_json=True)
    assert json.loads(capsys.readouterr().out) == {'behoerdenkategorie': None, 'score': None}
    show(result, TAX, as_json=False)
    assert capsys.readouterr().out == 'null (Score: null)\n'


def test_cli_parser_accepts_details_flag():
    from authority_matcher.autorun import parser
    assert parser().parse_args(['--json', '--no-semantic', 'Mein Wohnsitz']).details is False
    assert parser().parse_args(['--json', '--details', 'Mein Wohnsitz']).details is True
    assert parser().parse_args(['--debug', 'Mein Wohnsitz']).details is True


def test_autorun_compact_end_to_end_mocked(monkeypatch, capsys):
    from authority_matcher import autorun
    monkeypatch.setattr(autorun, 'DB', type('DBStub', (), {'exists': lambda self: True})())
    monkeypatch.setattr(autorun, 'get_index_docs', lambda **kwargs: {})
    monkeypatch.setattr(autorun, 'reference_regions', lambda _: ('073150000000',))
    monkeypatch.setattr(autorun, 'make_enricher', lambda *a, **kw: lambda rows: rows)
    monkeypatch.setattr(autorun, 'match_authority', lambda *a, **kw: {
        'status': 'vorschlag', 'behoerdenkategorie': 'buergeramt', 'score': .03791,
        'leistungen': [{'titel': 'Wohnsitz abmelden', 'zuordnung_belege': [
            {'organisation': 'Bürgeramt Adlershof'}]}], 'alternativen': []})
    assert autorun.main(['--json','--no-semantic','Wohnsitz abmelden']) == 0
    captured=capsys.readouterr()
    assert json.loads(captured.out) == {'behoerdenkategorie': 'buergeramt', 'score': .03791}
    assert captured.err == ''

