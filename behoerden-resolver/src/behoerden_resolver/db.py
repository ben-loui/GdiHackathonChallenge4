import gzip
import json
import math
import os
from collections import Counter
from pathlib import Path
import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from .catalog import categories, category, plan, resource, source, sources
from .etl import read_manifest

DEFAULT_DSN = "postgresql://resolver:resolver-local@127.0.0.1:55432/authorities"


def connect(dsn=None):
    return psycopg.connect(dsn or os.environ.get("DATABASE_URL", DEFAULT_DSN), row_factory=dict_row)


def init(dsn=None):
    with connect(dsn) as conn:
        conn.execute(resource("schema.sql").read_text(encoding="utf-8"))
        for c in categories():
            conn.execute("INSERT INTO behoerden.categories VALUES (%s,%s) ON CONFLICT(id) DO UPDATE SET metadata=excluded.metadata", (c["id"], Jsonb(c)))
            conn.execute(sql.SQL("CREATE TABLE IF NOT EXISTS behoerden.{} PARTITION OF behoerden.authorities FOR VALUES IN ({})").format(sql.Identifier(c["id"]), sql.Literal(c["id"])))
        for s in sources():
            conn.execute("INSERT INTO behoerden.sources VALUES (%s,%s) ON CONFLICT(id) DO UPDATE SET metadata=excluded.metadata", (s["id"], Jsonb(s)))


def load_snapshot(path, dsn=None):
    path = Path(path)
    manifest = read_manifest(path)
    s = source(manifest["source"]["id"])
    if s.get("active") is False:
        raise ValueError(s["exclusion_reason"])
    # An old snapshot cannot silently acquire a new meaning after a mapping change.
    if manifest["source"] != s:
        raise ValueError("Quellkonfiguration hat sich geändert; Snapshot erneut abrufen oder alte Projektversion verwenden")
    counted = Counter()
    with connect(dsn) as conn:
        # Serialise replacement for this source; readers see either complete version.
        conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (s["id"],))
        row = conn.execute("INSERT INTO behoerden.import_runs(source_id,manifest,record_count) VALUES(%s,%s,0) RETURNING run_id", (s["id"], Jsonb(manifest))).fetchone()
        run = row["run_id"]
        conn.execute("DELETE FROM behoerden.authorities WHERE source_id=%s", (s["id"],))
        conn.execute("DELETE FROM behoerden.boundaries WHERE source_id=%s", (s["id"],))
        conn.execute("DELETE FROM behoerden.locations WHERE source_id=%s", (s["id"],))
        # The transaction also rolls the deletes back on any invalid feature.
        with gzip.open(path / "records.jsonl.gz", "rt", encoding="utf-8") as stream:
            for line in stream:
                r = json.loads(line)
                if r["source_id"] != s["id"] or r["kind"] != s["kind"] or r["category"] not in {route["category"] for route in s["routes"]}:
                    raise ValueError("Snapshot enthält falsche Quelle/Kategorie/Geometrieart")
                geom = json.dumps(r["geometry"])
                if r["kind"] == "authority":
                    conn.execute("""INSERT INTO behoerden.authorities
                      (category,source_id,source_key,authority_name,geom,geometry_repaired,properties,scope,source_date,evidence_url,name_rule,run_id)
                      VALUES (%s,%s,%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s,%s,%s,%s,%s,%s,%s)""",
                      (r["category"],s["id"],r["source_key"],r["authority_name"],geom,r["geometry_repaired"],Jsonb(r["properties"]),r["scope"],r["source_date"],r["evidence_url"],Jsonb(r["name_rule"]),run))
                elif r['kind']=='authority_point':
                    conn.execute("""INSERT INTO behoerden.locations
                      VALUES (%s,%s,%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s,%s,%s,%s,%s,%s)""",
                      (r['category'],s['id'],r['source_key'],r['authority_name'],geom,Jsonb(r['properties']),r['scope'],r['source_date'],r['evidence_url'],Jsonb(r['name_rule']),run))
                else:
                    conn.execute("""INSERT INTO behoerden.boundaries
                      VALUES (%s,%s,%s,%s,ST_SetSRID(ST_GeomFromGeoJSON(%s),4326),%s,%s,%s)""",
                      (r["category"],s["id"],r["source_key"],r["area_name"],geom,Jsonb(r["properties"]),r["geometry_repaired"],run))
                counted[r["category"]] += 1
        if dict(counted) != manifest["records_per_category"]:
            raise ValueError("Importzählung stimmt nicht mit Snapshot überein")
        conn.execute("UPDATE behoerden.import_runs SET record_count=%s WHERE run_id=%s", (sum(counted.values()),run))
        conn.execute("ANALYZE behoerden.authorities")
        conn.execute("ANALYZE behoerden.boundaries")
        conn.execute("ANALYZE behoerden.locations")
    return {"source_id": s["id"], "run_id": run, "records_per_category": dict(counted)}


def coverage(dsn=None):
    with connect(dsn) as conn:
        rows = conn.execute("""SELECT c.id,c.metadata,
          (SELECT count(*) FROM behoerden.authorities a WHERE a.category=c.id) AS authority_count,
          (SELECT count(*) FROM behoerden.boundaries b WHERE b.category=c.id) AS boundary_count,
          (SELECT count(*) FROM behoerden.locations l WHERE l.category=c.id) AS location_count
          FROM behoerden.categories c ORDER BY c.id""").fetchall()
        imported = conn.execute("""SELECT DISTINCT ON(source_id) source_id,imported_at,manifest,record_count
          FROM behoerden.import_runs ORDER BY source_id,run_id DESC""").fetchall()
    return {"categories": [{**r["metadata"], "authority_count": r["authority_count"],
                            "boundary_count": r["boundary_count"],
                            "location_count": r['location_count'],
                            "empty_local_table": r["authority_count"] == 0,
                            "data_coverage_status": "polygons_available" if r['authority_count'] else "locations_only" if r['location_count'] else "no_integrated_geometry",
                            "requires_case_context": r['metadata']['resolution_mode'] in ('non_spatial','context_required')} for r in rows],
            "imports": imported, "national_coverage_guaranteed": False}


