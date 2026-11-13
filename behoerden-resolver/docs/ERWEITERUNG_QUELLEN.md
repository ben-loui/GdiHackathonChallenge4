# Erweiterung der Quellen (Stand 2026-11-13)

Dieses Dokument ergänzt [ABDECKUNG.md](ABDECKUNG.md). Es beschreibt, welche Quellen seit der letzten gemessenen Abdeckung hinzukamen, welche mit dieser Erweiterung neu eingebunden wurden und welche Kandidaten bewusst noch nicht importiert werden.

**Wichtig:** Die Erweiterung wurde ohne Netzzugriff auf die Dienste aus der Entwicklungsumgebung erstellt. Capabilities, Schema und Beispielfeatures der neuen Dienste wurden vorab per Webabruf eingesehen; ein vollständiger `verify`/`fetch`, die Tests und eine neue Abdeckungsmessung (`python scripts/report.py`) müssen lokal ausgeführt werden. Bis dahin gelten die Zahlen unten nicht als gemessen.

## 1. Ausgangslage der gemessenen Abdeckung

Die Tabelle in `ABDECKUNG.md` (Messung 2026-11-13 18:05 UTC; 6.376 Flächeneinträge in 14 Kategorien, 767 Standorte) zeigt für Flächen:

| Gruppe | Kategorien | Gemeindeindikator (VG25-AGS) |
| --- | --- | --- |
| Bundesweit (BZB Open / GEMFA) | amtsgericht, landgericht, jobcenter, arbeitsagentur, finanzamt | 99,2–99,9 % |
| Regional | stadtverwaltung (36,2 %), regierungsprs (37,8 %), schulamt (29,6 %), kreisverwaltung (23,8 %), polizei (23,8 %), ihk/handwerkskammer/verwaltungsgericht (≈20 %), staatsanwaltschaft (18,8 %) | siehe Tabelle |
| Keine Fläche | auslaenderbehoerde, buergeramt, gesundheitsamt, gewerbeamt, jugendamt, ordnungsamt, veterinaeramt, zulassungsstelle u. a. | 0 % |

Nach dieser Messung wurden weitere Snapshots erzeugt, die die Tabelle noch nicht enthält: `by_wohngeld_gesetz` (96 Wohngeldbehörden, BY), `nw_bau_gesetz` (211 untere Bauaufsichten, NW), `bb_kommunal_gebiete` (141 Stadt-/Gemeindeverwaltungen und 14 Kreisverwaltungen, BB) sowie Standortquellen (u. a. `hh_jugend_asd_locations`, `bb_registry_locations`, `bb_kommunal_locations`, `nw_muenster_locations`, `sn_chemnitz_*`, `mv_rostock_locations`, `osm_exact_offices`). `python scripts/report.py` erzeugt `ABDECKUNG.md` und `data/coverage-summary.json` neu.

## 2. Neu eingebundene Quellen

| Quelle | Kategorie | Art | Land | Lizenz | Hinweis |
| --- | --- | --- | --- | --- | --- |
| `be_polizei_abschnitt` | polizei | Fläche (WFS, GeoJSON in EPSG:25833) | BE | dl-de/zero-2-0 | Polizeiabschnitte der Polizei Berlin, Name aus `langbezeic` mit Präfix „Polizei Berlin, “ |
| `bw_polizei_areas` | polizei | Fläche (INSPIRE-WFS, GML 3.2) | BW | dl-de/zero-2-0 | nur Features mit ausdrücklichem `areaOfResponsibilityByPolygon` und `policeService` |
| `bw_polizei_locations` | polizei | Standort | BW | dl-de/zero-2-0 | derselbe Dienst, nur Standortpunkte (Anlaufhinweis) |
| `osm_states_locations` | 35 Kategorien (nur bei passenden Tags/Namen) | Standort, Opt-in | DE | ODbL-1.0 | je Bundesland eine Overpass-Abfrage, siehe 4. |
| `be_bezirke_gesetz` | jugendamt, gesundheitsamt, veterinaeramt, wohngeldstelle, ordnungsamt | Fläche, **Opt-in, rechtliche Prüfung nötig** | BE | dl-de/zero-2-0 | Bezirksgrenzen als allgemeiner Zuständigkeitsbezirk des Bezirksamts |

Technische Voraussetzungen, die dafür ergänzt wurden:

