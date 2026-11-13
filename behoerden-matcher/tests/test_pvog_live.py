"""Offline contract tests for PVOG public API client, not live API claims."""
import json
import sqlite3
from pathlib import Path

from authority_matcher.catalog import AuthorityTaxonomy
from authority_matcher.pipeline import build_fim_documents
from authority_matcher.jzufi import connect
from authority_matcher.pvog_live import fetch_online_key, make_enricher, reference_regions
from authority_matcher.jzufi_fetch import resolve_leika
from authority_matcher.matcher import LocalMatcher, match_authority

ROOT=Path(__file__).resolve().parents[1]
TAX=AuthorityTaxonomy(ROOT/'data/categories.json')
KEY='99008001000000'


def make_fim(db):
    con=sqlite3.connect(db)
    con.execute('CREATE TABLE records(record_key TEXT PRIMARY KEY, source TEXT, document TEXT, imported_at TEXT)')
    con.execute('INSERT INTO records VALUES(?,?,?,?)',(
        'profile:'+KEY,'service-profiles',json.dumps({
            'id':'profile:'+KEY,'fim_source_key':'profile:'+KEY,
            'titel':'Personalausweis beantragen',
            'beschreibung':'Personalausweis beantragen',
            'synonyme':['Ausweis beantragen'],'leistungsschluessel':KEY,
            'behoerdenkategorien':[],'mapping_status':'kein_zustaendigkeitsfeld',
            'quelle':'fim:service-profiles'}),'2026-11-13'))
    con.commit();con.close()


class Session:
    headers={}


def test_live_jzufi_fetch_with_official_titled_org(monkeypatch,tmp_path):
    """A JZuFi service + public titles response must link FIM key to org."""
    import authority_matcher.pvog_live as mod
    import authority_matcher.jzufi_fetch as fetchmod
    db=tmp_path/'fim.sqlite3';make_fim(db)
    requests=[]
    def fake_fetch(session,url,params,**kwargs):
        requests.append((url,params))
        if url.endswith('v3/servicedescriptions/leikaid'):
            return {'content':[{'id':'L100008.LB.183729','name':'Personalausweis beantragen'}]}
        if url.endswith('/jzufi-2-3') and '/servicedescriptions/' in url:
            return {'id':'L100008.LB.183729','leistungsschluessel':[KEY], 'bezeichnung':'Personalausweis'}
        if url.endswith('v1/relations/jzufi-2-3'):
            return []  # JZuFi representation not compatible or empty; titles is backup
        if url.endswith('v2/organisationunits/titles'):
            return [{'id':'L100008.OE.17','title':'Bürgeramt Beispielstadt',
                     'role':{'code':'02','name':'Zuständige Stelle'}}]
        raise AssertionError(url)
    monkeypatch.setattr(mod,'fetch_one',fake_fetch)
    monkeypatch.setattr(fetchmod,'fetch_one',fake_fetch)
    monkeypatch.setattr(mod.time,'sleep',lambda n:None)
    report=fetch_online_key(db,TAX,KEY,regions=('110000000000',),delay=.2,session=Session())
    assert report['categories']==['buergeramt'],report
    assert report['evidence'][0]['lb_id']=='L100008.LB.183729'
    assert report['evidence'][0]['organisation']=='Bürgeramt Beispielstadt'
    assert any(x[0].endswith('v1/relations/jzufi-2-3') for x in requests)
    docs,_=build_fim_documents(db)
    assert docs[0]['behoerdenkategorien']==['buergeramt']
    calls=len(requests)
    again=fetch_online_key(db,TAX,KEY,regions=('110000000000',),delay=.2,session=Session())
    assert len(requests)==calls
    assert again['categories']==['buergeramt']


