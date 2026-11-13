-- =============================================================================
-- BZB – Veröffentlichungsschicht bzb_ows (eine View je Feature Type)
--
-- Konventionen für alle Views:
--   * id   stabile, fachliche Objekt-ID (text), bleibt über Neuladungen gleich
--   * Attribute heißen wie in der BKG-Produktdoku (klein geschrieben), damit
--     Styles, Filter und Clients für das Originalprodukt weiter passen;
--     zusätzliche Attribute stehen hinter den Originalattributen
--   * genau eine Geometriespalte geom, typisiert, EPSG:25832
--     (wird damit korrekt in geometry_columns gemeldet)
-- Idempotent (CREATE OR REPLACE).
-- =============================================================================
\set ON_ERROR_STOP on
BEGIN;

-- ---------------------------------------------------------------- Bundespolizei
CREATE OR REPLACE VIEW bzb_ows.bpol_direktionen AS
SELECT b.bereich_kn   AS id,
       b.dir_kurz,
       b.bereich_kn   AS dir_kn,
       b.bereich_lang AS dir_lang,
       b.geom
FROM bzb.bpol_direktionsbereich b;

CREATE OR REPLACE VIEW bzb_ows.bpol_inspektionen AS
SELECT i.ins_kurz       AS id,
       i.dir_kurz,
       i.zuordnung_kn   AS dir_kn,
       i.zuordnung_lang AS dir_lang,
       i.ins_kurz, i.ins_kn, i.ins_lang,
       i.geom
FROM bzb.bpol_inspektion i;

CREATE OR REPLACE VIEW bzb_ows.bpol_deu_aut AS
SELECT z.esz            AS id,
       i.dir_kurz,
       i.zuordnung_kn   AS dir_kn,
       i.zuordnung_lang AS dir_lang,
       z.esz,
       i.ins_kurz, i.ins_kn, i.ins_lang,
       z.geom
FROM bzb.bpol_grenzzone_aut z
JOIN bzb.bpol_inspektion i USING (ins_kurz);

CREATE OR REPLACE VIEW bzb_ows.bpol_inspektionen_250 AS
SELECT i.ins_kurz       AS id,
       i.dir_kurz,
       i.zuordnung_kn   AS dir_kn,
       i.zuordnung_lang AS dir_lang,
       i.ins_kurz, i.ins_kn, i.ins_lang,
       g.geom
FROM bzb.bpol_inspektion_250 g
JOIN bzb.bpol_inspektion i USING (ins_kurz);

CREATE OR REPLACE VIEW bzb_ows.bpol_inspektionen_250_p AS
SELECT p.punkt_id       AS id,
       p.dir_kurz,
       p.zuordnung_kn   AS dir_kn,
       p.zuordnung_lang AS dir_lang,
       p.ins_kurz, p.ins_kn, p.ins_lang,
       p.geom
FROM bzb.bpol_inspektion_250_punkt p;

-- --------------------------------------------------------- Staatsanwaltschaften
CREATE OR REPLACE VIEW bzb_ows.sta_staatsanwaltschaften AS
SELECT s.sta_nr                     AS id,
       s.sta_nr,
       coalesce(h.name, g.name)     AS uebergeord,
       s.name,
       -- Zusatzattribute
       s.gsta_nr,
       g.name                       AS generalstaatsanwaltschaft,
       s.hauptstelle_nr,
       (s.hauptstelle_nr IS NOT NULL) AS ist_zweigstelle,
       s.geom
FROM bzb.sta_staatsanwaltschaft s
JOIN bzb.sta_generalstaatsanwaltschaft g USING (gsta_nr)
LEFT JOIN bzb.sta_staatsanwaltschaft h ON h.sta_nr = s.hauptstelle_nr;

-- ------------------------------------------------------------------------- THW
CREATE OR REPLACE VIEW bzb_ows.thw_landesverband AS
SELECT l.lv_kurz            AS id,
       l.lv_kurz, l.lv_kn, l.lv_lang, l.lv_zb,
       l.landesbeauftragter AS landesbeau,
       l.geom
FROM bzb.thw_landesverband l;

CREATE OR REPLACE VIEW bzb_ows.thw_regionalstellen AS
SELECT r.rst_kurz AS id,
       l.lv_kurz, l.lv_kn, l.lv_lang, l.lv_zb,
       r.rst_kurz, r.rst_kn, r.rst_lang, r.rst_zb,
       b.name     AS bundesland,
       -- Zusatzattribute
       r.land_schluessel,
       r.geom
