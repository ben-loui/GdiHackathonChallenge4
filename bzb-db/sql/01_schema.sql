-- =============================================================================
-- BZB – Behördenzuständigkeitsbereiche (BKG), Datenbankschema für OGC-Dienste
-- PostgreSQL >= 15, PostGIS >= 3.3
--
--   bzb        Kernmodell, normalisiert, fachliche Schlüssel als Primärschlüssel
--   bzb_ows    Veröffentlichung: eine View je Feature Type      (03_ows.sql)
--   bzb_stage  Rohimport der Shapefiles per ogr2ogr              (laden.sh)
--
-- Speicher-CRS ist EPSG:25832 (ETRS89 / UTM 32N) wie in der BKG-Lieferung.
-- Andere Ausgabe-CRS (4326, 4258, 25833, 3035, 3857, 31467 …) transformiert
-- der Dienst; das Speicher-CRS bleibt verlustfrei.
-- =============================================================================
\set ON_ERROR_STOP on
BEGIN;

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA bzb;
CREATE SCHEMA bzb_ows;
CREATE SCHEMA bzb_stage;

COMMENT ON SCHEMA bzb       IS 'BZB Kernmodell (normalisiert). Kein direkter Dienstzugriff.';
COMMENT ON SCHEMA bzb_ows   IS 'BZB Veröffentlichungsschicht: eine View je Feature Type / Collection. Einzige Schnittstelle für WMS, WFS und OGC API Features.';
COMMENT ON SCHEMA bzb_stage IS 'BZB Rohimport der Shapefiles (ogr2ogr). Wird bei jedem Laden neu erzeugt.';


-- =============================================================================
-- Produkt-, Themen- und Datensatzmetadaten (Inhalte: 02_metadaten.sql)
-- Quelle für GetCapabilities / OGC-API-Collection-Metadaten.
-- =============================================================================
CREATE TABLE bzb.produkt (
  produkt_id          text PRIMARY KEY DEFAULT 'BZB' CHECK (produkt_id = 'BZB'),
  bezeichnung         text NOT NULL,
  produktstand        text NOT NULL CHECK (produktstand ~ '^\d{4}-\d{2}$'),
  anbieter            text NOT NULL,
  datenquellen_url    text NOT NULL,
  nutzungsbedingungen text NOT NULL,
  kontakt             text NOT NULL
);
COMMENT ON TABLE  bzb.produkt IS 'Genau eine Zeile: Produktmetadaten der BZB-Lieferung.';
COMMENT ON COLUMN bzb.produkt.produktstand IS 'Produktstand JJJJ-MM laut dokumentation/aktualitaet.txt (wird von laden.sh gesetzt).';

CREATE TABLE bzb.thema (
  thema_id          text PRIMARY KEY CHECK (thema_id IN ('BPOL', 'STA', 'THW', 'ZOLL')),
  bezeichnung       text NOT NULL UNIQUE,
  datenurheber      text NOT NULL,
  stand_fachdaten   text NOT NULL CHECK (stand_fachdaten ~ '^\d{4}-\d{2}$'),
  referenzgeometrie text NOT NULL,
  leserolle         name NOT NULL
);
COMMENT ON TABLE  bzb.thema IS 'Themen der BZB-Lieferung (bzb_bpol, bzb_sta, bzb_thw, bzb_zoll).';
COMMENT ON COLUMN bzb.thema.stand_fachdaten   IS 'Stand der Zuständigkeitsbereiche (monatsgenau, BKG-Doku Kap. 3.2).';
COMMENT ON COLUMN bzb.thema.referenzgeometrie IS 'Geometriegrundlage inkl. Stand, z. B. "VG250 (31.12.2025)" oder "PLZ (2026-02)".';
COMMENT ON COLUMN bzb.thema.leserolle         IS 'Datenbankrolle, die die Views dieses Themas lesen darf.';

