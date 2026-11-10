"""A small, read-only bridge to the official BKG WFS and an optional geocoder."""
import os
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse
import threading
import time
import xml.etree.ElementTree as ET

import requests
from flask import Flask, jsonify, request
from shapely import make_valid
from shapely.geometry import Point, shape, mapping
from shapely.errors import ShapelyError

app = Flask(__name__, static_folder="static", static_url_path="")
WFS_URL = "https://sgx.geodatenzentrum.de/wfs_bzb_open"
LAYERS = {
    "ba_arbeitsagenturen", "ba_geschaeftsstellen", "ba_jobcenter",
    "ba_regionaldirektionen", "gerichte_amtsgerichte", "gerichte_landgerichte",
    "gerichte_oberlandesgerichte",
}
# Both services can be switched without changing application code.
NOMINATIM_URL = os.getenv("NOMINATIM_URL", "https://nominatim.openstreetmap.org/search")
PHOTON_URL = os.getenv("PHOTON_URL", "https://photon.komoot.io/api/")
CONTACT = os.getenv("GEOCODER_CONTACT", "https://github.com/KTV02/GdiHackathonChallenge4")
_last_geocode = 0.0
_geocode_lock = threading.Lock()
_geocode_cache = {}


@app.before_request
def validate_api_body():
    if request.method == "POST" and request.path.startswith("/api/"):
        if not isinstance(request.get_json(silent=True), dict):
            return jsonify(error="invalid_query"), 400


@app.get("/")
def index():
    return app.send_static_file("index.html")


@app.get("/api/layers")
def layers():
    # Advertise only layers the application knows how to describe. If the
    # capabilities document is unavailable, use the seven exercise layers.
    try:
        response = requests.get(WFS_URL, params={"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"}, timeout=12)
        response.raise_for_status()
        root = ET.fromstring(response.content)
        names = {node.text.split(":")[-1] for node in root.findall(".//{http://www.opengis.net/wfs/2.0}FeatureType/{http://www.opengis.net/wfs/2.0}Name") if node.text}
        available = sorted(LAYERS & names)
        if not available:
            raise ValueError("No supported layers advertised")
        return jsonify(layers=available, fallback=False)
    except (requests.RequestException, ET.ParseError, ValueError):
        return jsonify(layers=sorted(LAYERS), fallback=True)


@app.post("/api/geocode")
def geocode():
    global _last_geocode
    payload = request.get_json(silent=True) or {}
    query = payload.get("q", "")
    if not isinstance(query, str):
        return jsonify(error="invalid_query"), 400
    query = query.strip()
    provider = payload.get("provider")
    autocomplete = payload.get("autocomplete") is True
    if provider not in ("nominatim", "photon") or not 3 <= len(query) <= 200:
        return jsonify(error="invalid_query"), 400
    if provider == "nominatim" and autocomplete:
        return jsonify(error="autocomplete_not_allowed"), 400
    url = NOMINATIM_URL if provider == "nominatim" else PHOTON_URL
    params = ({"q": query, "format": "jsonv2", "countrycodes": "de", "limit": 5}
              if provider == "nominatim" else {"q": query, "countrycode": "de", "limit": 5})
    key = (provider, query.casefold())
    try:
        # One process only: a public multi-process deployment needs a shared
        # limiter and cache. Never write the address or search results to disk.
        with _geocode_lock:
            now = time.monotonic()
            for old in list(_geocode_cache):
                if now - _geocode_cache[old][0] > 300:
                    del _geocode_cache[old]
            if key in _geocode_cache:
                return jsonify(_geocode_cache[key][1])
            delay = 1.1 - (now - _last_geocode)
            if delay > 0:
                time.sleep(delay)
            try:
                response = requests.get(url, params=params,
                    headers={"User-Agent": f"Zustaendigkeitsfinder-Hackathon/1.0 ({CONTACT})"}, timeout=12)
                response.raise_for_status()
                data = response.json()
            finally:
                _last_geocode = time.monotonic()
            if provider == "nominatim":
                if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
                    raise ValueError("Unexpected Nominatim response")
                results = [{"label": item["display_name"], "lat": float(item["lat"]), "lon": float(item["lon"])} for item in data]
            else:
                if not isinstance(data, dict):
                    raise ValueError("Unexpected Photon response")
                if data.get("type") != "FeatureCollection":
                    raise ValueError("Unexpected Photon response")
                results = []
                for feature in records(data.get("features")):
                    if not isinstance(feature.get("geometry"), dict):
                        raise ValueError("Invalid Photon geometry")
                    props = feature.get("properties", {})
                    if not isinstance(props, dict):
                        raise ValueError("Invalid Photon properties")
                    lon, lat = feature["geometry"]["coordinates"][:2]
                    label = ", ".join(str(props[k]) for k in ("name", "street", "housenumber", "postcode", "city", "state", "country") if props.get(k))
                    results.append({"label": label, "lat": float(lat), "lon": float(lon)})
            results = [item for item in results if 5 <= item["lon"] <= 16 and 47 <= item["lat"] <= 56]
            if len(_geocode_cache) >= 100:
                _geocode_cache.pop(next(iter(_geocode_cache)))
            _geocode_cache[key] = (time.monotonic(), results)
            return jsonify(results)
    except (requests.RequestException, ValueError, TypeError, KeyError, IndexError):
        return jsonify(error="geocoder_unavailable"), 502