def test_live_ignores_asp_role(monkeypatch,tmp_path):
    import authority_matcher.pvog_live as mod
    import authority_matcher.jzufi_fetch as fetchmod
    db=tmp_path/'fim.sqlite3'; make_fim(db)
    def fake_fetch(session,url,params,**kwargs):
        if url.endswith('v3/servicedescriptions/leikaid'):
            return {'content':[{'id':'L123.LB.1'}]}
        if '/servicedescriptions/' in url:
            return {'id':'L123.LB.1','leistungsschluessel':[KEY]}
        if url.endswith('v1/relations/jzufi-2-3'):
            return []
        if url.endswith('v2/organisationunits/titles'):
            return [{'id':'L123.OE.1','title':'Bürgeramt Beispielstadt','role':{'code':'03'}}]
        raise AssertionError(url)
    monkeypatch.setattr(mod,'fetch_one',fake_fetch)
    monkeypatch.setattr(fetchmod,'fetch_one',fake_fetch)
    monkeypatch.setattr(mod.time,'sleep',lambda n:None)
    result=fetch_online_key(db,TAX,KEY,regions=('110000000000',),delay=.2,session=Session())
    assert result['categories']==[]


def test_empty_search_cached_not_syntax_error(monkeypatch,tmp_path):
    import authority_matcher.pvog_live as mod
    import authority_matcher.jzufi_fetch as fetchmod
    db=tmp_path/'fim.sqlite3';make_fim(db)
    calls=[]
    def fake_fetch(session,url,params,**kwargs):
        calls.append(url)
        return {'content':[]}
    monkeypatch.setattr(mod,'fetch_one',fake_fetch)
    monkeypatch.setattr(fetchmod,'fetch_one',fake_fetch)
    result=fetch_online_key(db,TAX,KEY,regions=('110000000000',),delay=.2,session=Session())
    assert result['found_official_mapping'] is False
    assert result['regions'][0]['outcome']=='empty'
    assert len(calls)==1
    fetch_online_key(db,TAX,KEY,regions=('110000000000',),delay=.2,session=Session())
    assert len(calls)==1


def test_query_enrichment_with_official_cache(monkeypatch,tmp_path):
    import authority_matcher.pvog_live as mod
    db=tmp_path/'fim.sqlite3'; make_fim(db)
    def fake_online(db,tax,key,**kwargs):
        con=connect(db)
        try:
            from authority_matcher.jzufi import import_payloads
            import_payloads(db,tax,iter([{'leistungen':[{'id':'L123.LB.1','leistungsschluessel':[KEY]}],
              'organisationseinheiten':[{'id':'L123.OE.1','name':'Bürgeramt Beispielstadt'}],
              'zustaendigkeiten':[{'leistungID':'L123.LB.1','organisationseinheitID':'L123.OE.1','rolle':{'code':'02'}}]}]),source='test:official-cache')
        finally:
            con.close()
        con=connect(db)
        from authority_matcher.jzufi import evidence_by_key
        ev=evidence_by_key(con)[KEY];con.close()
        return {'leika':key,'regions':[],'evidence':ev,'categories':['buergeramt']}
    monkeypatch.setattr(mod,'fetch_online_key',fake_online)
    docs,_=build_fim_documents(db)
    # LocalMatcher historically drops unmapped services: test enrich callback
    # over rows directly; actual CLI searches Elasticsearch which keeps them.
    rows=[(docs[0],.85)]
    traced=[]
    enriched=make_enricher(db,TAX,regions=('110000000000',),trace=traced)(rows)
    assert enriched[0][0]['behoerdenkategorien']==['buergeramt']
    assert traced[0]['leika']==KEY


def test_reference_ars_validation():
    assert reference_regions('110000000000, 073150000000')==('110000000000','073150000000')
    try:
        reference_regions('Berlin')
    except ValueError:
        pass
    else:
        raise AssertionError('invalid ARS accepted')


def test_cli_leika_empty_does_not_raise_argparse(monkeypatch, tmp_path, capsys):
    import authority_matcher.autorun as a
    db=tmp_path/'fim.sqlite3'; make_fim(db)
    monkeypatch.setattr(a,'DB',db)
    monkeypatch.setattr(a,'fetch_online_key',lambda *args,**kwargs:
                        {'leika':KEY,'categories':[],'regions':[{'ars':'110000000000','outcome':'empty'}]})
    status=a.do_fetch(['--leika',KEY,'--ars','110000000000'])
    output=capsys.readouterr()
    assert status==2
    assert 'Keine belegte Kategorie' in output.err
    assert 'Bitte --lbid' not in output.err