FROM bzb.thw_regionalstelle r
JOIN bzb.thw_landesverband l USING (lv_kurz)
JOIN bzb.bundesland b USING (land_schluessel);

-- ------------------------------------------------------------------------ Zoll
CREATE OR REPLACE VIEW bzb_ows.zoll_hauptza AS
SELECT h.hza_dss AS id, h.hza_kn, h.hza_lang, h.hza_dss, h.geom
FROM bzb.zoll_hauptzollamt h;

CREATE OR REPLACE VIEW bzb_ows.zoll_zfa AS
SELECT f.zfa_dss AS id, f.zfa_kn, f.zfa_lang, f.zfa_dss, f.geom
FROM bzb.zoll_zollfahndungsamt f;

-- Aufgaben mit zuständiger Stelle
CREATE OR REPLACE VIEW bzb_ows.zoll_agrar AS
SELECT b.bereich_id AS id, h.hza_kn, h.hza_lang, h.hza_dss, b.zst_kn, b.zst_lang, b.zst_dss, b.geom
FROM bzb.zoll_zustaendigkeitsbereich b JOIN bzb.zoll_hauptzollamt h USING (hza_dss)
WHERE b.aufgabe_id = 'AGRAR';

CREATE OR REPLACE VIEW bzb_ows.zoll_ausfuhr AS
SELECT b.bereich_id AS id, h.hza_kn, h.hza_lang, h.hza_dss, b.zst_kn, b.zst_lang, b.zst_dss, b.geom
FROM bzb.zoll_zustaendigkeitsbereich b JOIN bzb.zoll_hauptzollamt h USING (hza_dss)
WHERE b.aufgabe_id = 'AUSFUHR';

CREATE OR REPLACE VIEW bzb_ows.zoll_fks AS
SELECT b.bereich_id AS id, h.hza_kn, h.hza_lang, h.hza_dss, b.zst_kn, b.zst_lang, b.zst_dss, b.geom
FROM bzb.zoll_zustaendigkeitsbereich b JOIN bzb.zoll_hauptzollamt h USING (hza_dss)
WHERE b.aufgabe_id = 'FKS';

CREATE OR REPLACE VIEW bzb_ows.zoll_kfzsteuerfest AS
SELECT b.bereich_id AS id, h.hza_kn, h.hza_lang, h.hza_dss, b.zst_kn, b.zst_lang, b.zst_dss, b.geom
FROM bzb.zoll_zustaendigkeitsbereich b JOIN bzb.zoll_hauptzollamt h USING (hza_dss)
WHERE b.aufgabe_id = 'KFZSTEUER_FEST';

CREATE OR REPLACE VIEW bzb_ows.zoll_verwertung AS
SELECT b.bereich_id AS id, h.hza_kn, h.hza_lang, h.hza_dss, b.zst_kn, b.zst_lang, b.zst_dss, b.geom
FROM bzb.zoll_zustaendigkeitsbereich b JOIN bzb.zoll_hauptzollamt h USING (hza_dss)
WHERE b.aufgabe_id = 'VERWERTUNG';

CREATE OR REPLACE VIEW bzb_ows.zoll_vollstreckung AS
SELECT b.bereich_id AS id, h.hza_kn, h.hza_lang, h.hza_dss, b.zst_kn, b.zst_lang, b.zst_dss, b.geom
FROM bzb.zoll_zustaendigkeitsbereich b JOIN bzb.zoll_hauptzollamt h USING (hza_dss)
WHERE b.aufgabe_id = 'VOLLSTRECKUNG';

-- Aufgaben ohne zuständige Stelle (nur HZA)
CREATE OR REPLACE VIEW bzb_ows.zoll_kfzsteuer AS
SELECT b.bereich_id AS id, h.hza_kn, h.hza_lang, h.hza_dss, b.geom
FROM bzb.zoll_zustaendigkeitsbereich b JOIN bzb.zoll_hauptzollamt h USING (hza_dss)
WHERE b.aufgabe_id = 'KFZSTEUER';

CREATE OR REPLACE VIEW bzb_ows.zoll_strabu AS
SELECT b.bereich_id AS id, h.hza_kn, h.hza_lang, h.hza_dss, b.geom
FROM bzb.zoll_zustaendigkeitsbereich b JOIN bzb.zoll_hauptzollamt h USING (hza_dss)
WHERE b.aufgabe_id = 'STRABU';


