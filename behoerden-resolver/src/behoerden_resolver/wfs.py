"""Strict adapters for the verified BKG GeoJSON and Bavarian GML 3.2 services."""
import json
import math
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pyproj import CRS, Transformer
from shapely import MultiPolygon, Polygon, make_valid, transform, union_all
from shapely.geometry import mapping, shape
from .http import get, request_url

GML = "{http://www.opengis.net/gml/3.2}"
CRS84 = "urn:ogc:def:crs:OGC::CRS84"


@dataclass
class Page:
    features: list
    matched: int | None


def xml(data):
    root = ET.fromstring(data)
    if root.tag.split("}")[-1] in ("ExceptionReport", "ServiceExceptionReport"):
        raise ValueError("WFS exception: " + " ".join(root.itertext())[:1000])
    return root


def numeric(value):
    return int(value) if str(value).isdigit() else None


def capabilities(data):
    root = xml(data)
    if not root.tag.endswith("WFS_Capabilities"):
        raise ValueError("Keine WFS-Capabilities")
    return {f.findtext("{*}Name"): {"title": f.findtext("{*}Title"),
                "crs": [e.text for e in f if e.tag.endswith(("DefaultCRS", "OtherCRS"))]}
            for f in root.findall(".//{*}FeatureType")}


def feature_params(s, start=0, count=100):
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
              "typeNames": s["layer"], "srsName": s["request_crs"],
              "startIndex": start, "count": count, "sortBy": s["sort_by"]}
    if s["format"] == "geojson":
        params["outputFormat"] = "application/json"
    return params


def ring(element):
    positions = element.findall(".//" + GML + "posList")
    if len(positions) != 1:
        raise ValueError("Erwartet: genau eine GML posList pro LinearRing")
    pos = positions[0]
    if pos.get("srsDimension", "2") != "2":
        raise ValueError("Nur zweidimensionale Flächen werden unterstützt")
    values = [float(v) for v in (pos.text or "").split()]
    if len(values) < 8 or len(values) % 2 or not all(math.isfinite(v) for v in values):
        raise ValueError("Ungültiger GML-Ring")
    coordinates = list(zip(values[::2], values[1::2]))
    if coordinates[0] != coordinates[-1]:
        raise ValueError("Offener GML-Ring")
    return coordinates


def gml_geometry(element, requested_crs):
    geometry = list(element)
    if len(geometry) != 1 or geometry[0].tag not in (GML + "MultiSurface", GML + "Polygon"):
        raise ValueError("Nur GML MultiSurface/Polygon unterstützt; keine stille Näherung")
    root = geometry[0]
    def same_crs(value):
        return CRS.from_user_input(value) == CRS.from_user_input(requested_crs)
    for e in root.iter():
        if e.get("srsName") and not same_crs(e.get("srsName")):
            raise ValueError(f"Unerwartetes Quell-CRS: {e.get('srsName')}")
        if e.get("srsDimension", "2") != "2":
            raise ValueError("GML-Dimension nicht 2")
    # Only explicitly supported projected XY CRSs; no EPSG:4326 axis guessing.
    if requested_crs not in ("EPSG:3857", "EPSG:25832", "EPSG:25833") or not root.get("srsName") or not same_crs(root.get("srsName")):
        raise ValueError("GML-Adapter benötigt ein explizites unterstütztes projiziertes CRS")
    polygons = [root] if root.tag == GML + "Polygon" else root.findall("./" + GML + "surfaceMember/" + GML + "Polygon")
    if not polygons or (root.tag == GML + "MultiSurface" and len(polygons) != len(list(root))):
        raise ValueError("Nicht unterstützte GML-Flächenstruktur")
    parts = []
    for polygon in polygons:
        exterior = polygon.find(GML + "exterior")
        if exterior is None:
            raise ValueError("GML-Polygon ohne Außenring")
        parts.append(Polygon(ring(exterior), [ring(e) for e in polygon.findall(GML + "interior")]))
    projection = Transformer.from_crs(requested_crs, "EPSG:4326", always_xy=True)
    return mapping(transform(MultiPolygon(parts), projection.transform, interleaved=False))