def test_fim_index_created_even_when_mappings_absent(monkeypatch,tmp_path):
    import authority_matcher.autorun as a
    db=tmp_path/'fim.sqlite3';make_fim(db)
    monkeypatch.setattr(a,'DB',db)
    monkeypatch.setattr(a,'EXPORT',tmp_path/'docs.jsonl')
    monkeypatch.setattr(a,'MANIFEST',tmp_path/'manifest.json')
    class FakeIndices:
        def exists(self,index): return False
    class FakeClient:
        indices=FakeIndices()
        def ping(self): return True
    monkeypatch.setattr(a,'es_client',lambda url: FakeClient())
    index_calls=[]
    monkeypatch.setattr(a,'index_elastic',lambda docs,**kwargs:
                        index_calls.append(len(docs)) or {'indexed':len(docs)})
    info=a.get_index_docs(semantic=False,force=False,no_start_docker=True)
    assert info['indexed']==1
    assert index_calls==[1]
    assert json.loads((tmp_path/'docs.jsonl').read_text().splitlines()[0])['behoerdenkategorien']==[]


def test_live_resolves_organisation_from_relation_even_if_titles_400(monkeypatch,tmp_path):
    """Regression: LIVE relations returned rows but titles endpoint HTTP 400."""
    import authority_matcher.pvog_live as mod
    import authority_matcher.jzufi_fetch as fetchmod
    db=tmp_path/'fim.sqlite3'; make_fim(db)
    calls=[]
    lb='L100008.LB.183729'
    oe='L100008.OE.51'
    def fake_fetch(session,url,params,**kwargs):
        calls.append((url,params))
        if url.endswith('v3/servicedescriptions/leikaid'):
            return {'content':[{'id':lb}]}
        if '/servicedescriptions/' in url and url.endswith('/jzufi-2-3'):
            return {'id':lb, 'leistungsschluessel':[KEY]}
        if url.endswith('/v1/relations/jzufi-2-3'):
            return [{'leistungID':lb, 'organisationseinheitID':oe,
                     'rolle':{'code':'02'}, 'gebietID':'110000000000'}]
        if url.endswith('/v1/organisationunits/'+oe+'/jzufi-2-3'):
            return {'id':oe, 'name':'Bürgeramt Beispielstadt'}
        if url.endswith('/v2/organisationunits/titles'):
            raise RuntimeError('PVOG HTTP 400: invalid request')
        raise AssertionError(url)
    monkeypatch.setattr(mod,'fetch_one',fake_fetch)
    monkeypatch.setattr(fetchmod,'fetch_one',fake_fetch)
    monkeypatch.setattr(mod.time,'sleep',lambda n:None)
    report=fetch_online_key(db,TAX,KEY,regions=('110000000000',),delay=.2,session=Session())
    assert report['categories']==['buergeramt'], report
    assert report['regions'][0]['outcome']=='success', report
    assert report['evidence'][0]['org_id']==oe
    assert any('/v1/organisationunits/'+oe+'/' in url for url,_ in calls)
    original_count=len(calls)
    fetch_online_key(db,TAX,KEY,regions=('110000000000',),delay=.2,session=Session())
    assert len(calls)==original_count


