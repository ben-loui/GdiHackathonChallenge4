import copy
import json
import pytest
from shapely.geometry import shape
from behoerden_resolver.catalog import source
from behoerden_resolver.etl import normalise_feature
from behoerden_resolver.resolver import point_bbox
from behoerden_resolver.wfs import feature_params, parse_page

CRS25833 = {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25833"}}
# ~1 km square near the Berlin city centre in EPSG:25833 (easting/northing).
SQUARE = [[[390000, 5820000], [391000, 5820000], [391000, 5821000], [390000, 5821000], [390000, 5820000]]]


def collection(crs=CRS25833, geometry=None, props=None, fid="c_polizei_abschnitte.11"):
    obj = {"type": "FeatureCollection", "numberMatched": 1,
           "features": [{"type": "Feature", "id": fid,
                         "properties": props or {"langbezeic": "Direktion 1, Abschnitt 11"},
                         "geometry": geometry or {"type": "MultiPolygon", "coordinates": [SQUARE]}}]}
    if crs is not None:
        obj["crs"] = crs
    return json.dumps(obj).encode()


def test_projected_geojson_is_reprojected_to_wgs84():
    s = source("be_polizei_abschnitt")
    page = parse_page(s, collection())
    bounds = shape(page.features[0]["geometry"]).bounds
    assert 13.2 < bounds[0] < bounds[2] < 13.5 and 52.4 < bounds[1] < bounds[3] < 52.6
    assert page.matched == 1


@pytest.mark.parametrize("crs", [None, {"type": "name", "properties": {"name": "urn:ogc:def:crs:EPSG::25832"}},
                                 {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC::CRS84"}}])
def test_projected_geojson_requires_the_declared_crs_member(crs):
    with pytest.raises(ValueError, match="erwartet"):
        parse_page(source("be_polizei_abschnitt"), collection(crs=crs))


def test_geojson_without_geojson_crs_still_demands_crs84():
    with pytest.raises(ValueError, match="CRS84"):
        parse_page(source("bzb_jobcenter"), collection())


def test_request_uses_projected_crs_and_bbox():
    s = source("be_polizei_abschnitt")
    params = feature_params(s, 0, 100)
    assert params["srsName"] == "EPSG:25833" and params["outputFormat"] == "application/json"
    x0, y0, x1, y1, crs = point_bbox(s, 13.3777, 52.5163).split(",")
    assert crs == "EPSG:25833" and 380000 < float(x0) < float(x1) < 400000 and 5.8e6 < float(y0) < float(y1) < 5.83e6


def test_berlin_names_are_composed_without_inventing_departments():
    page = parse_page(source("be_polizei_abschnitt"), collection())
    record = list(normalise_feature(source("be_polizei_abschnitt"), page.features[0]))[0]
    assert record["authority_name"] == "Polizei Berlin, Direktion 1, Abschnitt 11" and record["category"] == "polizei"
    s = source("be_bezirke_gesetz")
    page = parse_page(s, collection(props={"namgem": "Mitte", "gem": "001"}, fid="bezirksgrenzen.11000001"))
    records = list(normalise_feature(s, page.features[0]))
    assert {r["authority_name"] for r in records} == {"Bezirksamt Mitte von Berlin"}
    assert {r["category"] for r in records} == {route["category"] for route in s["routes"]}
    # No citywide competences are routed through the district layer.
    assert not {"auslaenderbehoerde", "zulassungsstelle", "finanzamt"} & {r["category"] for r in records}


def test_statutory_opt_in_source_is_not_queried_live(monkeypatch):
    from behoerden_resolver import db, resolver
    monkeypatch.setattr(resolver, "query_wfs", lambda *a, **k: pytest.fail("opt-in source must not be queried live"))
    monkeypatch.setattr(db, "resolve", lambda *a, **k: {"category": "jugendamt", "status": "no_coverage_at_point", "matches": []})
    result = resolver._resolve_areas("jugendamt", 13.4, 52.5, backend="auto")
    assert result["backend"] == "local"
