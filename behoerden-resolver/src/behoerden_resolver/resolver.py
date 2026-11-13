"""Category + WGS84 point -> complete records from live WFS or local PostGIS."""
import math
import json
from pyproj import Transformer
from shapely.geometry import Point, shape
from . import db
from .catalog import category, sources, resource
from .etl import normalise_feature, now
from .http import get, request_url
from .wfs import CRS84, feature_params, parse_page


def complete_response(result):
    for r in result.get('matches',[]):
        r['geometry_completeness']=r['properties'].get('geometry_completeness','official_source_or_documented_derived_polygon')
    return result


def point_bbox(s, lon, lat):
    if s["request_crs"] == CRS84:
        x, y, delta = lon, lat, 0.000001
    else:
        x, y = Transformer.from_crs("EPSG:4326", s["request_crs"], always_xy=True).transform(lon, lat)
        delta = 1.0
    return ",".join([*(format(v, ".9f") for v in (x-delta,y-delta,x+delta,y+delta)), s["request_crs"]])


def within_routing_envelope(s,lon,lat):
    if s['scope']=='DE':return True
    extents=json.loads(resource('routing.json').read_text(encoding='utf-8'))['state_envelopes']
    for scope in s['scope'].split('|'):
        if scope not in extents:return True
        x0,y0,x1,y1=extents[scope]
        if x0-0.02<=lon<=x1+0.02 and y0-0.02<=lat<=y1+0.02:return True
    return False


def query_wfs(s, code, lon, lat, fetch=get, page_size=100):
    """BBOX selects candidates only; covers checks full polygons, including holes."""
    if s["kind"] != "authority" or s.get("active") is False or s["format"] not in ("geojson", "gml"):
        raise ValueError("Quelle ist kein verwendbarer Behördengebiets-WFS")
    seen, matches, urls, expected, offset = set(), [], [], None, 0
    point = Point(lon, lat)
    while True:
        params = feature_params(s, offset, page_size)
        params["bbox"] = point_bbox(s, lon, lat)
        url = request_url(s["endpoint"], params)
        page = parse_page(s, fetch(url))
        urls.append(url)
        if page.matched is not None:
            if expected is not None and expected != page.matched:
                raise ValueError("WFS-Trefferzahl änderte sich während der Abfrage")
            expected = page.matched
        if not page.features:
            break
        for feature in page.features:
            key = feature.get("id")
            if key is None or str(key) in seen:
                raise ValueError("WFS-Paging lieferte fehlende oder wiederholte IDs")
            seen.add(str(key))
            for record in normalise_feature(s, feature):
                if record["category"] != code:
                    continue
                polygon = shape(record["geometry"])
                if polygon.covers(point):
                    record.pop("area_name", None)
                    matches.append({**record, "license": s["license"], "attribution": s["attribution"],
                                    "fetched_at": now(), "on_boundary": polygon.touches(point),
                                    "run_id": None})
        offset += len(page.features)
        if expected is not None and offset >= expected:
            break
        if offset >= 10000:
            raise ValueError("Zu viele WFS-Kandidaten für eine Punktabfrage")
    if expected is not None and expected != offset:
        raise ValueError(f"Unvollständige WFS-Antwort: {offset} statt {expected}")
    return matches, {"source_id": s["id"], "endpoint": s["endpoint"], "layer": s["layer"],
                     "request_urls": urls, "candidate_count": offset, "match_count": len(matches)}