def test_relation_without_org_does_not_cache_as_complete_success(monkeypatch,tmp_path):
    import authority_matcher.pvog_live as mod
    import authority_matcher.jzufi_fetch as fetchmod
    db=tmp_path/'fim.sqlite3'; make_fim(db)
    lb='L100008.LB.183729'
    def fake_fetch(session,url,params,**kwargs):
        if url.endswith('v3/servicedescriptions/leikaid'):
            return {'content':[{'id':lb}]}
        if '/servicedescriptions/' in url and url.endswith('/jzufi-2-3'):
            return {'id':lb,'leistungsschluessel':[KEY]}
        if url.endswith('/v1/relations/jzufi-2-3'):
            return [{'leistungID':lb,'organisationseinheitID':'L100008.OE.1',
                     'rolle':{'code':'02'}}]
        if '/organisationunits/' in url:
            raise RuntimeError('PVOG HTTP 503')
        raise AssertionError(url)
    monkeypatch.setattr(mod,'fetch_one',fake_fetch)
    monkeypatch.setattr(fetchmod,'fetch_one',fake_fetch)
    monkeypatch.setattr(mod.time,'sleep',lambda n:None)
    report=fetch_online_key(db,TAX,KEY,regions=('110000000000',),delay=.2,session=Session())
    assert report['categories']==[]
    assert report['regions'][0]['outcome']=='partial'


def test_v3_success_without_any_org_is_not_cached(tmp_path):
    from authority_matcher.pvog_live import initialize, _recent_attempt, _record_attempt
    db=tmp_path/'fim.sqlite3'
    initialize(db)
    _record_attempt(db,KEY,'110000000000','success',
      json.dumps({'counts':{'lbids':1,'jzufi_relations':2,'titles_links':0,'orgs':0}}))
    assert _recent_attempt(db,KEY,'110000000000') is None


def test_live_nested_jzufi_agency_ids_are_joined(monkeypatch, tmp_path):
    """Regression: genuine XZuFi IDs are schemeAgencyID+value, not .LB/.OE."""
    import authority_matcher.pvog_live as mod
    import authority_matcher.jzufi_fetch as fetchmod
    db = tmp_path / 'fim.sqlite3'
    make_fim(db)
    calls = []
    lb = 'L100039.LB.8966482'
    oe = 'L100039.OE.4711'

    def fake_fetch(session, url, params, **kwargs):
        calls.append(url)
        if url.endswith('v3/servicedescriptions/leikaid'):
            return {'content': [{'id': lb}]}
        if url.endswith('/servicedescriptions/' + lb + '/jzufi-2-3'):
            return {'id': {'schemeAgencyID': 'L100039', 'value': '8966482'},
                    'leistungsschluessel': [KEY]}
        if url.endswith('/v1/relations/jzufi-2-3'):
            return {'content': [{
                'organisationseinheitID': {'schemeAgencyID':'L100039','value':'4711'},
                'zustaendigkeit': [{
                    'leistungID': {'schemeAgencyID':'L100039','value':'8966482'},
                    'gebietID': {'value':'073150000000','schemeAgencyID':'DESTATIS'},
                    'rolle': [{'code':'03'},{'code':'02'}]
                }]
            }]}
        if url.endswith('/v1/organisationunits/' + oe + '/jzufi-2-3'):
            return {'id': {'schemeAgencyID': 'L100039', 'value': '4711'},
                    'name': [{'wert':'Bürgeramt Beispielstadt'}]}
        if url.endswith('/v2/organisationunits/titles'):
            raise AssertionError('When direct JZuFi OE resolution succeeds, titles is not needed')
        raise AssertionError(url)

    monkeypatch.setattr(mod, 'fetch_one', fake_fetch)
    monkeypatch.setattr(fetchmod, 'fetch_one', fake_fetch)
    monkeypatch.setattr(mod.time, 'sleep', lambda n: None)
    result = fetch_online_key(db, TAX, KEY, regions=('073150000000',), delay=.2, session=Session())
    assert result['categories'] == ['buergeramt'], result
    assert result['evidence'][0]['lb_id'] == lb
    assert result['evidence'][0]['org_id'] == oe
    assert result['evidence'][0]['gebiete'] == ['073150000000']
    assert not any('/v2/organisationunits/titles' in x for x in calls)


def test_partial_and_error_cache_are_not_reused(tmp_path):
    import authority_matcher.pvog_live as mod
    db = tmp_path / 'fim.sqlite3'; make_fim(db)
    region = '073150000000'
    mod.initialize(db)
    mod._record_attempt(db, KEY, region, 'partial', '{"counts":{"jzufi_relations":2,"orgs":0}}')
    assert mod._recent_attempt(db, KEY, region) is None
    mod._record_attempt(db, KEY, region, 'error', 'HTTP 400')
    assert mod._recent_attempt(db, KEY, region) is None