PROJECTED_GEOJSON_CRS = ("EPSG:3857", "EPSG:25832", "EPSG:25833")


def reproject_geojson(geometry, source_crs):
    """Reproject an XY GeoJSON geometry from a supported projected CRS to CRS84; no simplification."""
    if not isinstance(geometry, dict) or geometry.get("type") not in ("Polygon", "MultiPolygon", "Point"):
        raise ValueError("Nur Polygon/MultiPolygon/Point-GeoJSON unterstützt")
    projection = Transformer.from_crs(source_crs, "EPSG:4326", always_xy=True)
    def convert(value):
        if value and isinstance(value[0], (int, float)):
            if len(value) not in (2, 3) or not all(math.isfinite(v) for v in value):
                raise ValueError("Ungültige GeoJSON-Koordinate")
            lon, lat = projection.transform(value[0], value[1])
            return [lon, lat]
        return [convert(v) for v in value]
    return {"type": geometry["type"], "coordinates": convert(geometry["coordinates"])}


def parse_page(s, data):
    if s["format"] == "geojson":
        try:
            obj = json.loads(data)
        except (ValueError, UnicodeDecodeError):
            xml(data)  # Surface service exceptions, not a misleading JSON error.
            raise ValueError("WFS hat kein GeoJSON geliefert")
        if obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
            raise ValueError("Keine GeoJSON FeatureCollection")
        crs = obj.get("crs", {}).get("properties", {}).get("name")
        if s.get("geojson_crs"):
            # Projected GeoJSON (e.g. GeoServer with srsName=EPSG:25833): the crs member is
            # mandatory and must equal the declared CRS; coordinates are then reprojected.
            if s["geojson_crs"] not in PROJECTED_GEOJSON_CRS:
                raise ValueError("Nicht unterstütztes geojson_crs")
            if not crs or CRS.from_user_input(crs) != CRS.from_user_input(s["geojson_crs"]):
                raise ValueError(f"{s['geojson_crs']} erwartet, aber {crs} geliefert")
            for feature in obj["features"]:
                if isinstance(feature, dict) and feature.get("geometry") is not None:
                    feature["geometry"] = reproject_geojson(feature["geometry"], s["geojson_crs"])
        elif crs not in (None, CRS84, "urn:ogc:def:crs:CRS::84", "OGC:CRS84"):
            raise ValueError(f"CRS84 angefordert, aber {crs} geliefert")
        return Page(obj["features"], numeric(obj.get("numberMatched")))
    root = xml(data)
    if not root.tag.endswith("FeatureCollection"):
        raise ValueError("Keine GML FeatureCollection")
    features = []
    for member in root.findall("{*}member"):
        if len(member) != 1:
            raise ValueError("Ungültiges GML member")
        item = member[0]
        geom_field = s.get("geometry_field", "geometry")
        props = {e.tag.split("}")[-1]: e.text for e in item if e.tag.split("}")[-1] != geom_field}
        geom = item.find("{*}" + geom_field)
        if geom is None:
            raise ValueError("Fehlende Geometrie")
        # An institution id can repeat for different spatial parts (e.g. islands).
        # The WFS gml:id identifies the actual feature used for paging checks.
        value = gml_point(geom,s['request_crs']) if s['kind']=='authority_point' else gml_geometry(geom, s["request_crs"])
        features.append({"type": "Feature", "id": item.get(GML + "id"), "properties": props,"geometry":value})
    # deegree can report numberReturned=0 even when members exist. Count members.
    return Page(features, numeric(root.get("numberMatched")))