def resolve(value, lon, lat, dsn=None, include_geometry=True, exclude_sources=None):
    c = category(value)
    lon, lat = float(lon), float(lat)
    if not math.isfinite(lon) or not math.isfinite(lat) or not (-180 <= lon <= 180 and -90 <= lat <= 90):
        raise ValueError("Koordinaten müssen endliche WGS84-Werte sein (lon, lat)")
    result = {"category": c["id"], "point": {"lon": lon, "lat": lat},
              "limitations": c["limitations"], "matches": [],
              "national_coverage_guaranteed": False}
    context_required = c['resolution_mode'] in ('non_spatial','context_required')
    if context_required:
        result['required_context'] = c['limitations']
    has_areas = any(s['kind']=='authority' and s.get('active') is not False and any(r['category']==c['id'] for r in s['routes']) for s in sources())
    if c['resolution_mode']=='non_spatial' or (c['resolution_mode']=='context_required' and not has_areas):
        return {**result, "status": c["resolution_mode"], "required_context": c["limitations"]}
    geometry = sql.SQL(",ST_AsGeoJSON(a.geom)::jsonb AS geometry") if include_geometry else sql.SQL("")
    with connect(dsn) as conn:
        matches = conn.execute(sql.SQL("""WITH p AS (SELECT ST_SetSRID(ST_Point(%s,%s),4326) AS geom)
          SELECT a.authority_name,a.category,a.source_id,a.source_key,a.scope,a.source_date,a.evidence_url,
            a.geometry_repaired,a.properties,a.name_rule,a.run_id,'authority' AS kind,i.manifest->'source'->>'license' AS license,
            i.manifest->'source'->>'attribution' AS attribution,i.manifest->>'completed_at' AS fetched_at,
            ST_Touches(a.geom,p.geom) AS on_boundary {} FROM behoerden.authorities a
            JOIN behoerden.import_runs i ON i.run_id=a.run_id CROSS JOIN p
          WHERE a.category=%s AND NOT (a.source_id=ANY(%s::text[]))
            AND a.geom && p.geom AND ST_Covers(a.geom,p.geom)
          ORDER BY a.authority_name,a.source_id,a.source_key""").format(geometry), (lon,lat,c["id"],exclude_sources or [])).fetchall()
        boundary = conn.execute("""WITH p AS (SELECT ST_SetSRID(ST_Point(%s,%s),4326) AS geom)
          SELECT b.area_name,b.source_id,b.properties FROM behoerden.boundaries b CROSS JOIN p
          WHERE b.category=%s AND b.geom && p.geom AND ST_Covers(b.geom,p.geom)
          ORDER BY b.area_name,b.source_key""", (lon,lat,c["id"])).fetchall()
        count = conn.execute("SELECT count(*) AS n FROM behoerden.authorities WHERE category=%s", (c["id"],)).fetchone()["n"]
    status = "candidate" if len(matches) == 1 else "ambiguous" if matches else "no_coverage_at_point" if count else "no_local_data"
    return {**result, "status": 'context_required' if context_required else status,
            "area_search_status": status, "matches": matches, "boundary_references": boundary,
            "match_semantics": "general territorial candidates; category and point do not establish case-specific legal competence",
            "configured_sources": plan(c["id"])["wfs"]}


def nearby(value,lon,lat,radius_km=30,limit=3,dsn=None):
    code=category(value)['id']
    if not math.isfinite(float(radius_km)) or not 0<float(radius_km)<=300:raise ValueError('Punktsuchradius muss größer 0 und höchstens 300 km sein')
    if not 1<=limit<=10:raise ValueError('Anzahl Punktvorschläge muss zwischen 1 und 10 liegen')
    with connect(dsn) as conn:
        rows=conn.execute("""WITH p AS (SELECT ST_SetSRID(ST_Point(%s,%s),4326)::geography AS geog)
          SELECT l.authority_name,l.category,l.source_id,l.source_key,l.scope,l.source_date,l.evidence_url,
            l.properties,l.name_rule,l.run_id,ST_AsGeoJSON(l.geom)::jsonb AS geometry,
            i.manifest->'source'->>'license' AS license,i.manifest->'source'->>'attribution' AS attribution,
            i.manifest->>'completed_at' AS fetched_at,
            i.manifest->'source'->>'source_quality' AS source_quality,
            ST_Distance(l.geom::geography,p.geog) AS distance_m,
            false AS geometry_repaired,'authority_point' AS kind,false AS territorial_match_verified,false AS case_competence_verified,
            'location_only_no_jurisdiction_polygon' AS geometry_completeness,
            'nearest_point_fallback' AS match_type,false AS jurisdiction_verified
          FROM behoerden.locations l JOIN behoerden.import_runs i ON i.run_id=l.run_id CROSS JOIN p
          WHERE l.category=%s AND ST_DWithin(l.geom::geography,p.geog,%s)
          ORDER BY distance_m,l.authority_name,l.source_id,l.source_key LIMIT %s""",
          (float(lon),float(lat),code,float(radius_km)*1000,limit)).fetchall()
    return rows
