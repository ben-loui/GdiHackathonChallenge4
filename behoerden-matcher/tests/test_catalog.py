from pathlib import Path
from authority_matcher.catalog import AuthorityTaxonomy, normalize_record
from authority_matcher.index import load_catalog
from authority_matcher.matcher import LocalMatcher, match_authority

ROOT = Path(__file__).resolve().parents[1]
T = AuthorityTaxonomy(ROOT / 'data/categories.json')


def test_taxonomy_real_aliases():
    assert T.categorize('Finanzamt für Erbschaftsteuer') == ['finanzamt']
    assert T.categorize('Nachlassgericht') == ['amtsgericht']
    assert T.categorize('Fahrerlaubnisbehörde') == ['strassenverkehrsbehoerde']
    assert T.categorize('Krankenkassen') == ['krankenkasse']


def test_source_must_be_explicit_zustaendige_stelle():
    raw = {'leistungsschluessel': '99011111100000', 'leistungsbezeichnungI': 'Ausweis beantragen',
           'fachlich_freigegeben_durch': 'Finanzamt',
           'herausgebende_stelle': 'Amtsgericht',
           'zustaendige_stelle': 'Bürgeramt'}
    rec = normalize_record(raw, T)
    assert rec['behoerdenkategorien'] == ['buergeramt']
    assert rec['quelle'] == 'fim'
    assert rec['mapping_status'] == 'aus_zustaendigkeitsfeld'


def test_no_authority_no_hallucination():
    raw = {'id': 'abc', 'titel': 'Schenkung anmelden',
           'fachlich_freigegeben_durch': 'Finanzamt'}
    rec = normalize_record(raw, T)
    assert rec['behoerdenkategorien'] == []
    assert rec['mapping_status'] == 'kein_zustaendigkeitsfeld'


def test_role_and_ambiguous():
    raw = {'id': 'a', 'titel': 'Leistung', 'organisationseinheiten': [
        {'rolle': 'Ansprechpunkt', 'name': 'Bürgerbüro'},
        {'rolle': 'zuständige Stelle', 'name': 'Gewerbeamt'},
        {'rolle': 'zuständige Stelle', 'name': 'Ordnungsamt'}]}
    result = normalize_record(raw, T)
    assert set(result['behoerdenkategorien']) == {'gewerbeamt', 'ordnungsamt'}
    assert result['mapping_status'] == 'mehrdeutig'


def test_demo_queries():
    demo = load_catalog(ROOT / 'data/demo_services.jsonl', T, demo=True)
    matcher = LocalMatcher(demo)
    a = match_authority('Meine Oma hat mir 10.000 Euro geschenkt, wie gebe ich das rechtlich an?', local=matcher)
    b = match_authority('Ich habe mir einen Beagle zugelegt, wie melde ich das dem Staat?', local=matcher)
    assert a['top_kategorie'] == 'finanzamt', a
    assert b['top_kategorie'] == 'stadtverwaltung', b
    assert a['suchmodus'] == 'lexikalisch'
    assert a['leistungen'][0]['quelle'] == 'demo'


def test_out_of_domain():
    docs = load_catalog(ROOT / 'data/demo_services.jsonl', T, demo=True)
    matcher = LocalMatcher(docs)
    res = match_authority('Quantenchromodynamik Higgsboson Elektronenspin', local=matcher)
    assert res['status'] == 'keine_zuordnung', res


def test_demo_provenance_detected_without_explicit_flag():
    doc = next(x for x in load_catalog(ROOT / 'data/demo_services.jsonl', T) if x['id'] == 'demo-schenkung')
    assert doc['quelle'] == 'demo'
    assert doc['mapping_status'] == 'demo'
