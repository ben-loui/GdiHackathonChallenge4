# Behördenresolver für Kategorie und Koordinate

Eingabe: eine der **36 Behördenkategorien** sowie `lat` und `lon` in WGS84. Ausgabe: vollständige Quelltreffer einschließlich Behördenname, Zuständigkeitsgeometrie, Originalattributen, Quelle, Lizenz und Abdeckungskennzeichnung. Im Standardmodus werden passende Fach-WFS direkt abgefragt und lokale PostGIS-Ergänzungen genutzt. Findet die abgeschlossene Flächensuche keinen Treffer, werden nahegelegene **Standortpunkte** angeboten.

**Nicht alle 36 Kategorien haben bundesweit belegte Zuständigkeitsflächen.** Vier besitzen bundesweit angebotene BZB-Open-Layer. Weitere Flächen kommen aus GEMFA und regionalen Diensten bzw. ausdrücklich belegten Zuordnungen. Amtliche Standortdaten sowie ein begrenzter OSM-Abzug im Raum Mainz/Wiesbaden erweitern die Kontaktmöglichkeiten. Der OSM-Bestand ist ausdrücklich keine bundesweite Standortabdeckung. Der gemessene Lieferstand für jede Kategorie und die Quellen stehen in [docs/ABDECKUNG.md](docs/ABDECKUNG.md) und [data/coverage-summary.json](data/coverage-summary.json).

Das vorhandene `../behoerden-matcher` wurde nicht verändert; die 36 Kennungen und Aliasse sind übernommen. Es kann weiterhin Anliegen in Kategorien übersetzen und dann diesen eigenständigen Resolver aufrufen.

## Schnellstart mit den mitgelieferten echten Daten

Voraussetzung: gestartetes Docker Desktop bzw. Docker Engine mit Compose. Die Datenbank bindet lokal an `127.0.0.1:55432`. Auf Apple Silicon wird das offizielle PostGIS-Image in AMD64-Emulation gestartet; der Python-Container wird nativ gebaut. Ein vorhandener PostgreSQL-Server kann alternativ per `DATABASE_URL` verwendet werden.

```bash
cd ~/Desktop/GdiHackathonChallenge4/behoerden-resolver
docker compose up -d db
docker compose build cli
docker compose run --rm cli load
docker compose run --rm cli coverage
```

`load` verwendet pro Quelle den jüngsten vollständigen Snapshot unter `data/snapshots`. Es benötigt **keinen WFS-Zugriff**; beim ersten Containerbau werden jedoch Images und Python-Pakete heruntergeladen. Die Datenbank enthält anschließend echte importierte Daten, keine Testquadrate. Die synthetischen Testdaten liegen ausschließlich in einer getrennten Testdatenbank.

```bash
# Endpunkt + Layer + Filter + Lizenz + Prüfbelege, ohne DB-Verbindung:
docker compose run --rm cli plan kreisverwaltung
docker compose run --rm cli plan jobcenter

# Allgemeiner Jobcenterbezirk am Beispielpunkt in Mannheim:
docker compose run --rm cli resolve jobcenter --lon 8.466 --lat 49.488

# Beispielpunkt im Landkreis München:
docker compose run --rm cli resolve kreisverwaltung --lon 11.615 --lat 48.065

# Der vollständige Eintrag einschließlich Geometrie kommt immer zurück:
docker compose run --rm cli resolve amtsgericht --lon 8.27 --lat 50.0

# Lokal und offline suchen, Standortvorschläge bis 40 km erlauben:
docker compose run --rm cli resolve gesundheitsamt --lon 11.589 --lat 50.927 --backend local --radius-km 40

# Ausschließlich Flächentreffer akzeptieren:
docker compose run --rm cli resolve gesundheitsamt --lon 11.589 --lat 50.927 --no-point-fallback

# Korrekte Behandlung einer ortsunabhängigen Kategorie:
docker compose run --rm cli resolve krankenkasse --lon 8.27 --lat 50.0
```

Alle Ausgaben sind JSON; Fortschritt und Fehler gehen nach stderr. Unbekannte Kategorien und ungültige Koordinaten sind Fehler. Länge (`lon`) und Breite (`lat`) werden ausdrücklich getrennt übergeben.

## Reihenfolge und Antwort

