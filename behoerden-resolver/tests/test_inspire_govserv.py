import pytest
from shapely.geometry import shape
from behoerden_resolver.catalog import source
from behoerden_resolver.inspire_govserv import parse_members

NS = ('xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" '
      'xmlns:us-govserv="http://inspire.ec.europa.eu/schemas/us-govserv/4.0" xmlns:xlink="http://www.w3.org/1999/xlink"')
POLICE = "http://inspire.ec.europa.eu/codelist/ServiceTypeValue/policeService"
OTHER = "http://inspire.ec.europa.eu/codelist/ServiceTypeValue/fireService"
POINT = ('<us-govserv:serviceLocation><us-govserv:ServiceLocationType><us-govserv:serviceLocationByGeometry>'
         '<gml:Point gml:id="{id}_P" srsName="EPSG:25832"><gml:pos>513500 5403500</gml:pos></gml:Point>'
         '</us-govserv:serviceLocationByGeometry></us-govserv:ServiceLocationType></us-govserv:serviceLocation>')
AREA = ('<us-govserv:areaOfResponsibility><us-govserv:AreaOfResponsibilityType><us-govserv:areaOfResponsibilityByPolygon>'
        '<gml:MultiSurface srsName="EPSG:25832"><gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing>'
        '<gml:posList>513000 5403000 514000 5403000 514000 5404000 513000 5404000 513000 5403000</gml:posList>'
        '</gml:LinearRing></gml:exterior></gml:Polygon></gml:surfaceMember></gml:MultiSurface>'
        '</us-govserv:areaOfResponsibilityByPolygon></us-govserv:AreaOfResponsibilityType></us-govserv:areaOfResponsibility>')


def member(key, name, service=POLICE, point=True, area=False):
    return (f'<wfs:member><us-govserv:GovernmentalService gml:id="{key}"><gml:name>{name}</gml:name>'
            f'{POINT.format(id=key) if point else ""}{AREA if area else ""}'
            f'<us-govserv:serviceType xlink:title="x" xlink:href="{service}"/></us-govserv:GovernmentalService></wfs:member>')


def collection(*members):
    return f'<wfs:FeatureCollection {NS} numberMatched="unknown" numberReturned="0">{"".join(members)}</wfs:FeatureCollection>'.encode()


DATA = collection(member("a", "Polizeipräsidium TEST", area=True), member("b", "Polizeirevier TEST"),
                  member("c", "Feuerwache TEST", service=OTHER))


def test_areas_keep_only_explicit_polygons_of_police_services():
    records, audit, total = parse_members(source("bw_polizei_areas"), DATA)
    assert total == 3 and [r["authority_name"] for r in records] == ["Polizeipräsidium TEST"]
    assert audit == {"not_police_service": 1, "no_jurisdiction_polygon": 1}
    bounds = shape(records[0]["geometry"]).bounds
    assert 9 < bounds[0] < bounds[2] < 9.3 and 48.7 < bounds[1] < bounds[3] < 48.9
    assert records[0]["kind"] == "authority" and records[0]["category"] == "polizei"


def test_points_never_become_polygons():
    records, audit, _ = parse_members(source("bw_polizei_locations"), DATA)
    assert {r["authority_name"] for r in records} == {"Polizeipräsidium TEST", "Polizeirevier TEST"}
    assert audit == {"not_police_service": 1}
    assert all(r["kind"] == "authority_point" and r["geometry"]["type"] == "Point" for r in records)


def test_incomplete_or_ambiguous_results_fail_closed():
    s = source("bw_polizei_areas")
    with pytest.raises(ValueError, match="Unvollständig"):
        parse_members(s, DATA, expected=4)
    with pytest.raises(ValueError, match="gml:id"):
        parse_members(s, collection(member("a", "A", area=True), member("a", "B", area=True)))
    with pytest.raises(ValueError, match="Name"):
        parse_members(s, collection(member("a", " ", area=True)))
    with pytest.raises(ValueError, match="Keine verwertbaren"):
        parse_members(s, collection(member("b", "Polizeirevier TEST")))