def validated_point(value):
    if not isinstance(value,dict) or value.get('type')!='Point':raise ValueError('Standort muss ein Punkt sein')
    coordinates=value.get('coordinates',[])
    if len(coordinates) not in (2,3):raise ValueError('Ungültiger Standort')
    lon,lat=map(float,coordinates[:2])
    if not math.isfinite(lon) or not math.isfinite(lat) or not (0<lon<25 and 40<lat<60):
        raise ValueError('Standort außerhalb plausibler deutscher WGS84-Grenzen')
    return {'type':'Point','coordinates':[lon,lat]}


def gml_point(element,requested_crs):
    points=element.findall('.//'+GML+'Point')
    if len(points)!=1:raise ValueError('GML-Standort muss genau einen Point enthalten')
    point=points[0]
    crs=point.get('srsName') or (element[0].get('srsName') if len(element) else None)
    if not crs or CRS.from_user_input(crs)!=CRS.from_user_input(requested_crs):raise ValueError('Unerwartetes Standort-CRS')
    if requested_crs not in ('EPSG:3857','EPSG:25832','EPSG:25833'):raise ValueError('Standort-CRS nicht unterstützt')
    coords=[float(v) for v in (point.findtext(GML+'pos') or '').split()]
    if len(coords) not in (2,3):raise ValueError('Ungültige GML-Punktkoordinaten')
    lon,lat=Transformer.from_crs(requested_crs,'EPSG:4326',always_xy=True).transform(*coords[:2])
    return validated_point({'type':'Point','coordinates':[lon,lat]})


def validated_geometry(value):
    geometry = shape(value)
    if geometry.geom_type not in ("Polygon", "MultiPolygon") or geometry.is_empty:
        raise ValueError("Behördengebiet muss Polygon/MultiPolygon sein")
    repaired = not geometry.is_valid
    if repaired:
        geometry = make_valid(geometry)
        if geometry.geom_type == "GeometryCollection":
            def polygons(g):
                if g.geom_type == "Polygon":
                    yield g
                elif hasattr(g, "geoms"):
                    for part in g.geoms:
                        yield from polygons(part)
            # make_valid may leave collapsed (zero-area) boundary lines/points.
            # Keep ALL polygon parts; never buffer/simplify or invent area.
            parts = list(polygons(geometry))
            if not parts:
                raise ValueError("Reparatur enthält keine Fläche")
            geometry = union_all(parts)
    if geometry.geom_type == "Polygon":
        geometry = MultiPolygon([geometry])
    if geometry.geom_type != "MultiPolygon" or geometry.is_empty or not geometry.is_valid:
        raise ValueError("Fläche nach Reparatur nicht verwendbar; Import abgebrochen")
    bounds = geometry.bounds
    if not all(math.isfinite(v) for v in bounds) or not (0 < bounds[0] < bounds[2] < 25 and 40 < bounds[1] < bounds[3] < 60):
        raise ValueError("Geometrie außerhalb plausibler deutscher CRS84-Grenzen")
    return mapping(geometry), repaired


def verify_source(s, fetch=get):
    cap_url = request_url(s["endpoint"], {"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"})
    cap = fetch(cap_url)
    layers = capabilities(cap)
    if s["layer"] not in layers:
        raise ValueError(f"Layer fehlt: {s['layer']}")
    desc_url = request_url(s["endpoint"], {"service": "WFS", "version": "2.0.0", "request": "DescribeFeatureType", "typeNames": s["layer"]})
    desc = fetch(desc_url)
    schema = xml(desc)
    if schema.tag != "{http://www.w3.org/2001/XMLSchema}schema":
        raise ValueError("DescribeFeatureType lieferte kein XML-Schema")
    sample_url = request_url(s["endpoint"], feature_params(s, count=1))
    sample = fetch(sample_url)
    page = parse_page(s, sample)
    if not page.features:
        raise ValueError("Leerer Live-Test; Layer nicht als nutzbar verifiziert")
    if s['kind']=='authority_point':validated_point(page.features[0]['geometry'])
    else:validated_geometry(page.features[0]["geometry"])
    return {"capabilities": (cap_url, cap), "schema": (desc_url, desc), "sample": (sample_url, sample)}
