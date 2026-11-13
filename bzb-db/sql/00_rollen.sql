-- =============================================================================
-- BZB – Rollen (clusterweit, benötigt CREATEROLE). Idempotent.
--
-- Je Thema eine Leserolle, weil die BKG-Nutzungsbedingungen die Daten je nach
-- Vertrag "allen oder ausgewählten Bundesbehörden" bereitstellen. Ein Dienst
-- (GeoServer, QGIS Server, pygeoapi, ...) bekommt ein Login, das nur Mitglied
-- der Themen ist, die er ausliefern darf.
-- =============================================================================
\set ON_ERROR_STOP on

DO $$
DECLARE
  r text;
BEGIN
  FOREACH r IN ARRAY ARRAY['bzb_leser_bpol', 'bzb_leser_sta', 'bzb_leser_thw',
                           'bzb_leser_zoll', 'bzb_leser']
  LOOP
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('CREATE ROLE %I NOLOGIN', r);
    END IF;
  END LOOP;
END $$;

-- bzb_leser = alle Themen + Funktion bzb_ows.zustaendigkeiten()
GRANT bzb_leser_bpol, bzb_leser_sta, bzb_leser_thw, bzb_leser_zoll TO bzb_leser;

COMMENT ON ROLE bzb_leser_bpol IS 'Lesezugriff BZB Thema Bundespolizei (bzb_ows.bpol_*)';
COMMENT ON ROLE bzb_leser_sta  IS 'Lesezugriff BZB Thema Staatsanwaltschaften (bzb_ows.sta_*)';
COMMENT ON ROLE bzb_leser_thw  IS 'Lesezugriff BZB Thema THW (bzb_ows.thw_*)';
COMMENT ON ROLE bzb_leser_zoll IS 'Lesezugriff BZB Thema Zoll (bzb_ows.zoll_*)';
COMMENT ON ROLE bzb_leser      IS 'Lesezugriff auf alle BZB-Themen inkl. Punktabfrage';

-- Beispiel Dienstkonto (Passwort außerhalb der Versionsverwaltung setzen):
--   CREATE ROLE geoserver_bzb LOGIN IN ROLE bzb_leser;
--   \password geoserver_bzb