CREATE TABLE bzb.datensatz (
  datensatz_id     text PRIMARY KEY CHECK (datensatz_id ~ '^[a-z][a-z0-9_]*$'),
  thema_id         text NOT NULL REFERENCES bzb.thema,
  quelle_layer     text NOT NULL UNIQUE,
  titel            text NOT NULL,
  beschreibung     text NOT NULL,
  schlagwoerter    text[] NOT NULL DEFAULT '{}',
  geometrietyp     text NOT NULL CHECK (geometrietyp IN ('MultiPolygon', 'Point')),
  darstellung      text NOT NULL DEFAULT 'vollstaendig'
                   CHECK (darstellung IN ('vollstaendig', 'uebersicht')),
  sortierung       smallint NOT NULL,
  -- vom Ladeprozess gepflegt
  dbf_stand        date,
  anzahl_objekte   integer,
  ausdehnung_wgs84 box2d,
  geladen_am       timestamptz
);
COMMENT ON TABLE  bzb.datensatz IS 'Ein Eintrag je veröffentlichtem Layer; datensatz_id = Name der View in bzb_ows.';
COMMENT ON COLUMN bzb.datensatz.quelle_layer     IS 'Name des Shapefiles / Layers der BKG-Lieferung, z. B. BPOL_Inspektionen.';
COMMENT ON COLUMN bzb.datensatz.darstellung      IS 'vollstaendig = fachlich maßgeblich; uebersicht = für Übersichtsmaßstäbe generalisiert (nicht für Zuständigkeitsabfragen).';
COMMENT ON COLUMN bzb.datensatz.dbf_stand        IS 'DBF_DATE_LAST_UPDATE aus dem Shapefile-Header.';
COMMENT ON COLUMN bzb.datensatz.ausdehnung_wgs84 IS 'Umgebendes Rechteck in EPSG:4326 (lon/lat) für Capabilities.';


-- =============================================================================
-- Referenzlisten
-- =============================================================================
CREATE TABLE bzb.bundesland (
  land_schluessel text PRIMARY KEY CHECK (land_schluessel ~ '^(0[1-9]|1[0-6])$'),
  name            text NOT NULL UNIQUE
);
COMMENT ON TABLE bzb.bundesland IS 'Bundesländer mit Länderschlüssel (erste zwei Stellen des AGS).';

INSERT INTO bzb.bundesland (land_schluessel, name) VALUES
  ('01', 'Schleswig-Holstein'), ('02', 'Hamburg'),        ('03', 'Niedersachsen'),
  ('04', 'Bremen'),             ('05', 'Nordrhein-Westfalen'), ('06', 'Hessen'),
  ('07', 'Rheinland-Pfalz'),    ('08', 'Baden-Württemberg'), ('09', 'Bayern'),
  ('10', 'Saarland'),           ('11', 'Berlin'),         ('12', 'Brandenburg'),
  ('13', 'Mecklenburg-Vorpommern'), ('14', 'Sachsen'),    ('15', 'Sachsen-Anhalt'),
  ('16', 'Thüringen');


-- =============================================================================
-- Thema Bundespolizei (BZB_BPOL)
-- =============================================================================
CREATE TABLE bzb.bpol_direktion (
  dir_kurz text PRIMARY KEY,
  dir_kn   text NOT NULL UNIQUE,
  dir_lang text NOT NULL UNIQUE
);
COMMENT ON TABLE  bzb.bpol_direktion IS 'Bundespolizeidirektionen (Organisationseinheit, ohne Geometrie).';
COMMENT ON COLUMN bzb.bpol_direktion.dir_kurz IS 'Abkürzung Direktion, z. B. BPOLD STA';
COMMENT ON COLUMN bzb.bpol_direktion.dir_kn   IS 'Kurzname Direktion, z. B. BPOLD Sankt Augustin';
COMMENT ON COLUMN bzb.bpol_direktion.dir_lang IS 'Langbezeichnung, z. B. Bundespolizeidirektion Sankt Augustin';