1. `--backend auto` fragt die für den Ort relevanten Fach-WFS mit einer kleinen BBOX im unterstützten CRS ab. Anschließend wird der Punkt gegen das vollständige Polygon geprüft, einschließlich Löchern und Grenzen. Reine VG25-Verwaltungsgrenzen sind keine Fachzuständigkeitsnachweise.
2. Ohne WFS-Flächentreffer werden konfigurierte lokale Ergänzungen geprüft. Gibt es keinen passenden Fach-WFS, beginnt die Suche lokal. `--backend local` nutzt ausschließlich die importierten Flächen. `--backend wfs` erzwingt die Live-Flächensuche; vor einem Standortersatz werden trotzdem vorhandene lokale Flächenergänzungen geprüft.
3. Erst ohne passenden Flächentreffer wird `behoerden.locations` nach geodätischer Entfernung durchsucht. Ein WFS-Ausfall ist ein Fehler, keine festgestellte Abdeckungslücke; daraus entsteht kein stiller Standortersatz. Der lokale Modus steht für bewussten Betrieb mit dem importierten Datenstand bereit.

Jeder Flächentreffer enthält die **gesamte gespeicherte oder vom WFS gelieferte Geometrie**, Originalattribute unter `properties`, Quellen-ID, Feature-ID, Name, Datum, Lizenz und ggf. Reparaturkennzeichen. Bei GEMFA bedeutet diese Geometrie ausdrücklich nur die belegte Teilmenge des Bezirks; `geometry_completeness` weist das aus. Sonderzuständigkeiten werden nicht behauptet. `status=ambiguous` liefert alle passenden Quelltreffer, beispielsweise Haupt- und Außenstelle; es gibt keine willkürliche Auswahl.

Standortersatz liefert dieselbe Struktur mit einer **Point-Geometrie** und zusätzlichen Feldern:

```json
{
  "status": "nearby_candidate",
  "backend": "local_point_fallback",
  "fallback_used": true,
  "point_search": {"radius_km": 40, "count": 1, "limit": 3},
  "matches": [{
    "authority_name": "Name aus der Standortquelle",
    "geometry": {"type": "Point", "coordinates": [11.59164, 50.93027]},
    "distance_m": 408.39,
    "match_type": "nearest_point_fallback",
    "geometry_completeness": "location_only_no_jurisdiction_polygon",
    "jurisdiction_verified": false
  }]
}
```

Das gekürzte Beispiel erläutert das Antwortformat; echte Antworten enthalten die vollständigen Quellfelder und einen Warntext. Nähe ist ein **Anlaufhinweis**, keine belegte Zuständigkeit. Es werden keine erfundenen Zuständigkeitskreise erzeugt. Standard: bis zu drei Punkte (`--point-limit 1` für nur den nächsten), unterschiedliche Radien pro Kategorie in [fallback.json](src/behoerden_resolver/resources/fallback.json), etwa 20 km für Bürgeramt/Polizei und 40 km für Gesundheitsamt. `--radius-km` überschreibt den Radius (größer 0 bis 300 km); `--no-point-fallback` deaktiviert die Ergänzung.

Krankenkasse, Pflegekasse, Rentenversicherung und Bundesverwaltungsamt behalten `non_spatial`. Weitere aufgabenabhängige Kategorien behalten `context_required`. Ein eventuell mitgelieferter naher Kontaktpunkt beantwortet nicht die Frage nach Mitgliedschaft oder persönlicher Verfahrenszuständigkeit. `required_context` und die Kategoriehinweise bleiben enthalten.

`plan` zeigt die Quellen getrennt als `authority`, `authority_point` oder `boundary_reference` sowie lokale Ableitungen. Der Status `not_verified` eines ausgeschlossenen oder noch ungeprüften Endpunkts darf nicht als bestätigte Verfügbarkeit interpretiert werden. Die erfolgreiche Live-Prüfung ist nur für den angegebenen Prüfzeitpunkt belegt.

## Frisch von den amtlichen Diensten laden

```bash
# Prüft Capabilities, DescribeFeatureType und eine echte Geometrie je Quelle:
docker compose run --rm cli verify --output /data/verification-current.json

# Vollabruf der Standardlayer und atomarer Import pro Quelle:
docker compose run --rm cli sync

# Einzelne Quelle aktualisieren:
docker compose run --rm cli sync --source bzb_jobcenter

# Abruf und Import getrennt:
docker compose run --rm cli fetch --source by_kreis
docker compose run --rm cli load

# VG25-Gemeinden sind Standardabhängigkeit für GEMFA:
docker compose run --rm cli sync --source vg25_gem
```