-- =============================================================================
-- Metadaten-View für Dienstkonfiguration (Capabilities, OGC-API-Collections)
-- =============================================================================
CREATE OR REPLACE VIEW bzb_ows.datensatz AS
SELECT d.datensatz_id,
       d.titel,
       d.beschreibung,
       d.schlagwoerter || ARRAY['Behördenzuständigkeitsbereiche', 'BZB'] AS schlagwoerter,
       t.bezeichnung                   AS thema,
       d.quelle_layer,
       d.geometrietyp,
       'EPSG:25832'::text              AS speicher_crs,
       d.darstellung,
       t.stand_fachdaten,
       t.referenzgeometrie,
       d.dbf_stand,
       d.anzahl_objekte,
       ST_XMin(d.ausdehnung_wgs84)     AS west,
       ST_YMin(d.ausdehnung_wgs84)     AS sued,
       ST_XMax(d.ausdehnung_wgs84)     AS ost,
       ST_YMax(d.ausdehnung_wgs84)     AS nord,
       d.geladen_am,
       t.datenurheber,
       -- Quellenvermerk laut Nutzungsbedingungen; Jahr = Jahr des Produktstands
       format('© BKG (%s), Datenquellen: %s', left(p.produktstand, 4), p.datenquellen_url) AS quellenvermerk,
       p.nutzungsbedingungen,
       p.anbieter,
       p.kontakt,
       d.sortierung
FROM bzb.datensatz d
JOIN bzb.thema t USING (thema_id)
CROSS JOIN bzb.produkt p;
COMMENT ON VIEW bzb_ows.datensatz IS 'Metadaten je Feature Type zum Erzeugen von Dienstkonfigurationen (Titel, Abstract, Keywords, Extent, Attribution).';


-- =============================================================================
-- GeoServer: Primärschlüssel der Views bekannt machen
-- (PostGIS-Store-Parameter "Primary key metadata table" = bzb_ows.gt_pk_metadata)
-- =============================================================================
CREATE TABLE IF NOT EXISTS bzb_ows.gt_pk_metadata (
  table_schema  varchar(32) NOT NULL,
  table_name    varchar(64) NOT NULL,
  pk_column     varchar(32) NOT NULL,
  pk_column_idx integer,
  pk_policy     varchar(32),
  pk_sequence   varchar(64),
  UNIQUE (table_schema, table_name, pk_column),
  CHECK (pk_policy IN ('sequence', 'assigned', 'autogenerated'))
);
DELETE FROM bzb_ows.gt_pk_metadata WHERE table_schema = 'bzb_ows';
INSERT INTO bzb_ows.gt_pk_metadata (table_schema, table_name, pk_column, pk_policy)
SELECT 'bzb_ows', datensatz_id, 'id', 'assigned' FROM bzb.datensatz;


