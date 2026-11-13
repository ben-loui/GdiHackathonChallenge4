-- =============================================================================
-- BZB – Laden: bzb_stage (ogr2ogr-Rohimport) → bzb (Kernmodell)
--
-- Aufruf über laden.sh. Erwartet in bzb_stage je Shapefile eine Tabelle
-- (Name = Layername klein, Geometriespalte geom) sowie bzb_stage.dbf_stand.
-- psql-Variable produktstand (JJJJ-MM oder leer).
--
-- Alles in einer Transaktion: Dienste sehen bis zum COMMIT den alten Stand
-- (DELETE statt TRUNCATE, damit lesende Dienste nicht blockiert werden).
-- Abschließend wird geprüft, dass jede View ihren Quell-Layer verlustfrei
-- wiedergibt (alle Attribute + Geometrie binär gleich). Sonst ROLLBACK.
-- =============================================================================
\set ON_ERROR_STOP on
BEGIN;

-- ------------------------------------------------------------------ leeren
DELETE FROM bzb.zoll_zustaendigkeitsbereich;
DELETE FROM bzb.zoll_hauptzollamt;
DELETE FROM bzb.zoll_zollfahndungsamt;
DELETE FROM bzb.thw_regionalstelle;
DELETE FROM bzb.thw_landesverband;
DELETE FROM bzb.sta_staatsanwaltschaft;
DELETE FROM bzb.sta_generalstaatsanwaltschaft;
DELETE FROM bzb.bpol_grenzzone_aut;
DELETE FROM bzb.bpol_inspektion_250_punkt;
DELETE FROM bzb.bpol_inspektion_250;
DELETE FROM bzb.bpol_inspektion;
DELETE FROM bzb.bpol_direktionsbereich;
DELETE FROM bzb.bpol_direktion;

-- ------------------------------------------------------------ Bundespolizei
-- Organisationseinheit Direktion: je Abkürzung der kürzeste Name
-- (BPOLD BBS → "BPOLD Bad Bramstedt", nicht "... See")
INSERT INTO bzb.bpol_direktion (dir_kurz, dir_kn, dir_lang)
SELECT DISTINCT ON (dir_kurz) dir_kurz, dir_kn, dir_lang
FROM bzb_stage.bpol_direktionen
ORDER BY dir_kurz, length(dir_kn), dir_kn;

INSERT INTO bzb.bpol_direktionsbereich (bereich_kn, bereich_lang, dir_kurz, geom)
SELECT dir_kn, dir_lang, dir_kurz, ST_Multi(geom)
FROM bzb_stage.bpol_direktionen;

INSERT INTO bzb.bpol_inspektion (ins_kurz, ins_kn, ins_lang, dir_kurz, zuordnung_kn, zuordnung_lang, geom)
SELECT ins_kurz, ins_kn, ins_lang, dir_kurz, dir_kn, dir_lang, ST_Multi(geom)
FROM bzb_stage.bpol_inspektionen;

INSERT INTO bzb.bpol_inspektion_250 (ins_kurz, geom)
SELECT ins_kurz, ST_Multi(geom)
FROM bzb_stage.bpol_inspektionen_250;

INSERT INTO bzb.bpol_inspektion_250_punkt
       (punkt_id, ins_kurz, ins_kn, ins_lang, dir_kurz, zuordnung_kn, zuordnung_lang, geom)
SELECT ins_kurz || '-' || row_number() OVER (PARTITION BY ins_kurz ORDER BY ST_X(geom), ST_Y(geom)),
       ins_kurz, ins_kn, ins_lang, dir_kurz, dir_kn, dir_lang, geom
FROM bzb_stage.bpol_inspektionen_250_p;

INSERT INTO bzb.bpol_grenzzone_aut (esz, ins_kurz, geom)
SELECT esz, ins_kurz, ST_Multi(geom)
FROM bzb_stage.bpol_deu_aut;

-- ----------------------------------------------------- Staatsanwaltschaften
-- GStA aus den Hauptstellen (…00) ableiten; ein Schlüssel mit zwei Namen
-- verletzt den Primärschlüssel und bricht das Laden ab.
INSERT INTO bzb.sta_generalstaatsanwaltschaft (gsta_nr, name)
SELECT DISTINCT left(sta_nr, 4), uebergeord
FROM bzb_stage.sta_staatsanwaltschaften
WHERE right(sta_nr, 2) = '00';

INSERT INTO bzb.sta_staatsanwaltschaft (sta_nr, name, geom)
SELECT sta_nr, name, ST_Multi(geom)
FROM bzb_stage.sta_staatsanwaltschaften;

-- ---------------------------------------------------------------------- THW
INSERT INTO bzb.thw_landesverband (lv_kurz, lv_kn, lv_lang, lv_zb, landesbeauftragter, geom)
SELECT lv_kurz, lv_kn, lv_lang, lv_zb, landesbeau, ST_Multi(geom)
FROM bzb_stage.thw_landesverband;

-- unbekanntes Bundesland → NULL → NOT NULL-Verletzung → Abbruch
INSERT INTO bzb.thw_regionalstelle (rst_kurz, rst_kn, rst_lang, rst_zb, lv_kurz, land_schluessel, geom)
SELECT r.rst_kurz, r.rst_kn, r.rst_lang, r.rst_zb, r.lv_kurz, b.land_schluessel, ST_Multi(r.geom)
FROM bzb_stage.thw_regionalstellen r
LEFT JOIN bzb.bundesland b ON b.name = r.bundesland;