Standardmäßig werden alle aktiven Quellen außer `vg25_gem` vollständig abgerufen. `sync --all` schließt diesen großen Layer ein. Vollständigkeit bezieht sich auf den **abgerufenen Layer zum Abrufzeitpunkt**, nicht auf das gesamte Verwaltungsrecht oder alle tatsächlich existierenden Behörden. Ein fachlich ungeeigneter Layer bleibt auch mit `--all` ausgeschlossen.

Ein fehlgeschlagener Layer führt zu Exitcode 2, während andere Quellen weiterbearbeitet werden. Nur vollständige Downloads erscheinen als neue Snapshots; nur erfolgreiche Datenbanktransaktionen ersetzen eine vorhandene Quelle. Ein Neustart beginnt einen abgebrochenen Layer erneut. Andere bereits gespeicherte Snapshots bleiben erhalten. Die WFS bieten keinen garantiert transaktionsfesten Gesamtabzug: stabile Sortierung, Feature-ID-Prüfung, gleichbleibende Gesamtzahlen und Endseitenkontrollen reduzieren dieses Risiko, beweisen aber keine zeitpunktgenaue Konsistenz bei parallelen Änderungen des Anbieters.

Der mitgelieferte OSM-Abzug umfasst ausschließlich einen erfolgreich geladenen Suchbereich von 10 km um 50.0 N, 8.27 E (Raum Mainz/Wiesbaden). Größere Deutschlandabfragen und ein Versuch mit 16 Stadtbereichen scheiterten an Zeitlimits; ihre unvollständigen Antworten wurden nicht importiert. Daher wird daraus keine bundesweite Punktabdeckung behauptet. OSM wird nur ausdrücklich als Batch aktualisiert, nicht bei jeder Suche:

```bash
docker compose run --rm cli sync --source osm_locations
```

Die verwendete Abfrage steht in `resources/osm_query.overpass`, ihre Prüfsumme im Quellenmanifest. Eine Erweiterung braucht eine entsprechend geänderte Abfrage, Quellenkonfiguration und neue Abdeckungsmessung. Öffentliche Overpass-Dienste sind kein verlässlicher Massendatenbetrieb; für große regelmäßige Aktualisierungen eignen sich Extrakte oder ein eigener Dienst. Die Resolverabfrage selbst nutzt stets den lokalen Standortindex.

## Datenmodell und Abfrage

Das Schema `behoerden` enthält:

| Tabelle | Inhalt |
| --- | --- |
| `authorities` | Gemeinsame, nach Kategorie partitionierte Behördendaten |
| `finanzamt`, `jobcenter`, … | 36 echte Kategoriepartitionen, auch wenn derzeit leer |
| `boundaries` | VG25-Verwaltungsgebiete ohne behaupteten Behördennamen |
| `locations` | Echte Standortpunkte mit Quelle, Originalattributen und lokalem Entfernungsindex; keine Zuständigkeitsflächen |
| `categories` | Alle Kategorien, Auflösungsmodus und Einschränkungen |
| `sources` | Endpunkte, Layer, Filter, Herkunft, Lizenz und Verarbeitung |
| `import_runs` | Importzeit, Snapshotmanifest, Abrufzeiten, Prüfsummen und Anzahl |

Behördenzeilen enthalten `authority_name` (vollständiger Quellname), `geom` (`MultiPolygon`, EPSG:4326), `category`, Quell-ID, Gebietsumfang, Quelldatum soweit vorhanden, Beleglink und die ursprünglichen Attribute. In Bayern werden `bezeichnungZusatz` und `bezeichnung` nur dort zusammengesetzt, wo beide amtliche Felder vorliegen, z. B. `Landratsamt` + `Tirschenreuth`. Es werden keine Namen aus VG25-Gebietsbezeichnungen erfunden. Getrennte geometrische Teile und Dienststellen können mehrere Quellzeilen derselben Institution ergeben; Zeilenzahlen sind deshalb keine garantierten Zahlen unterschiedlicher Rechtsträger.

```sql
SELECT authority_name, category, source_id, evidence_url
FROM behoerden.jobcenter
WHERE geom && ST_SetSRID(ST_Point(8.466, 49.488), 4326)
  AND ST_Covers(geom, ST_SetSRID(ST_Point(8.466, 49.488), 4326));
```

