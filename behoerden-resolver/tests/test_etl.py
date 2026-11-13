import copy
import gzip
import json
from urllib.parse import parse_qs, urlsplit
import pytest
from shapely.geometry import shape
from behoerden_resolver.catalog import source
from behoerden_resolver.etl import fetch_source, normalise_feature, read_manifest
from behoerden_resolver.wfs import parse_page, validated_geometry


def feature(key="one", name="SYNTHETIC TEST AUTHORITY"):
    return {"type": "Feature", "id": key, "properties": {"name": name},
            "geometry": {"type": "Polygon", "coordinates": [[[8,49],[9,49],[9,50],[8,50],[8,49]]]}}


def fake_service(pages):
    s = source("bzb_jobcenter")
    def get(url):
        params = parse_qs(urlsplit(url).query)
        request = params["request"][0]
        if request == "GetCapabilities":
            return f'<WFS_Capabilities><FeatureTypeList><FeatureType><Name>{s["layer"]}</Name></FeatureType></FeatureTypeList></WFS_Capabilities>'.encode()
        if request == "DescribeFeatureType":
            return b'<xsd:schema xmlns:xsd="http://www.w3.org/2001/XMLSchema"/>'
        if params["count"] == ["1"]:
            return json.dumps({"type":"FeatureCollection","features":[feature()]}).encode()
        offset = int(params["startIndex"][0])
        features, matched = pages[offset]
        return json.dumps({"type":"FeatureCollection","features":features,"numberMatched":matched}).encode()
    return s, get


def test_paging_uses_actual_count_and_continues_after_short_page(tmp_path):
    s, get = fake_service({0:([feature("one")],"unknown"),1:([feature("two")],"unknown"),2:([],"unknown")})
    result = fetch_source(s,tmp_path,page_size=20,fetch=get)
    manifest = read_manifest(result)
    assert manifest["observed_features"] == 2
    assert manifest["terminal_empty_page"] is True
    assert manifest["records_per_category"] == {"jobcenter":2}
    with gzip.open(result/'records.jsonl.gz','rt') as stream:
        assert len(list(stream)) == 2


@pytest.mark.parametrize("pages", [
    {0:([feature()],2),1:([],2)},
    {0:([feature()],"unknown"),1:([feature()],"unknown")},
    {0:([feature()],2),1:([feature("two")],3)},
])
def test_incomplete_duplicate_or_changing_pages_never_publish_snapshot(tmp_path,pages):
    s, get = fake_service(pages)
    with pytest.raises(ValueError):
        fetch_source(s,tmp_path,page_size=20,fetch=get)
    assert not list(tmp_path.iterdir())


def test_checksum_failure(tmp_path):
    s,get=fake_service({0:([feature()],1)})
    path=fetch_source(s,tmp_path,page_size=20,fetch=get)
    with (path/'records.jsonl.gz').open('ab') as stream:
        stream.write(b'bad')
    with pytest.raises(ValueError,match="Prüfsumme"):
        read_manifest(path)


def test_gml_actual_members_holes_and_axis_order():
    s=source('by_kreis')
    gml=b'''<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" xmlns:gml="http://www.opengis.net/gml/3.2" xmlns:s="urn:test" numberReturned="0" numberMatched="unknown"><wfs:member><s:Test><s:id>1</s:id><s:bezeichnung>TEST</s:bezeichnung><s:geometry><gml:MultiSurface srsName="EPSG:3857"><gml:surfaceMember><gml:Polygon><gml:exterior><gml:LinearRing><gml:posList>900000 6300000 1000000 6300000 1000000 6400000 900000 6400000 900000 6300000</gml:posList></gml:LinearRing></gml:exterior><gml:interior><gml:LinearRing><gml:posList>920000 6320000 930000 6320000 930000 6330000 920000 6330000 920000 6320000</gml:posList></gml:LinearRing></gml:interior></gml:Polygon></gml:surfaceMember></gml:MultiSurface></s:geometry></s:Test></wfs:member></wfs:FeatureCollection>'''
    page=parse_page(s,gml)
    assert len(page.features)==1 and page.matched is None
    polygon=shape(page.features[0]['geometry']).geoms[0]
    assert len(polygon.interiors)==1
    assert 8 < polygon.bounds[0] < 9 and 49 < polygon.bounds[1] < 50
    with pytest.raises(ValueError,match="CRS"):
        parse_page(s,gml.replace(b'EPSG:3857',b'EPSG:4326'))


def test_exceptions_and_wrong_crs_fail_closed():
    with pytest.raises(ValueError,match="exception"):
        parse_page(source('bzb_jobcenter'),b'<ExceptionReport><Exception>broken</Exception></ExceptionReport>')
    with pytest.raises(ValueError,match="CRS84"):
        parse_page(source('bzb_jobcenter'),json.dumps({"type":"FeatureCollection","features":[],"crs":{"properties":{"name":"EPSG:4326"}}}).encode())
    for geometry in ({"type":"Point","coordinates":[8,50]}, {"type":"Polygon","coordinates":[[[49,8],[50,8],[50,9],[49,9],[49,8]]]}):
        with pytest.raises(ValueError):
            validated_geometry(geometry)


def test_combined_court_layer_does_not_turn_other_institutions_into_courts():
    s=source('by_verwaltungsgericht')
    f=feature()
    f['properties']={'bezeichnung':'Bayerischer Verwaltungsgerichtshof','behoerdenUntergruppe':'verwaltungsgerichtshof'}
    assert list(normalise_feature(s,f))==[]
    f['properties']={'bezeichnung':'Bayerisches Verwaltungsgericht TEST','behoerdenUntergruppe':'verwaltungsgerichte'}
    assert list(normalise_feature(s,f))[0]['authority_name']=='Bayerisches Verwaltungsgericht TEST'


def test_vg25_and_explicit_name_composition():
    f=feature(); f['properties']={'gen':'TEST AREA'}
    record=list(normalise_feature(source('vg25_krs'),f))[0]
    assert record['authority_name'] is None and record['area_name']=='TEST AREA'
    f['properties']={'bezeichnung':'TEST','bezeichnungZusatz':'Landratsamt','behoerdenUntergruppe':'landratsaemter'}
    record=list(normalise_feature(source('by_kreis'),f))[0]
    assert record['authority_name']=='Landratsamt TEST'
    f['properties'].pop('bezeichnungZusatz')
    with pytest.raises(ValueError,match="Namenszusatz"):
        list(normalise_feature(source('by_kreis'),f))


def test_repair_keeps_polygon_area_and_removes_collapsed_line_only():
    # A square with a zero-area spike into its interior; make_valid yields a
    # GeometryCollection(Polygon, LineString). No polygon portion may be lost.
    geometry={'type':'Polygon','coordinates':[[[8,49],[9,49],[9,50],[8,50],[8,49.5],[8.5,49.5],[8,49.5],[8,49]]]}
    value,repaired=validated_geometry(geometry)
    assert repaired and shape(value).is_valid
    assert shape(value).area==pytest.approx(1.0)