def _resolve_areas(value, lon, lat, dsn=None, backend="auto", fetch=get):
    c = category(value)
    lon, lat = float(lon), float(lat)
    if not math.isfinite(lon) or not math.isfinite(lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Koordinaten müssen endliche WGS84-Werte sein (lon, lat)")
    if backend not in ("auto", "local", "wfs"):
        raise ValueError("Backend muss auto, local oder wfs sein")
    # Statutory sources flagged for legal review are opt-in: never queried live,
    # only served from the database after an explicit `fetch/sync --all`.
    available = [s for s in sources() if s.get("active") is not False and s["kind"] == "authority"
                 and not (s.get("legal_review_required") and s.get("default_import") is False)
                 and any(r["category"] == c["id"] for r in s["routes"])]
    if c['resolution_mode']=='non_spatial' or (c['resolution_mode']=='context_required' and not available):
        return {**db.resolve(c["id"],lon,lat,dsn), "backend": None, "requested_backend": backend}
    remote_all = [s for s in available if s["format"] in ("geojson", "gml")]
    remote = [s for s in remote_all if within_routing_envelope(s,lon,lat)]
    local_only = [s for s in available if s not in remote_all]
    if backend == "local" or (backend == "auto" and not remote_all):
        return complete_response({**db.resolve(c["id"],lon,lat,dsn), "backend": "local", "requested_backend": backend})
    if not remote_all:
        raise ValueError("Kein Behördengebiets-WFS für diese Kategorie; lokale Abfrage verwenden. VG25 ist nur eine Grenzreferenz.")
    matches, queried = [], []
    for s in remote:
        try:
            rows, evidence = query_wfs(s,c["id"],lon,lat,fetch)
        except Exception as exc:
            # Never pass off an old cache as a successful live result.
            raise RuntimeError(f"WFS-Abfrage {s['id']} fehlgeschlagen: {exc}") from exc
        matches.extend(rows)
        queried.append(evidence)
    if not matches and backend == "auto" and local_only:
        result = db.resolve(c["id"],lon,lat,dsn,exclude_sources=[s["id"] for s in remote_all])
        return complete_response({**result, "backend": "local", "requested_backend": backend, "wfs_queries": queried})
    matches.sort(key=lambda r:(r["authority_name"],r["source_id"],r["source_key"]))
    return complete_response({"category": c["id"], "point": {"lon":lon,"lat":lat}, "backend": "wfs",
            "requested_backend": backend, "status": "candidate" if len(matches)==1 else "ambiguous" if matches else "no_coverage_at_point",
            "matches": matches, "wfs_queries": queried, "limitations": c["limitations"],
            "national_coverage_guaranteed": False,
            "match_semantics": "general territorial candidates; category and point do not establish case-specific legal competence"})


def resolve(value,lon,lat,dsn=None,backend='auto',fetch=get,point_fallback=True,radius_km=None,point_limit=3):
    c=category(value)
    radii=json.loads(resource('fallback.json').read_text(encoding='utf-8'))
    radius=float(radius_km) if radius_km is not None else radii['category_radius_km'].get(c['id'],radii['default_radius_km'])
    if not math.isfinite(radius) or not 0<radius<=300:raise ValueError('Punktsuchradius muss größer 0 und höchstens 300 km sein')
    if not 1<=point_limit<=10:raise ValueError('Anzahl Punktvorschläge muss zwischen 1 und 10 liegen')
    result=_resolve_areas(value,lon,lat,dsn,backend,fetch)
    needs_context=c['resolution_mode'] in ('non_spatial','context_required')
    result.update(requires_case_context=needs_context,data_status='no_geometry_match')
    if needs_context:
        result.update(status=c['resolution_mode'],required_context=c['limitations'])
    # Even an explicitly requested live-only area search must not turn a known
    # local supplement into a point suggestion. Check those areas before fallback.
    if not result['matches'] and backend=='wfs' and point_fallback:
        remote_ids=[s['id'] for s in sources() if s.get('active') is not False
                    and s['kind']=='authority' and s['format'] in ('geojson','gml')]
        local=complete_response(db.resolve(c['id'],lon,lat,dsn,exclude_sources=remote_ids))
        if local['matches']:
            result={**local,'backend':'local','requested_backend':backend,
                    'wfs_queries':result.get('wfs_queries',[]),'fallback_area_check':True,
                    'requires_case_context':needs_context}
    if result['matches']:
        for row in result['matches']:
            row.update(match_type='polygon_cover',territorial_match_verified=True,case_competence_verified=False)
        return {**result,'fallback_used':False,'data_status':'polygon_match'}
    points_configured=any(s['kind']=='authority_point' and s.get('active') is not False
                          and any(r['category']==c['id'] for r in s['routes']) for s in sources())
    if not point_fallback or not points_configured:return {**result,'fallback_used':False}
    nearby=db.nearby(c['id'],lon,lat,radius_km=radius,limit=point_limit,dsn=dsn)
    if not nearby:return {**result,'fallback_used':False,'point_search':{'radius_km':radius,'count':0}}
    previous=result['status']
    status=previous if previous in ('non_spatial','context_required') else 'nearby_candidate' if len(nearby)==1 else 'nearby_candidates'
    return {**result,'status':status,'matches':nearby,'backend':'local_point_fallback','fallback_used':True,
            'data_status':'nearby_location_match',
            'area_search_status':previous,'point_search':{'radius_km':radius,'count':len(nearby),'limit':point_limit},
            'fallback_reason':'This category has no exclusive residence-based jurisdiction; nearby contact only.' if c['resolution_mode']=='non_spatial' else 'No matching jurisdiction polygon was found among the integrated sources.',
            'warning':'Nahegelegener Standort. Zuständigkeit nicht durch eine Fläche belegt; Nähe begründet keine fachliche oder persönliche Zuständigkeit.'}
