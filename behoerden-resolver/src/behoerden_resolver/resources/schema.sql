CREATE EXTENSION IF NOT EXISTS postgis;
CREATE SCHEMA IF NOT EXISTS behoerden;
CREATE TABLE IF NOT EXISTS behoerden.schema_version (version integer PRIMARY KEY CHECK (version = 1));
INSERT INTO behoerden.schema_version VALUES (1) ON CONFLICT DO NOTHING;
ALTER TABLE behoerden.schema_version DROP CONSTRAINT IF EXISTS schema_version_version_check;
INSERT INTO behoerden.schema_version VALUES (2) ON CONFLICT DO NOTHING;
CREATE TABLE IF NOT EXISTS behoerden.categories (
    id text PRIMARY KEY,
    metadata jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS behoerden.sources (
    id text PRIMARY KEY,
    metadata jsonb NOT NULL
);
CREATE TABLE IF NOT EXISTS behoerden.import_runs (
    run_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id text NOT NULL REFERENCES behoerden.sources(id),
    imported_at timestamptz NOT NULL DEFAULT now(),
    manifest jsonb NOT NULL,
    record_count integer NOT NULL CHECK (record_count >= 0)
);
CREATE TABLE IF NOT EXISTS behoerden.authorities (
    category text NOT NULL REFERENCES behoerden.categories(id),
    source_id text NOT NULL REFERENCES behoerden.sources(id),
    source_key text NOT NULL,
    authority_name text NOT NULL CHECK (length(trim(authority_name)) > 0),
    geom geometry(MultiPolygon, 4326) NOT NULL,
    geometry_repaired boolean NOT NULL,
    properties jsonb NOT NULL,
    scope text NOT NULL,
    source_date text,
    evidence_url text NOT NULL,
    name_rule jsonb NOT NULL,
    run_id bigint NOT NULL REFERENCES behoerden.import_runs(run_id),
    PRIMARY KEY (category, source_id, source_key),
    CHECK (NOT ST_IsEmpty(geom) AND ST_IsValid(geom))
) PARTITION BY LIST (category);
CREATE INDEX IF NOT EXISTS authorities_geom_idx ON behoerden.authorities USING gist(geom);
CREATE TABLE IF NOT EXISTS behoerden.boundaries (
    category text NOT NULL REFERENCES behoerden.categories(id),
    source_id text NOT NULL REFERENCES behoerden.sources(id),
    source_key text NOT NULL,
    area_name text NOT NULL,
    geom geometry(MultiPolygon, 4326) NOT NULL,
    properties jsonb NOT NULL,
    geometry_repaired boolean NOT NULL,
    run_id bigint NOT NULL REFERENCES behoerden.import_runs(run_id),
    PRIMARY KEY (category, source_id, source_key),
    CHECK (NOT ST_IsEmpty(geom) AND ST_IsValid(geom))
);
CREATE INDEX IF NOT EXISTS boundaries_geom_idx ON behoerden.boundaries USING gist(geom);
COMMENT ON TABLE behoerden.boundaries IS 'Verwaltungsgebiete; kein Nachweis einer Behörde oder Fachzuständigkeit';
CREATE TABLE IF NOT EXISTS behoerden.locations (
    category text NOT NULL REFERENCES behoerden.categories(id),
    source_id text NOT NULL REFERENCES behoerden.sources(id),
    source_key text NOT NULL,
    authority_name text NOT NULL CHECK (length(trim(authority_name)) > 0),
    geom geometry(Point,4326) NOT NULL,
    properties jsonb NOT NULL,
    scope text NOT NULL,
    source_date text,
    evidence_url text NOT NULL,
    name_rule jsonb NOT NULL,
    run_id bigint NOT NULL REFERENCES behoerden.import_runs(run_id),
    PRIMARY KEY(category,source_id,source_key),
    CHECK (NOT ST_IsEmpty(geom) AND ST_X(geom) BETWEEN -180 AND 180 AND ST_Y(geom) BETWEEN -90 AND 90)
);
CREATE INDEX IF NOT EXISTS locations_geog_idx ON behoerden.locations USING gist((geom::geography));
CREATE INDEX IF NOT EXISTS locations_category_idx ON behoerden.locations(category);
COMMENT ON TABLE behoerden.locations IS 'Standorte ohne behauptete Zuständigkeitsfläche; ausschließlich ausdrücklich gekennzeichnete Nähehinweise';