def test_live_productive_titles_requires_singular_lbId(monkeypatch, tmp_path):
    """Regression from PVOG 2026-11-13: "Parameter lbId ... fehlt"."""
    import authority_matcher.pvog_live as mod
    import authority_matcher.jzufi_fetch as fetchmod
    db = tmp_path / 'fim.sqlite3'
    make_fim(db)
    lb = 'L100039.LB.8966482'
    calls = []
    def fake_fetch(session, url, params, **kwargs):
        calls.append((url, params))
        if url.endswith('v3/servicedescriptions/leikaid'):
            return {'content': [{'id': lb}]}
        if url.endswith('/v1/servicedescriptions/' + lb + '/jzufi-2-3'):
            return {'id': {'schemeAgencyID': 'L100039', 'value': '8966482'}}
        if url.endswith('/v1/relations/jzufi-2-3'):
            # Actual incident showed returned relations but no usable org IDs.
            return {'content': [{'zustaendigkeit': [
                {'leistungID': {'schemeAgencyID': 'L100039', 'value': '8966482'},
                 'rolle': {'code': '02'}, 'gebietID': {'value': '073150000000'}}]}]}
        if url.endswith('/v2/organisationunits/titles'):
            assert params['lbId'] == lb
            assert 'lbids' not in params
            assert params['ars'] == '073150000000'
            return [{'id': 'L100039.OE.42', 'title': 'Bürgeramt Beispielstadt',
                     'role': {'code': '02', 'name': 'Zuständige Stelle'}}]
        raise AssertionError((url, params))
    monkeypatch.setattr(mod, 'fetch_one', fake_fetch)
    monkeypatch.setattr(fetchmod, 'fetch_one', fake_fetch)
    monkeypatch.setattr(mod.time, 'sleep', lambda _: None)
    result = fetch_online_key(db, TAX, KEY, regions=('073150000000',), delay=.2,
                              session=Session())
    assert result['found_official_mapping'], result
    assert result['categories'] == ['buergeramt']
    assert result['regions'][0]['outcome'] == 'success'
    con = connect(db)
    try:
        assert con.execute("SELECT COUNT(*) FROM jzufi_links WHERE org_id='' ").fetchone()[0] == 0
    finally:
        con.close()


def test_cleans_old_empty_organisation_relations_without_touching_valid(tmp_path):
    from authority_matcher.pvog_live import initialize
    from authority_matcher.jzufi import import_payloads
    db = tmp_path / 'fim.sqlite3'
    make_fim(db)
    # Explicitly simulate a corrupt link from old local cache.
    con = connect(db)
    con.execute("INSERT INTO jzufi_links VALUES('bad','L100039.LB.8966482','','02','[]','{}','previous')")
    con.execute("INSERT INTO jzufi_links VALUES('good','L100039.LB.8966482','L100039.OE.42','02','[]','{}','previous')")
    con.commit()
    con.close()
    initialize(db)
    con = connect(db)
    try:
        rows = con.execute('SELECT link_id FROM jzufi_links ORDER BY link_id').fetchall()
        assert rows == [('good',)]
    finally:
        con.close()


def test_relation_without_organisation_is_not_imported(tmp_path):
    from authority_matcher.jzufi import import_payloads
    db = tmp_path / 'fim.sqlite3'
    make_fim(db)
    result = import_payloads(db, TAX, iter([{'content':[{'zustaendigkeit':[
        {'leistungID': {'schemeAgencyID': 'L100039', 'value': '8966482'},
         'rolle': {'code': '02'}, 'gebietID': '073150000000'}]}]}]), source='test')
    assert result['links'] == 0
    con = connect(db)
    try:
        assert con.execute('SELECT COUNT(*) FROM jzufi_links').fetchone()[0] == 0
    finally:
        con.close()