GiST-Indizes beschleunigen die räumliche Suche. `ST_Covers` zählt Grenzpunkte mit; mehrere Treffer werden vollständig zurückgegeben. `candidate` ist ein allgemeiner territorialer Kandidat, `ambiguous` sind mehrere Quelltreffer. `no_coverage_at_point` bedeutet, dass lokal Daten dieser Kategorie vorliegen, aber keine Fläche den Punkt abdeckt. Es bedeutet **nicht**, dass dort keine Behörde zuständig wäre. `no_local_data` kennzeichnet eine leere Kategorietabelle.

Bei Gerichten muss der Punkt den verfahrensrechtlich maßgeblichen Ort repräsentieren; der Wohnort allein bestimmt nicht jedes Verfahren. Sonderzuständigkeiten, Steuerarten, Schularten, Kammermitgliedschaft, Auslandsbezug und persönliche Voraussetzungen werden nicht aus dem Polygon abgeleitet. Die Maßstäbe unterscheiden sich: BZB Open verwendet generalisierte VG250-Grundlagen, VG25 ist genauer. Ein genaueres Verwaltungsgebiet verbessert nicht automatisch die Genauigkeit eines anders abgegrenzten Fachbezirks. Grenzen werden weder automatisch aneinander angepasst noch vereinfacht.

## GEMFA und weitere Ergänzungen

**GEMFA ist integriert.** Der vollständige BZSt-XML-Export und sein Schema werden heruntergeladen. Eindeutige ganze Gemeinden werden über ihren exakten AGS mit VG25 verbunden. Geteilte Gemeinden, widersprechende Adressregeln und fehlende Schlüssel bleiben aus der Flächenableitung ausgeschlossen. Für 411 Finanzämter entstehen belegte Teilflächen; keine Behauptung eines vollständigen Finanzamtsbezirks. Bayern und Hamburg ergänzen echte Fachpolygone. `assignment_audit` im GEMFA-Snapshot dokumentiert Ein- und Ausschlüsse sowie den Quelldatenstand.

Zusätzliche regionale Integrationen umfassen Polizei Brandenburg, Schulämter Hessen und Thüringen, Landratsämter Sachsen und ausdrücklich benannte Regierungsbehörden in Baden-Württemberg, Hessen und Nordrhein-Westfalen. Bayern liefert außerdem amtliche Standortlayer; Thüringen liefert Gesundheits-, Veterinär- und Jugendamtsstandorte. Datenstand und tatsächliche regionale Abdeckung sind je Kategorie dokumentiert.

## Quellen, Lizenzen und Ausschlüsse

Das vollständige maschinenlesbare Quellen-/Lizenzmanifest ist [sources.json](src/behoerden_resolver/resources/sources.json). Dort stehen pro Layer der genaue Endpunkt, amtliche Filter, Namensregel, Raumumfang, Lizenz-URL, erforderliche Namensnennung und Verarbeitungshinweise. [verification.json](src/behoerden_resolver/resources/verification.json) enthält die ausgeführten Live-Prüfungen mit Abruf-URLs und Antwort-Prüfsummen. Jeder Snapshot enthält zusätzlich sein eigenes Manifest, normalisierte echte Daten und komprimierte Rohantworten.

