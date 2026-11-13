# Ausgeführte Validierung am 13 November 2026

Diese Ergebnisse wurden mit den echten gelieferten Daten lokal und im Container ausgeführt.

- **35 Tests bestanden**, davon drei mit echter PostGIS-Testdatenbank und 32 ohne Netzwerk. Ausgabe: `data/test-results.txt`, JUnit: `data/test-results.xml`. Die Integrationstests nutzen ausschließlich eine Datenbank mit dem Suffix `_test` und werden ohne `TEST_DATABASE_URL` ausdrücklich übersprungen.
- PostgreSQL 16 und PostGIS 3.5 laufen im offiziellen Docker-Image. Auf diesem Apple-Silicon-Rechner wird das PostGIS-Image in AMD64-Emulation verwendet; der CLI-Container nutzt Python 3.12 nativ. Der finale Container wurde tatsächlich gebaut.
- **35 vollständige Snapshots** wurden mit `docker compose run --rm cli load` erfolgreich in die laufende Datenbank geladen. Gesamtmenge: 18.539 Zeilen aus 6.376 Behördenflächen, 767 Standortpunkten und 11.396 Grenzreferenzen. Erneutes Laden ersetzt Quellen und erhöht die Menge nicht. Ergebnis: `data/container-load-final.json`.
- **27 WFS-Layer live geprüft** mit Capabilities, DescribeFeatureType und tatsächlicher Geometrieabfrage; 1 weiterer technisch erreichbarer Layer ist fachlich ausgeschlossen. Prüfzeit und Antwortprüfsummen stehen in `resources/verification.json`. Das ist keine zeitlich unbegrenzte Verfügbarkeitsgarantie.
- Der VG25-Gemeindelayer wurde vollständig geladen. Der Gemeindeindikator in `ABDECKUNG.md` wurde gegen alle 10.974 tatsächlich vorhandenen AGS gemessen; eine Gemeinde wird nur einmal je Kategorie gezählt. Dieser Indikator ist keine Adress-, Bevölkerungs- oder Flächenvollständigkeit.
- Alle 6.376 Behördenpolygone, 11.396 Referenzpolygone und 767 Standortpunkte sind in PostGIS gültig. 2.508 Behördenzeilen und 6.122 Grenzreferenzen tragen ein Reparaturkennzeichen; abgeleitete Zeilen übernehmen auch Reparaturkennzeichen ihrer Ausgangsgeometrien. Alle Flächenteile und die Rohantworten bleiben nachvollziehbar.
- GEMFA wurde vollständig eingelesen, aber ausschließlich für eindeutig belegte ganze Gemeindezuordnungen ohne widersprechende Adressregeln polygonisiert. Die 411 Finanzamtszeilen sind ausdrücklich Teilmengen ihres jeweiligen Bezirks. Der Audit im Snapshot nennt ausgeschlossene und nicht auflösbare Schlüssel.
- Große OSM-Abfragen für Deutschland und 16 Stadtbereiche scheiterten an Zeitlimits. Keine Teilantwort wurde publiziert. Integriert wurde ausschließlich der vollständige 10-km-Abzug um Mainz/Wiesbaden: 33 kategorisierte Quellzeilen aus 109 gelieferten OSM-Elementen. Diese Menge ist keine bundesweite Punktabdeckung. Elf amtliche Punktquellen liefern die weiteren 734 Standortzeilen.

## Beobachtete Containerabfragen

| Kategorie und Punkt als Länge Breite | Ergebnis | Nachweis |
| --- | --- | --- |
| `jobcenter` 8.466 49.488 | Direkter Live-WFS: Jobcenter Mannheim, Universitätsstadt; vollständiges MultiPolygon; `fallback_used=false` | `data/container-wfs-jobcenter.json` |
| `gesundheitsamt` 11.589 50.927 | Lokale Standortergänzung: Stadtverwaltung Jena – Gesundheitsamt; Point; 408,39 m; `jurisdiction_verified=false` | `data/container-point-health.json` |
| `rentenversicherung` 8.27 50.0 | Naher OSM-Kontakt Deutsche Rentenversicherung; Point; 316,72 m; Status bleibt `non_spatial` | `data/container-point-context.json` |

Weitere echte Abfragen stehen in `data/queries-auto-live.json` und `data/query-point-fallbacks.json`: Hamburger Finanzamt direkt per WFS, Polizeiinspektion Potsdam direkt per WFS, Landratsamt Mittelsachsen lokal, Schulamt Frankfurt lokal und Bezirksregierung Köln lokal. Jena zeigt zusätzlich Veterinär- und Jugendamtsstandorte. Die Antworten enthalten Originalattribute, Lizenz und Quellenkennzeichnung. Ältere Prüfdateien können frühere Importläufe dokumentieren; die hier benannten finalen Containerdateien und das Liefermanifest beziehen sich auf den finalen Bestand.

## Was die Tests absichern

Die Tests prüfen die 36 Kategoriekennungen, unbekannte Kategorien, endliche WGS84-Koordinaten, örtlich nicht entscheidbare Kategorien, Polygonlöcher und Grenzmehrdeutigkeit, GML- und CRS-Verarbeitung, geänderte WFS-Zähler, Paging mit wiederholten IDs, unvollständige Antworten und Prüfsummen. Fachfilter und explizite Namensfelder bleiben maßgeblich. Ein erfolgreicher WFS-Treffer kommt ohne lokale Datenbank aus; ein WFS-Ausfall wird nicht verdeckt durch einen alten Cache oder Standort ersetzt.

Die Standorttests prüfen echte geodätische Entfernungen, Maximalradius, Kategorieauswahl, Sortierung und Abschaltbarkeit. Ein Flächentreffer verhindert jeden Aufruf der Standortsuche. Auch der ausdrücklich gewählte WFS-Modus darf eine vorhandene lokale Flächenergänzung nicht durch einen Punkt übergehen. Ein naher Kontaktpunkt ändert einen ortsunabhängigen Status nicht in eine behauptete Zuständigkeit. OSM-Antworten mit Timeout-Hinweis werden verworfen, Punkte außerhalb der Deutschlandmaske ausgeschlossen und Quellmittelpunkte als solche markiert.

PostGIS-Tests prüfen 36 reale Partitionen, idempotente Ersatzimporte und Rollback nach fehlerhafter Geometrie oder fremder Kategorie. Produktive Behördenzeilen werden nicht durch Testquadrate ersetzt. Der Testdatensatz ist ausschließlich in `authorities_test` gespeichert.

Die GitHub-Actions-Konfiguration ist für ein eigenständig veröffentlichtes Repository vorbereitet. Ein entfernter CI-Lauf wurde nicht ausgeführt. Individuelle Anspruchs-, Mitgliedschafts- und Verfahrenszuständigkeiten sowie alle Änderungen seit den jeweiligen Quelldatenständen sind nicht Gegenstand dieser räumlichen Prüfung.