-- =============================================================================
-- Punktabfrage: alle zuständigen Stellen an einer Koordinate (WGS84 lon/lat)
-- Nur fachlich maßgebliche Layer (keine Übersichtsgeneralisierung).
-- An Grenzen und bei Zoll_Ausfuhr sind mehrere Treffer je Layer möglich.
--   SELECT * FROM bzb_ows.zustaendigkeiten(8.2711, 49.9987);
-- =============================================================================
CREATE OR REPLACE FUNCTION bzb_ows.zustaendigkeiten(lon double precision, lat double precision)
RETURNS TABLE (datensatz_id text, objekt_id text, kurzname text, bezeichnung text, uebergeordnet text)
LANGUAGE sql STABLE PARALLEL SAFE
SET search_path = bzb_ows, public
AS $$
  WITH p AS (
    SELECT ST_Transform(ST_SetSRID(ST_MakePoint(zustaendigkeiten.lon, zustaendigkeiten.lat), 4326), 25832) AS g
  )
  SELECT 'bpol_direktionen', v.id, v.dir_kn, v.dir_lang, NULL
    FROM bzb_ows.bpol_direktionen v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'bpol_inspektionen', v.id, v.ins_kn, v.ins_lang, v.dir_lang
    FROM bzb_ows.bpol_inspektionen v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'bpol_deu_aut', v.id, v.ins_kn, v.ins_lang, v.dir_lang
    FROM bzb_ows.bpol_deu_aut v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'sta_staatsanwaltschaften', v.id, NULL, v.name, v.uebergeord
    FROM bzb_ows.sta_staatsanwaltschaften v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'thw_landesverband', v.id, v.lv_kn, v.lv_lang, NULL
    FROM bzb_ows.thw_landesverband v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'thw_regionalstellen', v.id, v.rst_kn, v.rst_lang, v.lv_lang
    FROM bzb_ows.thw_regionalstellen v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_hauptza', v.id, v.hza_kn, v.hza_lang, NULL
    FROM bzb_ows.zoll_hauptza v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_zfa', v.id, v.zfa_kn, v.zfa_lang, NULL
    FROM bzb_ows.zoll_zfa v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_agrar', v.id, v.zst_kn, v.zst_lang, v.hza_lang
    FROM bzb_ows.zoll_agrar v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_ausfuhr', v.id, v.zst_kn, v.zst_lang, v.hza_lang
    FROM bzb_ows.zoll_ausfuhr v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_fks', v.id, v.zst_kn, v.zst_lang, v.hza_lang
    FROM bzb_ows.zoll_fks v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_kfzsteuer', v.id, v.hza_kn, v.hza_lang, NULL
    FROM bzb_ows.zoll_kfzsteuer v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_kfzsteuerfest', v.id, v.zst_kn, v.zst_lang, v.hza_lang
    FROM bzb_ows.zoll_kfzsteuerfest v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_strabu', v.id, v.hza_kn, v.hza_lang, NULL
    FROM bzb_ows.zoll_strabu v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_verwertung', v.id, v.zst_kn, v.zst_lang, v.hza_lang
    FROM bzb_ows.zoll_verwertung v, p WHERE ST_Intersects(v.geom, p.g)
  UNION ALL
  SELECT 'zoll_vollstreckung', v.id, v.zst_kn, v.zst_lang, v.hza_lang
    FROM bzb_ows.zoll_vollstreckung v, p WHERE ST_Intersects(v.geom, p.g)
$$;
COMMENT ON FUNCTION bzb_ows.zustaendigkeiten(double precision, double precision)
  IS 'Zuständige Stellen aller fachlich maßgeblichen BZB-Layer an einem Punkt (lon/lat, EPSG:4326).';


-- =============================================================================
-- Konsistenz: jeder Datensatz hat genau eine View und umgekehrt
-- =============================================================================
DO $$
DECLARE
  fehlend text;
BEGIN
  SELECT string_agg(coalesce(d.datensatz_id, v.table_name), ', ') INTO fehlend
  FROM bzb.datensatz d
  FULL JOIN (SELECT table_name::text FROM information_schema.views
             WHERE table_schema = 'bzb_ows' AND table_name <> 'datensatz') v
    ON v.table_name = d.datensatz_id
  WHERE d.datensatz_id IS NULL OR v.table_name IS NULL;
  IF fehlend IS NOT NULL THEN
    RAISE EXCEPTION 'bzb.datensatz und Views in bzb_ows passen nicht zusammen: %', fehlend;
  END IF;
END $$;


-- =============================================================================
-- Rechte: Leserollen sehen nur bzb_ows, und dort nur die Views ihres Themas
-- =============================================================================
REVOKE ALL ON ALL TABLES IN SCHEMA bzb_ows FROM PUBLIC;
REVOKE ALL ON FUNCTION bzb_ows.zustaendigkeiten(double precision, double precision) FROM PUBLIC;

DO $$
DECLARE
  r record;
BEGIN
  FOR r IN SELECT DISTINCT leserolle FROM bzb.thema LOOP
    EXECUTE format('GRANT USAGE ON SCHEMA bzb_ows TO %I', r.leserolle);
    EXECUTE format('GRANT SELECT ON bzb_ows.datensatz, bzb_ows.gt_pk_metadata TO %I', r.leserolle);
  END LOOP;
  FOR r IN SELECT d.datensatz_id, t.leserolle FROM bzb.datensatz d JOIN bzb.thema t USING (thema_id) LOOP
    EXECUTE format('GRANT SELECT ON bzb_ows.%I TO %I', r.datensatz_id, r.leserolle);
  END LOOP;
END $$;

-- Die Punktabfrage liest alle Themen
GRANT EXECUTE ON FUNCTION bzb_ows.zustaendigkeiten(double precision, double precision) TO bzb_leser;

COMMIT;