- **BKG BZB Open**: `https://sgx.geodatenzentrum.de/wfs_bzb_open`; Layer `bzb-open:gerichte_amtsgerichte`, `bzb-open:gerichte_landgerichte`, `bzb-open:ba_jobcenter`, `bzb-open:ba_arbeitsagenturen`. Lizenz **Datenlizenz Deutschland – Namensnennung 2.0**. [Amtliche Produktdokumentation](https://sg.geodatenzentrum.de/web_public/gdz/dokumentation/deu/bzb-open.pdf).
- **BKG VG25**: `https://sgx.geodatenzentrum.de/wfs_vg25`; Layer `vg25:vg25_krs`, `vg25:vg25_rbz`, `vg25:vg25_gem`. Lizenz **CC BY 4.0**, nicht ungeprüft die Lizenz älterer BKG-Produkte übernehmen. [Amtliche Produktseite](https://gdz.bkg.bund.de/index.php/default/wfs-verwaltungsgebiete-1-25-000-stand-31-12-wfs-vg25.html).
- **Verwaltungsatlas Bayern**: Ressort-WFS unter `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_…-wfs`; genaue Layernamen im Manifest. Lizenz **CC BY 4.0**, Namensnennung je Ressort gemäß Capabilities. [Amtliches Diensteverzeichnis](https://geoportal.bayern.de/geoportalbayern/seiten/dienste).

**Öffentlich erreichbar ist nicht automatisch frei nutzbar.** Das separate BKG-Produkt **BZB ohne „Open“** für u.a. Zoll, Bundespolizei und Staatsanwaltschaften ist auf bestimmte Nutzungsberechtigte beschränkt und wird nicht importiert. Der bayerische gemischte Gerichts-/Staatsanwaltschaftslayer liefert dagegen explizite, frei nutzbare regionale Staatsanwaltschaftsdatensätze. Kein Layer wird nur aufgrund eines ähnlich klingenden Namens einer anderen Behördenart zugeschlagen.

Ein konkreter Live-Befund: `stmi:VerwaltungsgerichtsbarkeitFlaeche` lieferte am Prüfdatum nur Verwaltungsgerichtshof und Landesanwaltschaft, während der Punktlayer auch Verwaltungsgerichte nennt. Dieser direkte Flächenlayer bleibt fachlich ausgeschlossen. **Die sechs Verwaltungsgerichtsbezirke werden stattdessen lokal aus der expliziten Zuordnung in [Art. 1 Abs. 2 AGVwGO](https://www.gesetze-bayern.de/Content/Document/BayAGVwGO-1) und den sieben VG25-Regierungsbezirken gebildet.** Die amtlichen Gerichtsnamen stammen aus dem Punktlayer, die Gebiete aus der gesetzlichen Zuordnung. Die überprüfte [Zuordnungstabelle](src/behoerden_resolver/resources/by_courts.csv) und ihr Prüftermin stehen im Manifest. Gesetzesänderungen müssen redaktionell geprüft werden; ein neuer Geometrieabruf aktualisiert diese Zuordnung nicht automatisch. Siehe [docs/RECHERCHE.md](docs/RECHERCHE.md) auch für die Quellenstrategie der nicht abgedeckten Kategorien.

Bei Nutzung/Weitergabe der Daten müssen die Namensnennungen aus dem Manifest einschließlich Datenurheber-/Quellenverweisen sichtbar mitgeführt werden. Die Verarbeitung umfasst CRS-Transformation, Untergruppenfilter und ggf. `make_valid`: alle Polygonteile bleiben erhalten; kollabierte Linien-/Punktreste ohne Fläche können entfernt werden. Reparierte Datensätze sind mit `geometry_repaired=true` gekennzeichnet. Rohantworten bleiben zur Kontrolle erhalten. Die Datenlizenzen sind unabhängig von der MIT-Lizenz des neu erstellten Programmcodes. Insbesondere stehen OpenStreetMap-Standorte unter **ODbL 1.0**, © OpenStreetMap-Mitwirkende; bei Weitergabe gelten deren Namensnennungs- und einschlägige Share-Alike-Pflichten. Sie sind als Gemeinschaftsdaten gekennzeichnet und bleiben vom amtlichen Flächenbestand unterscheidbar. Siehe [OSM-Lizenz](https://www.openstreetmap.org/copyright).

## Python und Einbindung in das vorhandene Projekt

Für die festgeschriebenen Paketversionen wird Python 3.12 oder neuer benötigt. Der Container bringt Python 3.12 bereits mit.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.lock
python -m pip install --no-deps -e .
export DATABASE_URL='postgresql://resolver:resolver-local@127.0.0.1:55432/authorities'
behoerden-resolver plan Kreisverwaltung
behoerden-resolver load
behoerden-resolver resolve jobcenter --lon 8.466 --lat 49.488
```

```python
from behoerden_resolver.resolver import resolve

# Den Kategoriecode des FIM-Matchers explizit übergeben:
result = resolve("jobcenter", lon=8.466, lat=49.488)
```

Die beiden Pakete besitzen unterschiedliche Python-Namensräume. Das bestehende Projekt muss für diese Nutzung nicht umgebaut werden. Eine automatische Freitextklassifikation oder eine neue Benutzeroberfläche ist nicht Bestandteil dieses räumlichen Moduls.

## Tests und Betrieb

```bash
python -m pip install -e '.[test]'
python -m pytest -q

# Einmalig separate, leere Testdatenbank im Entwicklungscontainer anlegen:
docker compose exec -T db createdb -U resolver authorities_test
TEST_DATABASE_URL='postgresql://resolver:resolver-local@127.0.0.1:55432/authorities_test' python -m pytest -q
```

Die PostGIS-Tests verweigern Datenbanknamen ohne `_test` am Ende. Geprüft werden u.a. Polygonlöcher, Grenzmehrdeutigkeit, Kategoriepartitionen, Idempotenz sowie Erhalt der alten Daten nach einem fehlerhaften Ersatzimport. Offline-Tests prüfen Paging, geänderte Gesamtzahlen, wiederholte IDs, GML/CRS, Fachfilter und Prüfsummen. Live-Verifikation ist getrennt, damit ein Dienstausfall keinen erfolgreichen Offline-Test vortäuscht. Ergebnisse dieses Lieferstands: [docs/VALIDIERUNG.md](docs/VALIDIERUNG.md).

`docker compose stop` hält die Datenbank an und bewahrt das Volume. `docker compose down` entfernt Container und Netzwerk, bewahrt das Volume ebenfalls. Ein neues Passwort kann über eine Kopie von `.env.example` gesetzt werden; bei einem bereits initialisierten PostgreSQL-Volume ändert eine neue Umgebungsvariable das gespeicherte Datenbankpasswort nicht automatisch. Für mehrere Projekte ist ein eigener Port konfigurierbar.

Falls Python auf macOS den lokalen Zertifikatsspeicher nicht findet, kann auf diesem Rechner `SSL_CERT_FILE=/etc/ssl/cert.pem` gesetzt werden. In einer Organisation mit eigener CA einen passenden CA-Bundle-Pfad verwenden. Die TLS-Prüfung wird nicht abgeschaltet.

## Erweiterte Quellen (Berlin, Baden-Württemberg, OSM je Land)

Zusätzlich eingebunden: Polizeiabschnitte Berlin (`be_polizei_abschnitt`, projiziertes GeoJSON, EPSG:25833), Polizei Baden-Württemberg als INSPIRE-WFS (`bw_polizei_areas` Flächen, `bw_polizei_locations` Standorte) sowie der opt-in OSM-Abzug je Bundesland (`scripts/osm_fetch_states.py`, Quelle `osm_states_locations`). `be_bezirke_gesetz` (Bezirksämter) ist Opt-in und braucht eine rechtliche Prüfung, bevor es aktiviert wird. Quellen, Befehle, offene Kandidaten und Grenzen: [docs/ERWEITERUNG_QUELLEN.md](docs/ERWEITERUNG_QUELLEN.md). Neue Quellen müssen lokal mit `verify`/`fetch` und `pytest` geprüft werden; die Abdeckung danach mit `python scripts/report.py` neu messen.

## Erweiterung

Neue Zuordnungen brauchen einen nachprüfbaren Behördennamen **und** einen belegten Gebietsschlüssel oder Fachpolygonbezug sowie eine passende freie Lizenz. Gemeinde-/Kreisgrenzen lassen sich erst nach einer solchen expliziten Zuordnung räumlich verknüpfen. Ein vorhandener Ämtername, Adresspunkt, FIM-Behördentyp, nächstgelegenes Büro oder eine allgemeine Landesregel genügt für eine belegte Zuständigkeitsfläche nicht. Echte Standorte können separat mit `kind=authority_point` importiert werden und stehen ausschließlich für die markierte Näheergänzung bereit. Ergänzte Quellen in `sources.json` müssen durch `verify`, einen kompletten `fetch`, Fachfilterprüfung und anschließende räumliche Stichproben gehen. Weitere WFS-Formate benötigen einen expliziten Adapter; der vorhandene GML-Adapter ist absichtlich auf die beobachteten Strukturen begrenzt.


Die vollständige Abdeckungsdokumentation liegt zusätzlich als [Word-Dokument](docs/Behoerdenresolver_Abdeckung_und_Quellen.docx) vor. Die bearbeitbare Markdown-Version wird mit `python scripts/report.py` aus der laufenden Datenbank neu erzeugt. Für die Word-Fassung kann optional `python -m pip install -e '.[docs]'` und danach `python scripts/create_document.py` verwendet werden. Der gelieferte Word-Stand wurde gerendert und auf allen neun Seiten visuell geprüft.
