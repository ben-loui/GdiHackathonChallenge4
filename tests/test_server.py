import unittest
from unittest.mock import patch

from app import server


def polygon(name, coords):
    return {"type": "Feature", "properties": {"name": name}, "geometry": {"type": "Polygon", "coordinates": [coords]}}


class FinderTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()

    def test_point_inside_boundary_and_outside(self):
        collection = {"features": [polygon("A", [[0,0], [1,0], [1,1], [0,1], [0,0]]),
                                   polygon("B", [[1,0], [2,0], [2,1], [1,1], [1,0]])]}
        names = lambda x: [f["properties"]["name"] for f in server.matches_for_point(collection, x, 0.5)[0]]
        self.assertEqual(names(0.5), ["A"])
        self.assertEqual(names(1), ["A", "B"])
        self.assertEqual(names(3), [])


    def test_invalid_source_geometry_is_repaired_and_reported(self):
        collection = {"features": [polygon("bowtie", [[0,0], [2,2], [0,2], [2,0], [0,0]])]}
        matches, repaired = server.matches_for_point(collection, 1, 0.5)
        self.assertTrue(repaired)
        self.assertEqual(len(matches), 1)
        from shapely.geometry import shape
        self.assertTrue(shape(matches[0]["geometry"]).is_valid)

    def test_invalid_location_and_unknown_layer_are_rejected(self):
        response = self.client.post('/api/lookup', json={"lat": 50, "lon": 8, "layer": "arbitrary"})
        self.assertEqual(response.status_code, 400)

    def test_truncated_wfs_results_are_not_reported_as_complete(self):
        with patch.object(server.requests, 'get') as get:
            get.return_value.json.return_value = {"type": "FeatureCollection", "features": [], "numberMatched": 1}
            response = self.client.post('/api/lookup', json={"lat": 50, "lon": 8, "layer": "ba_jobcenter"})
            self.assertEqual(response.status_code, 502)

    def test_nominatim_autocomplete_is_rejected_without_upstream_request(self):
        with patch.object(server.requests, 'get') as get:
            response = self.client.post('/api/geocode', json={"provider": "nominatim", "q": "Mainz", "autocomplete": True})
            self.assertEqual(response.status_code, 400)
            get.assert_not_called()

    def test_photon_normalizes_results(self):
        server._geocode_cache.clear()
        with patch.object(server.requests, 'get') as get, patch.object(server.time, 'sleep'):
            get.return_value.json.return_value = {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": {"type": "Point", "coordinates": [8.27, 50.0]}, "properties": {"name": "Mainz", "country": "Deutschland"}}]}
            response = self.client.post('/api/geocode', json={"provider": "photon", "q": "Mainz", "autocomplete": True})
            self.assertEqual(response.get_json(), [{"label": "Mainz, Deutschland", "lat": 50.0, "lon": 8.27}])

class ServiceSearchTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()

    def test_search_requires_a_valid_municipal_key(self):
        with patch.object(server, 'fetch_json') as fetch:
            response = self.client.post('/api/services', json={'ars': 'bad', 'q': 'Auto anmelden'})
            self.assertEqual(response.status_code, 400)
            fetch.assert_not_called()

    def test_search_never_returns_upstream_markup(self):
        upstream = {'serviceDescriptions': {'content': [{'id': 'L1.LB.1', 'name': '<b>Registration</b>', 'teaser': '<script>evil()</script><p>Official text</p>', 'sourcePortals': [{'title': 'Official', 'uri': 'javascript:alert(1)'}]}]}}
        with patch.object(server, 'fetch_json', return_value=upstream):
            response = self.client.post('/api/services', json={'ars': '073150000000', 'q': 'Auto anmelden'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json['services'][0]['name'], 'Registration')
        self.assertEqual(response.json['services'][0]['teaser'], 'Official text')
        self.assertEqual(response.json['services'][0]['sources'], [])

    def test_municipality_matching_does_not_select_bbox_neighbour(self):
        inside = polygon('Mainz', [[8,49],[9,49],[9,51],[8,51],[8,49]])
        inside['properties'] = {'gen':'Mainz', 'ars':'073150000000', 'lkz':'RP'}
        outside = polygon('Other', [[9,49],[10,49],[10,51],[9,51],[9,49]])
        outside['properties'] = {'gen':'Other', 'ars':'064140000000', 'lkz':'HE'}
        with patch.object(server, 'fetch_json', return_value={'type':'FeatureCollection', 'numberMatched':2, 'features':[inside,outside]}):
            response = self.client.post('/api/municipalities', json={'lat':50,'lon':8.5})
        self.assertEqual([p['name'] for p in response.json['places']], ['Mainz'])

    def test_detail_requires_valid_service_id(self):
        with patch.object(server, 'fetch_json') as fetch:
            response = self.client.post('/api/service-detail', json={'ars':'073150000000','id':'../unsafe'})
            self.assertEqual(response.status_code, 400)
            fetch.assert_not_called()


class ValidationRegressionTests(unittest.TestCase):
    def setUp(self):
        self.client = server.app.test_client()

    def test_non_object_bodies_are_rejected_without_network_requests(self):
        for route in ('geocode', 'municipalities', 'services', 'service-detail', 'lookup'):
            for body in ([1], 'text', None):
                with self.subTest(route=route, body=body), patch.object(server.requests, 'get') as get:
                    response = self.client.post('/api/' + route, json=body)
                    self.assertEqual(response.status_code, 400)
                    get.assert_not_called()

    def test_unpublished_and_nonproduction_online_links_are_excluded(self):
        links = [
            {'uri':'https://example.org/private', 'isPublicDisplayAllowed':False},
            {'uri':'https://example.org/test', 'status':'TEST'},
            {'uri':'javascript:alert(1)'},
            {'uri':'https:missing-host'},
            {'uri':'https://example.org/public', 'status':'PRODUCTION', 'isPublicDisplayAllowed':True},
        ]
        self.assertEqual([x['url'] for x in server.safe_links(links)], ['https://example.org/public'])

    def test_pagination_preserves_remaining_results(self):
        with patch.object(server, 'fetch_json', return_value={'serviceDescriptions':{'content':[], 'last':False}}) as fetch:
            response = self.client.post('/api/services', json={'ars':'073150000000','q':'Pass','page':1})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json['has_more'])
        self.assertEqual(response.json['page'], 1)
        self.assertEqual(fetch.call_args.args[1]['page'], 1)

    def test_invalid_pages_are_rejected(self):
        for page in (-1, 'one', True):
            response = self.client.post('/api/services', json={'ars':'073150000000','q':'Pass','page':page})
            self.assertEqual(response.status_code, 400)

    def test_bad_source_records_become_service_errors(self):
        with patch.object(server, 'fetch_json', return_value={'serviceDescriptions':{'content':['bad record']}}):
            response = self.client.post('/api/services', json={'ars':'073150000000','q':'Pass'})
        self.assertEqual(response.status_code, 502)

    def test_nonpolygon_wfs_feature_cannot_define_jurisdiction(self):
        collection = {'features':[{'geometry':{'type':'Point','coordinates':[8,50]}}]}
        with self.assertRaises(ValueError):
            server.matches_for_point(collection,8,50)

    def test_organisation_outage_preserves_service_and_official_links(self):
        import requests
        service = {'name':'Registration','organisations':[{'id':'L1.OE.1','title':'Authority'}], 'onlineServiceLinks':[{'uri':'https://example.org/apply'}]}
        with patch.object(server, 'fetch_json', side_effect=[service, requests.Timeout()]):
            response = self.client.post('/api/service-detail',json={'ars':'073150000000','id':'L1.LB.1'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json['organizations'][0]['details_unavailable'])
        self.assertEqual(response.json['links'][0]['url'],'https://example.org/apply')

    def test_projected_coordinates_are_not_exposed_as_wgs84(self):
        service = {'name':'Registration','organisations':[{'id':'L1.OE.1','title':'Authority'}]}
        org = {'title':'Authority','location':{'addresses':[{'code':'001','street':'Example','geo':{'system':'EPSG:25832','latitude':'50','longitude':'8'}}]}}
        with patch.object(server, 'fetch_json', side_effect=[service,org]):
            response = self.client.post('/api/service-detail',json={'ars':'073150000000','id':'L1.LB.1'})
        address = response.json['organizations'][0]['addresses'][0]
        self.assertIsNone(address['latitude'])
        self.assertIsNone(address['longitude'])


if __name__ == '__main__':
    unittest.main()