-- --------------------------------------------------------------------- Zoll
INSERT INTO bzb.zoll_hauptzollamt (hza_dss, hza_kn, hza_lang, geom)
SELECT hza_dss, hza_kn, hza_lang, ST_Multi(geom)
FROM bzb_stage.zoll_hauptza;

INSERT INTO bzb.zoll_zollfahndungsamt (zfa_dss, zfa_kn, zfa_lang, geom)
SELECT zfa_dss, zfa_kn, zfa_lang, ST_Multi(geom)
FROM bzb_stage.zoll_zfa;

INSERT INTO bzb.zoll_zustaendigkeitsbereich (aufgabe_id, hza_dss, zst_dss, zst_kn, zst_lang, geom)
          SELECT 'AGRAR',          hza_dss, zst_dss, zst_kn, zst_lang, ST_Multi(geom) FROM bzb_stage.zoll_agrar
UNION ALL SELECT 'AUSFUHR',        hza_dss, zst_dss, zst_kn, zst_lang, ST_Multi(geom) FROM bzb_stage.zoll_ausfuhr
UNION ALL SELECT 'FKS',            hza_dss, zst_dss, zst_kn, zst_lang, ST_Multi(geom) FROM bzb_stage.zoll_fks
UNION ALL SELECT 'KFZSTEUER',      hza_dss, NULL,    NULL,   NULL,     ST_Multi(geom) FROM bzb_stage.zoll_kfzsteuer
UNION ALL SELECT 'KFZSTEUER_FEST', hza_dss, zst_dss, zst_kn, zst_lang, ST_Multi(geom) FROM bzb_stage.zoll_kfzsteuerfest
UNION ALL SELECT 'STRABU',         hza_dss, NULL,    NULL,   NULL,     ST_Multi(geom) FROM bzb_stage.zoll_strabu
UNION ALL SELECT 'VERWERTUNG',     hza_dss, zst_dss, zst_kn, zst_lang, ST_Multi(geom) FROM bzb_stage.zoll_verwertung
UNION ALL SELECT 'VOLLSTRECKUNG',  hza_dss, zst_dss, zst_kn, zst_lang, ST_Multi(geom) FROM bzb_stage.zoll_vollstreckung;


-- =============================================================================
-- Prüfung: View = Quell-Layer (Attribute der Lieferung + Geometrie, mit Duplikaten)
-- =============================================================================
DO $$
DECLARE
  d       record;
  spalten text;
  fehlt   bigint;
  zuviel  bigint;
  geo_s   constant text := 'md5(ST_AsBinary(CASE WHEN GeometryType(geom) LIKE ''%POLYGON'' THEN ST_Multi(geom) ELSE geom END))';
BEGIN
  FOR d IN SELECT datensatz_id FROM bzb.datensatz ORDER BY sortierung LOOP
    SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) INTO spalten
    FROM information_schema.columns
    WHERE table_schema = 'bzb_stage' AND table_name = d.datensatz_id
      AND column_name NOT IN ('fid', 'geom');
    IF spalten IS NULL THEN
      RAISE EXCEPTION 'Quell-Layer bzb_stage.% fehlt', d.datensatz_id;
    END IF;

    EXECUTE format(
      'SELECT (SELECT count(*) FROM (SELECT %1$s, %3$s FROM bzb_stage.%2$I
                                     EXCEPT ALL
                                     SELECT %1$s, md5(ST_AsBinary(geom)) FROM bzb_ows.%2$I) x),
              (SELECT count(*) FROM (SELECT %1$s, md5(ST_AsBinary(geom)) FROM bzb_ows.%2$I
                                     EXCEPT ALL
                                     SELECT %1$s, %3$s FROM bzb_stage.%2$I) y)',
      spalten, d.datensatz_id, geo_s)
    INTO fehlt, zuviel;

    IF fehlt > 0 OR zuviel > 0 THEN
      RAISE EXCEPTION 'Prüfung % fehlgeschlagen: % Quellobjekte nicht wiedergegeben, % Objekte zu viel',
        d.datensatz_id, fehlt, zuviel;
    END IF;
    RAISE NOTICE 'ok  %', d.datensatz_id;
  END LOOP;
END $$;


-- =============================================================================
-- Datensatz-Metadaten aktualisieren
-- =============================================================================
UPDATE bzb.produkt SET produktstand = :'produktstand' WHERE :'produktstand' <> '';

UPDATE bzb.datensatz d
SET dbf_stand = s.stand
FROM bzb_stage.dbf_stand s
WHERE s.quelle_layer = d.quelle_layer;

DO $$
DECLARE
  d record;
BEGIN
  FOR d IN SELECT datensatz_id FROM bzb.datensatz LOOP
    -- Umring der UTM-Ausdehnung verdichten, damit die WGS84-Box sie sicher umschließt
    EXECUTE format(
      'UPDATE bzb.datensatz SET
         anzahl_objekte   = s.n,
         ausdehnung_wgs84 = box2d(ST_Transform(ST_Segmentize(ST_SetSRID(s.box::geometry, 25832), 1000), 4326)),
         geladen_am       = now()
       FROM (SELECT count(*)::int AS n, ST_Extent(geom) AS box FROM bzb_ows.%1$I) s
       WHERE datensatz_id = %1$L', d.datensatz_id);
  END LOOP;
END $$;

COMMIT;
