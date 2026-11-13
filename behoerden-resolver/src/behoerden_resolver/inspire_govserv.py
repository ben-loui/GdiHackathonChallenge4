"""INSPIRE us-govserv:GovernmentalService WFS (e.g. Polizei Baden-Württemberg).

One feature type carries office locations (serviceLocationByGeometry) and,
for some offices, an official jurisdiction polygon (areaOfResponsibilityByPolygon).
Two sources share one endpoint: ``inspire_govserv_areas`` keeps only features that
carry an explicit polygon, ``inspire_govserv_points`` keeps only office points.
Nothing is derived from other boundaries; incomplete data aborts the import.
"""
import xml.etree.ElementTree as ET
from collections import Counter
from .http import get, request_url
from .locations import point_record
from .supplements import base_record, write_snapshot
from .wfs import GML, gml_geometry, gml_point, numeric, xml

XLINK = "{http://www.w3.org/1999/xlink}"
POLICE = "http://inspire.ec.europa.eu/codelist/ServiceTypeValue/policeService"


def request_params(s, **extra):
    return {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
            "typeNames": s["layer"], "srsName": s["request_crs"], **extra}


def split_members(root):
    members = root.findall("{*}member")
    keys = [m[0].get(GML + "id") for m in members if len(m) == 1]
    if len(keys) != len(members) or not all(keys) or len(set(keys)) != len(keys):
        raise ValueError("INSPIRE-Mitglieder ohne eindeutige gml:id")
    return [m[0] for m in members]


def parse_members(s, data, expected=None):
    """Yield authority/authority_point records for one GetFeature response."""
    root = xml(data)
    if not root.tag.endswith("FeatureCollection"):
        raise ValueError("Keine GML FeatureCollection")
    members = split_members(root)
    if not members:
        raise ValueError("Leere INSPIRE-Antwort")
    if expected is not None and len(members) != expected:
        raise ValueError(f"Unvollständiger Abzug: {len(members)} statt {expected}")
    audit = Counter()
    records = []
    for item in members:
        key = item.get(GML + "id")
        name = (item.findtext(GML + "name") or "").strip()
        service = item.find("{*}serviceType")
        if service is None or service.get(XLINK + "href") != POLICE:
            audit["not_police_service"] += 1
            continue
        if not name:
            raise ValueError(f"Amtlicher Name fehlt: {key}")
        props = {"source_record_xml": ET.tostring(item, encoding="unicode"), "service_type": POLICE,
                 "source_quality": "official"}
        if s["kind"] == "authority":
            polygon = item.find(".//{*}areaOfResponsibilityByPolygon")
            if polygon is None:
                audit["no_jurisdiction_polygon"] += 1
                continue
            props["geometry_completeness"] = "official_source_polygon"
            records.append(base_record(s, key, name, gml_geometry(polygon, s["request_crs"]), props))
        else:
            location = item.find(".//{*}serviceLocationByGeometry")
            if location is None:
                audit["no_service_location"] += 1
                continue
            props["geometry_completeness"] = "location_only_no_jurisdiction_polygon"
            records.append(point_record(s, s["routes"][0]["category"], key, name,
                                        gml_point(location, s["request_crs"]), props))
    if not records:
        raise ValueError("Keine verwertbaren Datensätze")
    return records, dict(audit), len(members)


def import_inspire_govserv(s, directory, fetch=get):
    hits_url = request_url(s["endpoint"], request_params(s, resultType="hits"))
    hits = fetch(hits_url)
    matched = numeric(xml(hits).get("numberMatched"))
    url = request_url(s["endpoint"], request_params(s))
    data = fetch(url)
    records, audit, total = parse_members(s, data, matched)
    return write_snapshot(s, directory, iter(records),
                          {"classification_audit": audit, "observed_features": total, "expected_features": matched,
                           "completeness_check": "member_count_equals_resultType_hits" if matched is not None
                                                 else "unverifiable_numberMatched_unknown",
                           "pagination_consistency": "single unpaged GetFeature; member count compared with resultType=hits when numeric"},
                          [("hits", hits_url, hits), ("source", url, data)])