CREATE TABLE bzb.bpol_direktionsbereich (
  bereich_kn   text PRIMARY KEY,
  bereich_lang text NOT NULL UNIQUE,
  dir_kurz     text NOT NULL REFERENCES bzb.bpol_direktion,
  geom         geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT bpol_direktionsbereich_geom_gueltig CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE  bzb.bpol_direktionsbereich IS 'Zuständigkeitsflächen der Direktionen (Layer BPOL_Direktionen). Eine Direktion kann mehrere Bereiche haben, z. B. BPOLD BBS und "BPOLD Bad Bramstedt See".';
COMMENT ON COLUMN bzb.bpol_direktionsbereich.bereich_kn IS 'DIR_kn der Lieferung, eindeutig je Fläche.';

CREATE TABLE bzb.bpol_inspektion (
  ins_kurz       text PRIMARY KEY,
  ins_kn         text NOT NULL UNIQUE,
  ins_lang       text NOT NULL,
  dir_kurz       text NOT NULL REFERENCES bzb.bpol_direktion,
  zuordnung_kn   text NOT NULL,
  zuordnung_lang text NOT NULL,
  geom           geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT bpol_inspektion_geom_gueltig CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE  bzb.bpol_inspektion IS 'Bundespolizeiinspektionen mit Zuständigkeitsfläche (Layer BPOL_Inspektionen).';
COMMENT ON COLUMN bzb.bpol_inspektion.ins_kurz       IS 'Abkürzung Inspektion, z. B. BPOLI MS';
COMMENT ON COLUMN bzb.bpol_inspektion.zuordnung_kn   IS 'DIR_kn wie geliefert. Meist = Direktion, teils ein Bereich ("BPOLD Bad Bramstedt See", "BPOLD München - Bundespolizei Flughafen München").';
COMMENT ON COLUMN bzb.bpol_inspektion.zuordnung_lang IS 'DIR_lang wie geliefert (siehe zuordnung_kn).';

CREATE TABLE bzb.bpol_inspektion_250 (
  ins_kurz text PRIMARY KEY REFERENCES bzb.bpol_inspektion,
  geom     geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT bpol_inspektion_250_geom_gueltig CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE bzb.bpol_inspektion_250 IS 'Für Übersichtsmaßstäbe generalisierte Inspektionsflächen (Layer BPOL_Inspektionen_250). Kleine Inspektionen fehlen und liegen als Punkte in bpol_inspektion_250_punkt. Nicht für Zuständigkeitsabfragen.';

CREATE TABLE bzb.bpol_inspektion_250_punkt (
  punkt_id       text PRIMARY KEY,
  ins_kurz       text NOT NULL,
  ins_kn         text NOT NULL,
  ins_lang       text NOT NULL,
  dir_kurz       text NOT NULL REFERENCES bzb.bpol_direktion,
  zuordnung_kn   text NOT NULL,
  zuordnung_lang text NOT NULL,
  geom           geometry(Point, 25832) NOT NULL
);
COMMENT ON TABLE  bzb.bpol_inspektion_250_punkt IS 'Kleine Inspektionen als Punkte für Übersichtskarten (Layer BPOL_Inspektionen_250_p). Bewusst ohne Fremdschlüssel auf bpol_inspektion: "BPOLI FRA I-V" fasst die Inspektionen BPOLI FRA I bis V zusammen.';
COMMENT ON COLUMN bzb.bpol_inspektion_250_punkt.punkt_id IS 'Stabile ID: ins_kurz-n, n nach Lage (x, y) nummeriert.';

CREATE TABLE bzb.bpol_grenzzone_aut (
  esz      text PRIMARY KEY CHECK (esz ~ '^\d{3}$'),
  ins_kurz text NOT NULL REFERENCES bzb.bpol_inspektion,
  geom     geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT bpol_grenzzone_aut_geom_gueltig CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE  bzb.bpol_grenzzone_aut IS '30-km-Zone an der deutsch-österreichischen Grenze, Abschnitte je zuständiger Inspektion (Layer BPOL_DEU_AUT).';
COMMENT ON COLUMN bzb.bpol_grenzzone_aut.esz IS 'Abschnittskennung ESZ wie geliefert (in der BKG-Doku nicht beschrieben).';

CREATE INDEX ON bzb.bpol_direktionsbereich    (dir_kurz);
CREATE INDEX ON bzb.bpol_inspektion           (dir_kurz);
CREATE INDEX ON bzb.bpol_inspektion_250_punkt (ins_kurz);
CREATE INDEX ON bzb.bpol_grenzzone_aut        (ins_kurz);
CREATE INDEX ON bzb.bpol_direktionsbereich    USING gist (geom);
CREATE INDEX ON bzb.bpol_inspektion           USING gist (geom);
CREATE INDEX ON bzb.bpol_inspektion_250       USING gist (geom);
CREATE INDEX ON bzb.bpol_inspektion_250_punkt USING gist (geom);
CREATE INDEX ON bzb.bpol_grenzzone_aut        USING gist (geom);


-- =============================================================================
-- Thema Staatsanwaltschaften (BZB_StA)
--
-- Schlüssel StA_Nr = S + 7 Ziffern. Die ersten vier Zeichen bezeichnen die
-- Generalstaatsanwaltschaft (S092 = GStA München); die letzten beiden sind
-- 00 für eine Staatsanwaltschaft, sonst die Nummer der Zweigstelle (S0920661 =
-- Zweigstelle Neu-Ulm der StA Memmingen S0920600). Die Hierarchie wird daraus
-- abgeleitet statt über das Namensfeld "Uebergeord" verknüpft.
-- =============================================================================
CREATE TABLE bzb.sta_generalstaatsanwaltschaft (
  gsta_nr text PRIMARY KEY CHECK (gsta_nr ~ '^S\d{3}$'),
  name    text NOT NULL UNIQUE
);
COMMENT ON TABLE  bzb.sta_generalstaatsanwaltschaft IS 'Generalstaatsanwaltschaften (ohne Geometrie), abgeleitet aus StA_Nr und Uebergeord.';
COMMENT ON COLUMN bzb.sta_generalstaatsanwaltschaft.gsta_nr IS 'Erste vier Stellen der StA_Nr, z. B. S092';

CREATE TABLE bzb.sta_staatsanwaltschaft (
  sta_nr         text PRIMARY KEY CHECK (sta_nr ~ '^S\d{7}$'),
  name           text NOT NULL UNIQUE,
  gsta_nr        text NOT NULL GENERATED ALWAYS AS (left(sta_nr, 4)) STORED
                 REFERENCES bzb.sta_generalstaatsanwaltschaft,
  hauptstelle_nr text GENERATED ALWAYS AS (
                   CASE WHEN right(sta_nr, 2) <> '00' THEN left(sta_nr, 6) || '00' END
                 ) STORED REFERENCES bzb.sta_staatsanwaltschaft,
  geom           geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT sta_staatsanwaltschaft_geom_gueltig CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE  bzb.sta_staatsanwaltschaft IS 'Bezirke der Staatsanwaltschaften und ihrer Zweigstellen (Layer StA_Staatsanwaltschaften).';
COMMENT ON COLUMN bzb.sta_staatsanwaltschaft.sta_nr         IS 'Schlüsselnummer der Staatsanwaltschaft, z. B. S0110100';
COMMENT ON COLUMN bzb.sta_staatsanwaltschaft.hauptstelle_nr IS 'Bei Zweigstellen die StA_Nr der Staatsanwaltschaft, sonst NULL.';

CREATE INDEX ON bzb.sta_staatsanwaltschaft (gsta_nr);
CREATE INDEX ON bzb.sta_staatsanwaltschaft (hauptstelle_nr);
CREATE INDEX ON bzb.sta_staatsanwaltschaft USING gist (geom);


-- =============================================================================
-- Thema Technisches Hilfswerk (BZB_THW)
-- =============================================================================
CREATE TABLE bzb.thw_landesverband (
  lv_kurz            text PRIMARY KEY,
  lv_kn              text NOT NULL UNIQUE,
  lv_lang            text NOT NULL UNIQUE,
  lv_zb              text NOT NULL,
  landesbeauftragter text NOT NULL,
  geom               geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT thw_landesverband_geom_gueltig CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE  bzb.thw_landesverband IS 'THW-Landesverbände (Layer THW_Landesverband).';
COMMENT ON COLUMN bzb.thw_landesverband.lv_kurz IS 'Abkürzung Landesverband, z. B. LVNI';
COMMENT ON COLUMN bzb.thw_landesverband.lv_zb   IS 'Zuständigkeitsbereich als Text, z. B. "Bremen, Niedersachsen"';

CREATE TABLE bzb.thw_regionalstelle (
  rst_kurz        text PRIMARY KEY,
  rst_kn          text NOT NULL UNIQUE,
  rst_lang        text NOT NULL,
  rst_zb          text NOT NULL,
  lv_kurz         text NOT NULL REFERENCES bzb.thw_landesverband,
  land_schluessel text NOT NULL REFERENCES bzb.bundesland,
  geom            geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT thw_regionalstelle_geom_gueltig CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE  bzb.thw_regionalstelle IS 'THW-Regionalstellen (Layer THW_Regionalstellen).';
COMMENT ON COLUMN bzb.thw_regionalstelle.land_schluessel IS 'Bundesland, in dem die Regionalstelle liegt (Sitz, nicht Fläche).';

CREATE INDEX ON bzb.thw_regionalstelle (lv_kurz);
CREATE INDEX ON bzb.thw_landesverband  USING gist (geom);
CREATE INDEX ON bzb.thw_regionalstelle USING gist (geom);


-- =============================================================================
-- Thema Zoll (BZB_Zoll)
--
-- Hauptzollämter und Zollfahndungsämter sind eigene Tabellen. Die acht
-- fachlichen Zuständigkeiten (Ausfuhr, FKS, Kfz-Steuer, …) liegen gemeinsam in
-- zoll_zustaendigkeitsbereich, unterschieden über die Codeliste zoll_aufgabe.
-- Eine neue Aufgabe braucht so eine Zeile in zoll_aufgabe und eine View,
-- aber keine neue Tabelle.
-- Die zuständige Stelle (ZST) ist keine eigene Tabelle: derselbe
-- Dienststellenschlüssel trägt je Aufgabe unterschiedliche Namen
-- (2150 = "Verw Berlin" bzw. "Vollstr Berlin").
-- =============================================================================
CREATE TABLE bzb.zoll_hauptzollamt (
  hza_dss  text PRIMARY KEY CHECK (hza_dss ~ '^\d{4}$'),
  hza_kn   text NOT NULL UNIQUE,
  hza_lang text NOT NULL UNIQUE,
  geom     geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT zoll_hauptzollamt_geom_gueltig CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE  bzb.zoll_hauptzollamt IS 'Hauptzollämter mit Bezirk (Layer Zoll_HauptZA).';
COMMENT ON COLUMN bzb.zoll_hauptzollamt.hza_dss IS 'Dienststellenschlüssel Hauptzollamt, z. B. 9150';

CREATE TABLE bzb.zoll_zollfahndungsamt (
  zfa_dss  text PRIMARY KEY CHECK (zfa_dss ~ '^\d{4}$'),
  zfa_kn   text NOT NULL UNIQUE,
  zfa_lang text NOT NULL UNIQUE,
  geom     geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT zoll_zollfahndungsamt_geom_gueltig CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE bzb.zoll_zollfahndungsamt IS 'Zollfahndungsämter mit Bezirk (Layer Zoll_ZFA).';

CREATE TABLE bzb.zoll_aufgabe (
  aufgabe_id              text PRIMARY KEY CHECK (aufgabe_id ~ '^[A-Z][A-Z_]*$'),
  bezeichnung             text NOT NULL UNIQUE,
  mit_zustaendiger_stelle boolean NOT NULL,
  ueberlappung_moeglich   boolean NOT NULL DEFAULT false,
  UNIQUE (aufgabe_id, mit_zustaendiger_stelle)
);
COMMENT ON TABLE  bzb.zoll_aufgabe IS 'Codeliste der fachlichen Zoll-Zuständigkeiten.';
COMMENT ON COLUMN bzb.zoll_aufgabe.mit_zustaendiger_stelle IS 'true: Bereiche sind einer Stelle (ZST) unterhalb des HZA zugeordnet; false: nur dem HZA.';
COMMENT ON COLUMN bzb.zoll_aufgabe.ueberlappung_moeglich   IS 'true: Flächen dürfen sich laut BKG überlappen (Ausfuhr).';

INSERT INTO bzb.zoll_aufgabe (aufgabe_id, bezeichnung, mit_zustaendiger_stelle, ueberlappung_moeglich) VALUES
  ('AGRAR',          'Agrardieselvergütung',              true,  false),
  ('AUSFUHR',        'Ausfuhrzollstellen',                true,  true),
  ('FKS',            'Finanzkontrolle Schwarzarbeit',     true,  false),
  ('KFZSTEUER',      'Kfz-Steuer',                        false, false),
  ('KFZSTEUER_FEST', 'Kfz-Steuer-Festsetzungsstellen',    true,  false),
  ('STRABU',         'Straf- und Bußgeldstellen',         false, false),
  ('VERWERTUNG',     'Verwertungsstellen',                true,  false),
  ('VOLLSTRECKUNG',  'Vollstreckungsbezirke',             true,  false);

CREATE TABLE bzb.zoll_zustaendigkeitsbereich (
  bereich_id text GENERATED ALWAYS AS (lower(aufgabe_id) || '.' || coalesce(zst_dss, hza_dss)) STORED PRIMARY KEY,
  aufgabe_id text NOT NULL,
  hza_dss    text NOT NULL REFERENCES bzb.zoll_hauptzollamt,
  zst_dss    text CHECK (zst_dss ~ '^\d{4}$'),
  zst_kn     text,
  zst_lang   text,
  mit_zst    boolean NOT NULL GENERATED ALWAYS AS (zst_dss IS NOT NULL) STORED,
  geom       geometry(MultiPolygon, 25832) NOT NULL,
  CONSTRAINT zoll_zustaendigkeitsbereich_aufgabe_fk
    FOREIGN KEY (aufgabe_id, mit_zst) REFERENCES bzb.zoll_aufgabe (aufgabe_id, mit_zustaendiger_stelle),
  CONSTRAINT zoll_zustaendigkeitsbereich_zst_vollstaendig
    CHECK (num_nulls(zst_dss, zst_kn, zst_lang) IN (0, 3)),
  CONSTRAINT zoll_zustaendigkeitsbereich_geom_gueltig
    CHECK (ST_IsValid(geom) AND NOT ST_IsEmpty(geom))
);
COMMENT ON TABLE  bzb.zoll_zustaendigkeitsbereich IS 'Fachliche Zoll-Zuständigkeitsbereiche aller Aufgaben (Layer Zoll_Agrar, _Ausfuhr, _FKS, _KfzSteuer, _KfzSteuerFest, _StraBu, _Verwertung, _Vollstreckung).';
COMMENT ON COLUMN bzb.zoll_zustaendigkeitsbereich.bereich_id IS 'Stabile ID: aufgabe.dss, z. B. ausfuhr.2101 oder kfzsteuer.2300';
COMMENT ON COLUMN bzb.zoll_zustaendigkeitsbereich.zst_dss    IS 'Dienststellenschlüssel der zuständigen Stelle; NULL bei Aufgaben ohne ZST (Kfz-Steuer, StraBu).';
COMMENT ON COLUMN bzb.zoll_zustaendigkeitsbereich.mit_zst    IS 'Technische Spalte: erzwingt über den Fremdschlüssel, dass ZST-Angaben zur Aufgabe passen.';

CREATE INDEX ON bzb.zoll_zustaendigkeitsbereich (aufgabe_id);
CREATE INDEX ON bzb.zoll_zustaendigkeitsbereich (hza_dss);
CREATE INDEX ON bzb.zoll_hauptzollamt           USING gist (geom);
CREATE INDEX ON bzb.zoll_zollfahndungsamt       USING gist (geom);
CREATE INDEX ON bzb.zoll_zustaendigkeitsbereich USING gist (geom);

COMMIT;
