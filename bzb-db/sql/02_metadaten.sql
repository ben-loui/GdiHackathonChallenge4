-- =============================================================================
-- BZB – Produkt-, Themen- und Datensatzmetadaten (Upsert, idempotent)
--
-- Je Lieferung prüfen: Stände laut dokumentation/bzb.pdf, Kap. 3.2.
-- produktstand setzt laden.sh zusätzlich aus dokumentation/aktualitaet.txt.
-- =============================================================================
\set ON_ERROR_STOP on
BEGIN;

INSERT INTO bzb.produkt (produkt_id, bezeichnung, produktstand, anbieter,
                         datenquellen_url, nutzungsbedingungen, kontakt)
VALUES ('BZB', 'Behördenzuständigkeitsbereiche', '2026-06',
        'Bundesamt für Kartographie und Geodäsie (BKG)',
        'https://sg.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_bzb.pdf',
        'Geldleistungsfrei für Bundesbehörden und Nutzungsberechtigte nach § 4 V GeoBund, je nach Vertrag alle oder ausgewählte. Quellenvermerk ist anzubringen.',
        'BKG Dienstleistungszentrum, dlz@bkg.bund.de')
ON CONFLICT (produkt_id) DO UPDATE SET
  bezeichnung = EXCLUDED.bezeichnung, produktstand = EXCLUDED.produktstand,
  anbieter = EXCLUDED.anbieter, datenquellen_url = EXCLUDED.datenquellen_url,
  nutzungsbedingungen = EXCLUDED.nutzungsbedingungen, kontakt = EXCLUDED.kontakt;

INSERT INTO bzb.thema (thema_id, bezeichnung, datenurheber, stand_fachdaten, referenzgeometrie, leserolle) VALUES
  ('BPOL', 'Bundespolizei',         '© Bundespolizei',                                              '2026-06', 'VG250 (31.12.2025)', 'bzb_leser_bpol'),
  ('STA',  'Staatsanwaltschaften',  '© Ministerium der Justiz und für Migration Baden-Württemberg', '2026-05', 'PLZ (2026-02)',      'bzb_leser_sta'),
  ('THW',  'Technisches Hilfswerk', '© Technisches Hilfswerk',                                      '2026-05', 'VG250 (31.12.2025)', 'bzb_leser_thw'),
  ('ZOLL', 'Zoll',                  '© Zoll',                                                       '2026-04', 'PLZ (2026-02)',      'bzb_leser_zoll')
ON CONFLICT (thema_id) DO UPDATE SET
  bezeichnung = EXCLUDED.bezeichnung, datenurheber = EXCLUDED.datenurheber,
  stand_fachdaten = EXCLUDED.stand_fachdaten, referenzgeometrie = EXCLUDED.referenzgeometrie,
  leserolle = EXCLUDED.leserolle;