def matches_for_point(collection, lon, lat):
    """Return all matches and whether any candidate needed geometry repair."""
    point = Point(lon, lat)
    matches, repaired = [], False
    for feature in records(collection.get("features")):
        if not feature.get("geometry"):
            raise ValueError("A WFS feature has no geometry")
        if not isinstance(feature["geometry"], dict):
            raise ValueError("Invalid WFS geometry")
        geom = shape(feature["geometry"])
        if geom.geom_type not in ("Polygon", "MultiPolygon"):
            raise ValueError("A WFS area must be polygonal")
        if geom.is_empty:
            raise ValueError("A WFS feature has an empty geometry")
        if not geom.is_valid:
            geom = make_valid(geom)
            repaired = True
            if geom.is_empty or not geom.is_valid:
                raise ValueError("Unable to repair WFS geometry")
            # The returned and exported geometry must be the geometry tested.
            feature = {**feature, "geometry": mapping(geom)}
        if geom.covers(point):
            matches.append(feature)
    return matches, repaired


@app.post("/api/lookup")
def lookup():
    payload = request.get_json(silent=True) or {}
    layer = payload.get("layer", "")
    try:
        lon = float(payload["lon"])
        lat = float(payload["lat"])
        if not (5 <= lon <= 16 and 47 <= lat <= 56) or layer not in LAYERS:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        return jsonify(error="invalid_location"), 400
    # CRS84 explicitly uses longitude, latitude, avoiding the EPSG:4326 axis
    # order ambiguity in WFS 2.0. The small box also catches boundary touches.
    epsilon = 0.0001
    crs = "urn:ogc:def:crs:OGC::CRS84"
    bbox = f"{lon-epsilon},{lat-epsilon},{lon+epsilon},{lat+epsilon},{crs}"
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
              "typeNames": "bzb-open:" + layer, "outputFormat": "application/json",
              "srsName": crs, "bbox": bbox, "count": 1000}
    try:
        response = requests.get(WFS_URL, params=params, headers={"User-Agent": "Zustaendigkeitsfinder-Hackathon/1.0"}, timeout=25)
        response.raise_for_status()
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError("Unexpected WFS response")
        if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
            raise ValueError("Unexpected WFS response")
        # Never silently report a potentially incomplete set as authoritative.
        count = data.get("numberMatched", "unknown")
        if (str(count).isdigit() and int(count) > len(data["features"])) or len(data["features"]) >= 1000:
            raise ValueError("WFS results may be truncated")
        matches, repaired = matches_for_point(data, lon, lat)
        return jsonify(type="FeatureCollection", features=matches, geometry_repaired=repaired)
    except (requests.RequestException, ValueError, TypeError, KeyError, ShapelyError):
        return jsonify(error="wfs_unavailable"), 502


