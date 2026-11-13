"""Contract tests based on representative XZuFi/JZuFi field names.
Fixtures are synthetically constructed; they are NOT official live API responses.
"""
import json
import sqlite3
from pathlib import Path

from authority_matcher.catalog import AuthorityTaxonomy
from authority_matcher.jzufi import import_payloads, mapping_stats, connect, relation_data
from authority_matcher.pipeline import build_fim_documents

ROOT = Path(__file__).resolve().parents[1]
TAX = AuthorityTaxonomy(ROOT / 'data/categories.json')
KEY = '99008001000000'


def create_fim(db):
    con=sqlite3.connect(db)
    con.execute('''CREATE TABLE records(record_key TEXT PRIMARY KEY,source TEXT NOT NULL,document TEXT NOT NULL,imported_at TEXT NOT NULL)''')
    con.execute('''INSERT INTO records VALUES(?,?,?,?)''',(
        'profile:'+KEY,'service-profiles',json.dumps({
            'id':'profile:'+KEY,'fim_source_key':'profile:'+KEY,'titel':'Personalausweis beantragen',
            'beschreibung':'Personalausweis bei der zuständigen Behörde beantragen',
            'synonyme':['Ausweis beantragen'],'leistungsschluessel':KEY,
            'behoerdenkategorien':[],'mapping_status':'kein_zustaendigkeitsfeld',
            'quelle':'fim:service-profiles'}),'2026-11-13'))
    con.commit()
    con.close()


def payload():
    return {
        'leistungen':[{'id':'L123456.LB.111','title':'Personalausweis beantragen',
                      'leistungsschluessel':[KEY]}],
        'organisationseinheiten':[{'id':'L123456.OE.222',
                                   'name':'Bürgeramt Musterstadt'}],
        'zustaendigkeiten':[{'leistungID':[{'value':'L123456.LB.111'}],
                            'organisationseinheitID':{'value':'L123456.OE.222'},
                            'gebietID':[{'value':'073150000000'}],
                            'rolle':{'code':'02'}}],
    }


def test_jzufi_join_to_fim_existing_database(tmp_path):
    db=tmp_path/'fim_catalog.sqlite3'
    create_fim(db)
    stats=import_payloads(db,TAX,iter([payload()]),source='test-synthetic')
    assert stats['services_total']==1
    assert stats['mapped_links']==1
    docs,metrics=build_fim_documents(db)
    assert docs[0]['behoerdenkategorien']==['buergeramt']
    assert docs[0]['zuordnung_belege'][0]['rolle']=='02'
    assert docs[0]['zuordnung_belege'][0]['gebiete']==['073150000000']
    assert metrics['fim_with_jzufi_category']==1
    assert docs[0]['mapping_status']=='jzufi_belegt'


def test_unknown_relationship_not_guessed(tmp_path):
    db=tmp_path/'test.sqlite3'
    create_fim(db)
    p=payload()
    p['zustaendigkeiten'][0]['rolle']={'code':'03'} # only ansprechpunkt, not responsible
    import_payloads(db,TAX,iter([p]),source='test-synthetic')
    docs,metrics=build_fim_documents(db)
    assert metrics['fim_with_jzufi_category']==0
    assert docs[0]['mapping_status']=='ohne_jzufi_zuordnung'


def test_no_title_based_inference_or_ambiguous_link(tmp_path):
    db=tmp_path/'test.sqlite3'
    create_fim(db)
    p=payload()
    p['leistungen'][0]['leistungsschluessel']=['99000000000000']
    import_payloads(db,TAX,iter([p]),source='test-synthetic')
    docs,_=build_fim_documents(db)
    assert docs[0]['behoerdenkategorien']==[]


def test_mixed_import_order_resolves(tmp_path):
    db=tmp_path/'test.sqlite3'
    create_fim(db)
    p=payload()
    import_payloads(db,TAX,iter([{'zustaendigkeiten':p['zustaendigkeiten']}]),source='rels')
    import_payloads(db,TAX,iter([{'organisationseinheiten':p['organisationseinheiten']}]),source='orgs')
    import_payloads(db,TAX,iter([{'leistungen':p['leistungen']}]),source='services')
    docs,_=build_fim_documents(db)
    assert docs[0]['behoerdenkategorien']==['buergeramt']


def test_multiple_valid_categories_are_ambiguous(tmp_path):
    db=tmp_path/'test.sqlite3'
    create_fim(db)
    p=payload()
    p['organisationseinheiten'].append({'id':'L123456.OE.223','name':'Ordnungsamt Musterstadt'})
    p['zustaendigkeiten'].append({'leistungID':['L123456.LB.111'],
                                  'organisationseinheitID':'L123456.OE.223',
                                  'rolle':{'code':'01'}})
    import_payloads(db,TAX,iter([p]),source='test-synthetic')
    docs,_=build_fim_documents(db)
    assert set(docs[0]['behoerdenkategorien'])=={'ordnungsamt','buergeramt'}
    assert docs[0]['mapping_status']=='jzufi_mehrdeutig'


def test_full_text_query_reduces_to_category(tmp_path):
    from authority_matcher.matcher import LocalMatcher, match_authority
    db=tmp_path/'test.sqlite3'
    create_fim(db)
    import_payloads(db,TAX,iter([payload()]),source='synthetic-test')
    docs,_=build_fim_documents(db)
    answer=match_authority('Wo kann ich einen Personalausweis beantragen?',
                            local=LocalMatcher(docs),backend='local')
    assert answer['top_kategorie']=='buergeramt'
    assert answer['status']=='vorschlag'


def test_jzufi_content_envelope_with_nested_zustaendigkeit(tmp_path):
    db=tmp_path/'test.sqlite3'
    create_fim(db)
    p=payload()
    envelope={'content':[{'organisationseinheitID':'L123456.OE.222',
                          'zustaendigkeit': [dict(p['zustaendigkeiten'][0])]}]}
    import_payloads(db,TAX,iter([{'leistungen':p['leistungen']},
                                 {'organisationseinheiten':p['organisationseinheiten']},
                                 envelope]),source='synthetic-test')
    docs,_=build_fim_documents(db)
    assert docs[0]['behoerdenkategorien']==['buergeramt']


def test_xzufi_xml_import_and_id_agency(tmp_path):
    from authority_matcher.jzufi import import_files
    db=tmp_path/'fim_catalog.sqlite3'
    create_fim(db)
    xml=tmp_path/'transfer.xml'
    xml.write_text('''<transfer xmlns:x="urn:xzufi:test">
      <x:leistung><x:id schemeAgencyID="L123456">111</x:id>
      <x:leistungsschluessel>99008001000000</x:leistungsschluessel>
      <x:bezeichnung>Personalausweis beantragen</x:bezeichnung></x:leistung>
      <x:organisationseinheit><x:id schemeAgencyID="L123456">222</x:id>
      <x:name>Bürgeramt Musterstadt</x:name>
      <x:zustaendigkeit><x:leistungID schemeAgencyID="L123456">111</x:leistungID>
      <x:rolle><x:code>02</x:code></x:rolle></x:zustaendigkeit>
      </x:organisationseinheit></transfer>''', encoding='utf-8')
    stats=import_files(db,TAX,[xml])
    docs,_=build_fim_documents(db)
    assert stats['mapped_links']==1
    assert docs[0]['behoerdenkategorien']==['buergeramt']