INSERT INTO bzb.datensatz (datensatz_id, thema_id, quelle_layer, titel, beschreibung,
                           schlagwoerter, geometrietyp, darstellung, sortierung) VALUES
  ('bpol_direktionen', 'BPOL', 'BPOL_Direktionen',
   'Bundespolizei – Direktionen',
   'Zuständigkeitsbereiche der Bundespolizeidirektionen einschließlich des Direktionsbereichs Bundespolizei See. Grenzen auf Basis VG250.',
   '{Bundespolizei,Direktion,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 10),
  ('bpol_inspektionen', 'BPOL', 'BPOL_Inspektionen',
   'Bundespolizei – Inspektionen',
   'Zuständigkeitsbereiche der Bundespolizeiinspektionen. Grenzen auf Basis VG250, für Flughäfen und Bundesliegenschaften nach Angaben der Bundespolizei.',
   '{Bundespolizei,Inspektion,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 20),
  ('bpol_deu_aut', 'BPOL', 'BPOL_DEU_AUT',
   'Bundespolizei – 30-km-Zone Österreich',
   '30-km-Zone an der deutsch-österreichischen Grenze mit der jeweils zuständigen Inspektion.',
   '{Bundespolizei,Grenze,Österreich,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 30),
  ('bpol_inspektionen_250', 'BPOL', 'BPOL_Inspektionen_250',
   'Bundespolizei – Inspektionen (Übersicht)',
   'Für Übersichtskarten generalisierte Inspektionsflächen. Kleine Inspektionen sind als Punkte in bpol_inspektionen_250_p enthalten. Nicht für Zuständigkeitsabfragen verwenden.',
   '{Bundespolizei,Inspektion,Übersichtskarte}', 'MultiPolygon', 'uebersicht', 40),
  ('bpol_inspektionen_250_p', 'BPOL', 'BPOL_Inspektionen_250_p',
   'Bundespolizei – kleine Inspektionen (Übersicht, Punkte)',
   'Kleine Inspektionen (Flughäfen, Bundesliegenschaften) als Punkte für Übersichtskarten, ergänzend zu bpol_inspektionen_250.',
   '{Bundespolizei,Inspektion,Übersichtskarte}', 'Point', 'uebersicht', 50),
  ('sta_staatsanwaltschaften', 'STA', 'StA_Staatsanwaltschaften',
   'Staatsanwaltschaften',
   'Bezirke der Staatsanwaltschaften und ihrer Zweigstellen mit übergeordneter (General-)Staatsanwaltschaft. Grenzen auf Basis der Postleitzahlgebiete.',
   '{Staatsanwaltschaft,Justiz,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 110),
  ('thw_landesverband', 'THW', 'THW_Landesverband',
   'THW – Landesverbände',
   'Zuständigkeitsbereiche der Landesverbände des Technischen Hilfswerks. Grenzen auf Basis VG250.',
   '{THW,Bevölkerungsschutz,Landesverband,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 210),
  ('thw_regionalstellen', 'THW', 'THW_Regionalstellen',
   'THW – Regionalstellen',
   'Zuständigkeitsbereiche der Regionalstellen des Technischen Hilfswerks. Grenzen auf Basis VG250.',
   '{THW,Bevölkerungsschutz,Regionalstelle,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 220),
  ('zoll_hauptza', 'ZOLL', 'Zoll_HauptZA',
   'Zoll – Hauptzollämter',
   'Bezirke der Hauptzollämter. Grenzen auf Basis der Postleitzahlgebiete.',
   '{Zoll,Hauptzollamt,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 310),
  ('zoll_agrar', 'ZOLL', 'Zoll_Agrar',
   'Zoll – Agrardieselvergütung',
   'Zuständige Stellen für die Agrardieselvergütung.',
   '{Zoll,Agrardiesel,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 320),
  ('zoll_ausfuhr', 'ZOLL', 'Zoll_Ausfuhr',
   'Zoll – Ausfuhrzollstellen',
   'Zuständige Ausfuhrzollstellen. Flächen können sich überlappen, weil die Zuständigkeit teils von nicht verfügbaren Geometrien abhängt.',
   '{Zoll,Ausfuhr,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 330),
  ('zoll_fks', 'ZOLL', 'Zoll_FKS',
   'Zoll – Finanzkontrolle Schwarzarbeit',
   'Zuständige Stellen der Finanzkontrolle Schwarzarbeit.',
   '{Zoll,Schwarzarbeit,FKS,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 340),
  ('zoll_kfzsteuer', 'ZOLL', 'Zoll_KfzSteuer',
   'Zoll – Kfz-Steuer',
   'Für die Kfz-Steuer zuständige Hauptzollämter.',
   '{Zoll,Kfz-Steuer,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 350),
  ('zoll_kfzsteuerfest', 'ZOLL', 'Zoll_KfzSteuerFest',
   'Zoll – Kfz-Steuer-Festsetzungsstellen',
   'Zuständige Festsetzungsstellen für die Kfz-Steuer.',
   '{Zoll,Kfz-Steuer,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 360),
  ('zoll_strabu', 'ZOLL', 'Zoll_StraBu',
   'Zoll – Straf- und Bußgeldstellen',
   'Für Straf- und Bußgeldsachen zuständige Hauptzollämter.',
   '{Zoll,Bußgeld,Strafsachen,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 370),
  ('zoll_verwertung', 'ZOLL', 'Zoll_Verwertung',
   'Zoll – Verwertungsstellen',
   'Zuständige Verwertungsstellen.',
   '{Zoll,Verwertung,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 380),
  ('zoll_vollstreckung', 'ZOLL', 'Zoll_Vollstreckung',
   'Zoll – Vollstreckungsbezirke',
   'Zuständige Vollstreckungsstellen.',
   '{Zoll,Vollstreckung,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 390),
  ('zoll_zfa', 'ZOLL', 'Zoll_ZFA',
   'Zoll – Zollfahndungsämter',
   'Bezirke der Zollfahndungsämter.',
   '{Zoll,Zollfahndung,Zuständigkeit}', 'MultiPolygon', 'vollstaendig', 400)
ON CONFLICT (datensatz_id) DO UPDATE SET
  thema_id = EXCLUDED.thema_id, quelle_layer = EXCLUDED.quelle_layer,
  titel = EXCLUDED.titel, beschreibung = EXCLUDED.beschreibung,
  schlagwoerter = EXCLUDED.schlagwoerter, geometrietyp = EXCLUDED.geometrietyp,
  darstellung = EXCLUDED.darstellung, sortierung = EXCLUDED.sortierung;

COMMIT;