- `geojson_crs` in `sources.json`: projiziertes GeoJSON (z. B. GeoServer mit `srsName=EPSG:25833`). Das `crs`-Member der Antwort muss vorhanden sein und exakt zum deklarierten CRS passen; sonst bricht der Import ab. Die Koordinaten werden danach nach WGS84 umprojiziert, ohne Vereinfachung. Gilt auch für die Live-Abfrage (`resolve`).
- `name_suffix_literal` in den Routen, analog zu `name_prefix_literal`.
- `inspire_govserv.py`: Adapter für `us-govserv:GovernmentalService`. Er vergleicht die Mitgliederzahl mit `resultType=hits`; ist `numberMatched` dort `unknown`, wird das im Manifest als `unverifiable_numberMatched_unknown` vermerkt. Doppelte `gml:id`, fehlende Namen und nicht-polizeiliche Dienste werden nicht still übernommen (Letztere werden im Audit gezählt).

### Berlin-Bezirke (Opt-in)

`be_bezirke_gesetz` ist **nicht** Teil des Standardimports und wird nicht live abgefragt (`default_import: false`, `legal_review_required: true`). Der Name lautet „Bezirksamt <Bezirk> von Berlin“; Fachamtsnamen werden nicht erfunden. Bürgerämter und Standesämter sind bewusst nicht geroutet (Berlin erlaubt bezirksübergreifende Inanspruchnahme), ebenso wenig landesweite Zuständigkeiten (Ausländerbehörde, Kfz-Zulassung). Vor der Aktivierung (`sync --source be_bezirke_gesetz`) sind die Zuordnungen je Kategorie gegen Verfassung von Berlin, BezVG und Allgemeines Zuständigkeitsgesetz zu prüfen und der Prüfvermerk im Quelleneintrag zu ergänzen.

## 3. Befehle

```bash
docker compose run --rm cli verify --source be_polizei_abschnitt --source bw_polizei_areas --output /data/verification-erweiterung.json
docker compose run --rm cli sync --source be_polizei_abschnitt --source bw_polizei_areas --source bw_polizei_locations
docker compose run --rm cli resolve polizei --lon 13.3777 --lat 52.5163     # Berlin
docker compose run --rm cli resolve polizei --lon 9.1829 --lat 48.7758      # Stuttgart
```

`verify` prüft nur die Formate `geojson` und `gml`; die INSPIRE-Quellen werden beim `fetch` strikt geprüft (Anzahl, IDs, Namen, Geometrie). Alle neuen WFS-Quellen sind im Quellenmanifest mit `verification_required: true` markiert.

## 4. OSM je Bundesland

Die bundesweite Overpass-Abfrage lief in Zeitlimits. `scripts/osm_fetch_states.py` fragt stattdessen alle 16 Länder einzeln ab, cacht jede validierte Antwort (Wiederaufnahme nach Abbruch) und schreibt nur dann eine Ausgabedatei, wenn **alle** Länder vollständig waren (kein `remark`, Zeitstempel vorhanden):

```bash
python scripts/osm_fetch_states.py --out data/osm_states.json --pause 15
docker compose run --rm cli sync --source osm_states_locations --input data/osm_states.json
```

Die Abfragevorlage `resources/osm_states.overpass` ist über `query_sha256` an die Quellenkonfiguration gebunden. OSM-Standorte bleiben Gemeinschaftsdaten (ODbL), werden nie als Zuständigkeitsfläche behandelt und stehen nur im Standort-Fallback bereit. Für regelmäßige Läufe eine eigene Overpass-Instanz oder einen Extrakt verwenden.

## 5. Recherchierte, noch nicht importierte Kandidaten

| Kandidat | Status |
| --- | --- |
| Berlin Polizeidirektionen, Kontaktbereiche, Wachen (`polizei:d_/b_/a_*`, derselbe Dienst wie die Abschnitte) | Layer laut Capabilities vorhanden; Attributnamen der Direktionen/Wachen nicht geprüft; Abschnitte decken die Fläche bereits ab |
| Saarland Polizeistandorte, BW Schulamts-Standorte, Dortmund (Gesundheitsamt, Jugendamt, Finanzamt als GeoJSON) | Hinweise aus der Recherche; Endpunkt, Lizenz und Schema nicht verifiziert |
| BZB Open (nicht offene BZB-Layer) | Nutzung nicht frei; ausgeschlossen |
| Hamburg Behördenfinder | keine nachgewiesene offene Lizenz für Gebiete; ausgeschlossen |

Neue Kandidaten werden nur mit dokumentierter Lizenz, geprüften Capabilities/Schema und einem vollständigen `fetch` aufgenommen.

## 6. Weiterhin nicht flächig belegbar

Für `auslaenderbehoerde`, `buergeramt`, `gewerbeamt`, `zulassungsstelle`, `strassenverkehrsbehoerde`, `sozialamt`, `umweltamt` und `bafoegamt` fehlt bundesweit eine offene Gebietsquelle; dort bleiben Standorte mit Entfernungsfallback bzw. der Status `context_required`. Das ist kein Defizit der Implementierung, sondern die Datenlage: Die Zuständigkeit folgt häufig Land- oder Kommunalrecht oder Wahlfreiheit.