PVOG_URL = "https://pvog.fitko.net/suchdienst/api"
VG250_URL = "https://sgx.geodatenzentrum.de/wfs_vg250"
ID_PATTERN = re.compile(r"^[A-Za-z0-9_.-]{1,180}$")


class TextExtractor(HTMLParser):
    """Turn source HTML into text; never forward markup to the browser."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag in ("p", "br", "li", "div", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        elif tag in ("p", "li", "div", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def clean_text(value):
    parser = TextExtractor()
    parser.feed(str(value or ""))
    text = unescape("".join(parser.parts)).replace("\xa0", " ")
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def records(value):
    """Validate a source collection instead of treating malformed data as empty."""
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ValueError("Expected a list of records")
    return value


def safe_links(items):
    result = []
    for item in records(items):
        if item.get("isPublicDisplayAllowed") is False:
            continue
        if item.get("status") and item["status"] != "PRODUCTION":
            continue
        url = item.get("uri", "")
        parsed = urlparse(url) if isinstance(url, str) else None
        if parsed and parsed.scheme in ("http", "https") and parsed.netloc and not parsed.username:
            result.append({"url": url, "title": clean_text(item.get("title") or item.get("name") or url)})
    return result


def fetch_json(url, params):
    response = requests.get(url, params=params, headers={"User-Agent": "Zustaendigkeitsfinder-Hackathon/1.0"}, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("Expected a source object")
    return data


def valid_ars(value):
    return isinstance(value, str) and re.fullmatch(r"[0-9]{12}", value) is not None


@app.post("/api/municipalities")
def municipalities():
    payload = request.get_json(silent=True) or {}
    try:
        lat, lon = float(payload["lat"]), float(payload["lon"])
        if not (47 <= lat <= 56 and 5 <= lon <= 16):
            raise ValueError("Invalid coordinates")
    except (KeyError, TypeError, ValueError):
        return jsonify(error="invalid_location"), 400
    crs = "urn:ogc:def:crs:OGC::CRS84"
    e = 0.0001
    params = {"service": "WFS", "version": "2.0.0", "request": "GetFeature",
              "typeNames": "vg250:vg250_gem", "outputFormat": "application/json", "srsName": crs,
              "bbox": f"{lon-e},{lat-e},{lon+e},{lat+e},{crs}", "count": 1000}
    try:
        data = fetch_json(VG250_URL, params)
        if data.get("type") != "FeatureCollection" or not isinstance(data.get("features"), list):
            raise ValueError("Unexpected WFS response")
        count = data.get("numberMatched", "unknown")
        if (str(count).isdigit() and int(count) > len(data["features"])) or len(data["features"]) >= 1000:
            raise ValueError("Incomplete WFS response")
        features, repaired = matches_for_point(data, lon, lat)
        places = []
        for feature in features:
            props = feature.get("properties") or {}
            if not isinstance(props, dict):
                raise ValueError("Invalid WFS attributes")
            ars = props.get("ars")
            if valid_ars(ars) and not any(place["ars"] == ars for place in places):
                places.append({"ars": ars, "name": str(props.get("gen") or ars), "state": str(props.get("lkz") or "")})
        return jsonify(places=places, geometry_repaired=repaired)
    except (requests.RequestException, ValueError, TypeError, KeyError, ShapelyError):
        return jsonify(error="municipalities_unavailable"), 502


@app.post("/api/services")
def services():
    payload = request.get_json(silent=True) or {}
    query = payload.get("q", "")
    if not isinstance(query, str):
        return jsonify(error="invalid_query"), 400
    query = query.strip()
    ars = payload.get("ars")
    page = payload.get("page", 0)
    if not valid_ars(ars) or not 2 <= len(query) <= 150 or type(page) is not int or not 0 <= page <= 1000:
        return jsonify(error="invalid_query"), 400
    try:
        data = fetch_json(f"{PVOG_URL}/v7/servicedescriptions/{ars}",
                          {"q": query, "size": 8, "page": page, "useArsHierarchy": "true"})
        listing = data["serviceDescriptions"]
        if not isinstance(listing, dict) or not isinstance(listing.get("content"), list):
            raise ValueError("Unexpected service list")
        items = records(listing["content"])
        return jsonify(page=page, has_more=listing.get("last") is False,
                       services=[{"id": item.get("id"), "name": clean_text(item.get("name")),
                                  "teaser": clean_text(item.get("teaser")), "sources": safe_links(item.get("sourcePortals"))} for item in items
                                 if isinstance(item.get("id"), str) and ID_PATTERN.fullmatch(item["id"])])
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return jsonify(error="services_unavailable"), 502


@app.post("/api/service-detail")
def service_detail():
    payload = request.get_json(silent=True) or {}
    ars, service_id = payload.get("ars"), payload.get("id")
    if not valid_ars(ars) or not isinstance(service_id, str) or not ID_PATTERN.fullmatch(service_id):
        return jsonify(error="invalid_query"), 400
    try:
        service = fetch_json(f"{PVOG_URL}/v6/servicedescriptions/{service_id}/detail", {"ars": ars, "useArsHierarchy": "true"})
        if not service.get("name"):
            raise ValueError("Unexpected service detail")
        organisations = records(service.get("organisations"))
        organizations = []
        for item in organisations[:5]:
            org_id = item.get("id")
            if not isinstance(org_id, str) or not ID_PATTERN.fullmatch(org_id):
                continue
            try:
                org = fetch_json(f"{PVOG_URL}/v5/organisationunits/detail", {"q": org_id, "ars": ars, "lbId": service_id})
                location = org.get("location") or {}
                if not isinstance(location, dict):
                    raise ValueError("Invalid organisation location")
                addresses = []
                for address in records(location.get("addresses")):
                    if address.get("code") != "001":
                        continue
                    parts = [" ".join(filter(None, [str(address.get("street") or ""), str(address.get("houseNumber") or "")])),
                             " ".join(filter(None, [str(address.get("zip") or ""), str(address.get("city") or "")]))]
                    coordinates = address.get("geo") or {}
                    if not isinstance(coordinates, dict):
                        raise ValueError("Invalid address coordinates")
                    if coordinates.get("system") not in ("EPSG:4326", "urn:ogc:def:crs:EPSG::4326", "OGC:CRS84"):
                        coordinates = {}
                    addresses.append({"text": ", ".join(p for p in parts if p), "latitude": coordinates.get("latitude"), "longitude": coordinates.get("longitude"), "accessibility": clean_text(address.get("accessible"))})
                info = records(org.get("additionalInformation"))
                hours = [clean_text(entry.get("text")) for entry in info if entry.get("type") == "INFO_TIMES" and entry.get("text")]
                communications = [{"name": clean_text(c.get("name")), "value": clean_text(c.get("value"))} for c in records(location.get("communications")) if c.get("value")]
                organizations.append({"name": clean_text(org.get("title") or item.get("title")),
                    "role": clean_text(item["role"].get("name")) if isinstance(item.get("role"), dict) else "",
                    "description": clean_text(org.get("shortDescription")), "addresses": addresses,
                    "hours": hours, "communications": communications, "links": safe_links(org.get("internetAddresses")) + safe_links(location.get("urls")),
                    "updated": org.get("lastUpdate") if isinstance(org.get("lastUpdate"), str) else None})
            except (requests.RequestException, ValueError, TypeError, KeyError):
                organizations.append({"name": clean_text(item.get("title")), "details_unavailable": True})
        source_portals = safe_links(service.get("sourcePortals"))
        return jsonify(name=clean_text(service.get("name")), organizations=organizations,
                       links=safe_links(service.get("onlineServiceLinks")), sources=source_portals,
                       updated=service.get("externalLastUpdate") if isinstance(service.get("externalLastUpdate"), str) else None,
                       truncated=len(organisations) > 5)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return jsonify(error="details_unavailable"), 502


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
