# Quellenentscheidung, geprüft am 13. November 2026

Der Import wird auf belegte, frei verwendbare Gebietsdaten und explizite Zuordnungen begrenzt. „Nicht importiert“ bedeutet, dass in diesem Lieferstand kein ausreichend belegter und lizenzierter Import eingerichtet wurde. Es ist keine Behauptung, dass weltweit kein passender Datensatz existiere. Das Quellenmanifest dokumentiert die tatsächlich unterstützten Dienste; diese Datei beschreibt die Grenzen und Erweiterungswege.

## Bundesweite Fachgebiete und Verwaltungsgrenzen

[BKG BZB Open](https://sg.geodatenzentrum.de/web_public/gdz/dokumentation/deu/bzb-open.pdf) bietet allgemeine Gerichts- und Arbeitsmarktbezirke. Vier passende Kategorien sind eingerichtet und vollständig abgerufen. Die zusätzlichen BZB-Open-Layer für Oberlandesgerichte, Geschäftsstellen und Regionaldirektionen werden nicht mit einer der 36 anderen Kategorien gleichgesetzt.

[VG25](https://gdz.bkg.bund.de/index.php/default/wfs-verwaltungsgebiete-1-25-000-stand-31-12-wfs-vg25.html) liefert Kreise, Regierungsbezirke und Gemeinden. `GEN` ist eine Gebietsbezeichnung. Ohne explizite Organisationszuordnung darf daraus weder ein vollständiger Behördenname noch die Zuständigkeit eines kommunalen Fachamts entstehen. Deshalb gibt es eine getrennte Tabelle `boundaries`. Der Gemeindelayer ist vollständig geladen und bildet die Grenzgrundlage für GEMFA. Er bleibt zugleich eine getrennte Verwaltungsgebietsreferenz.

Der getrennte [BKG-BZB-Dienst ohne Open](https://gdz.bkg.bund.de/index.php/default/wfs-behordenzustandigkeitsbereiche-wfs-bzb.html) wird als zugangsbeschränkte Quelle dokumentiert und nicht als frei nutzbare Grundlage für Zoll oder Bundespolizei ausgegeben. Bundespolizei wäre zudem keine allgemeine Landespolizei.

## Regionale Daten: Verwaltungsatlas Bayern

Das [amtliche Diensteverzeichnis](https://geoportal.bayern.de/geoportalbayern/seiten/dienste) nennt die Ressortdienste. Capabilities und tatsächliche Features wurden direkt geprüft. Die Namensnennung aus dem jeweiligen Dienst steht unverändert im maschinenlesbaren Manifest.

- `KreisverwaltungsbehoerdenFlaeche` enthält Landratsämter, kreisfreie Städte, die Landeshauptstadt und Bezirksverwaltungen. Nur die ersten drei Gruppen werden den passenden Kategorien zugeordnet; Bezirksverwaltungen werden nicht als Landratsämter behandelt.
- `SteuerverwaltungFlaeche` enthält neben Finanzämtern auch Landesamt und Finanzschule. Die Untergruppenfilter schließen Letztere aus. Hauptstelle und Außen-/Dienststellen können sich räumlich überlagern.
- `PolizeiinspektionenFlaeche` enthält auch Fahndungsstellen und vier Einträge ohne Untergruppe. Ohne belegte Gruppenzuordnung werden sie nicht in die allgemeine Inspektionskategorie übernommen. Manche Institutionen haben mehrere räumliche Quellfeatures mit derselben institutionellen `id`; die eindeutigen `gml:id` werden erhalten.
- Der gemischte Landgerichts-/Staatsanwaltschaftslayer enthält ausdrücklich beide Arten. Nur `staatsanwaltschaften` werden für diese Kategorie übernommen; die bundesweiten Landgerichte kommen aus BZB Open.
- Kammern und Schulämter haben eigene Flächenlayer. Sie sind kein Ersatz für eine Mitgliedschafts-, Schulart- oder Fallprüfung.

Der direkte Flächenlayer `VerwaltungsgerichtsbarkeitFlaeche` ist ein Beispiel dafür, warum ein plausibler Titel nicht reicht: Die vollständige Live-Abfrage enthielt nur vier andere Institutionen (Verwaltungsgerichtshof, dessen auswärtige Senate, Landesanwaltschaft und ihre Außenstelle), keine Verwaltungsgerichte erster Instanz. Die sechs erstinstanzlichen Gerichte finden sich im Standortlayer; die Punkte sind keine Gebiete.

Für diese Kategorie wird stattdessen eine **explizite gesetzliche Zuordnung** genutzt: [Art. 1 Abs. 2 AGVwGO](https://www.gesetze-bayern.de/Content/Document/BayAGVwGO-1) ordnet die sieben Regierungsbezirke den sechs Gerichten zu. Die geprüfte CSV verknüpft die amtlichen Namen/IDs mit genau diesen VG25-Regionen; die beiden Regensburger Regionen werden vereinigt. Fehlende oder umbenannte Regionen brechen die Ableitung ab. Aus Entfernung wird kein Gerichtsbezirk abgeleitet. Standortpunkte stehen getrennt für ausdrücklich markierte Anlaufhinweise bereit. Gesetzestexte sind nach [§5 Abs. 1 UrhG](https://www.gesetze-im-internet.de/urhg/__5.html) vom urheberrechtlichen Schutz ausgenommen; für die verwendeten Geometrie- und Namensdaten bleiben die CC-BY-Namensnennungen erforderlich. Die redaktionelle Zuordnung ist mit dem Prüftermin gekennzeichnet und wird nicht automatisch bei Gesetzesänderungen erneuert.

## Kommunale Kategorien und Portalverbund

Für Bürgeramt, Ordnungsamt, Jugendamt, Wohngeldstelle, Zulassungsstelle und ähnliche Kategorien ist ein kommunaler Gebietsschlüssel nur die räumliche Grundlage. Es fehlt ohne weitere Quelle die Zuordnung zur konkreten Organisation einschließlich Leistungs-/Rollenbezug und Sonderfällen. Standesamtsverbände, gemeinsame Ämter und aufgabenabhängige Zuständigkeiten verhindern eine pauschale Kreis- oder Gemeindeableitung.

Der [Portalverbund](https://docs.fitko.de/pvog/docs/) ist eine sinnvolle Erweiterungsquelle, aber kein hier importierter freier Polygon-WFS. Die [FITKO-Dokumentation zur Auswahl zuständiger Organisationseinheiten](https://docs.fitko.de/efa-parametrisierung/docs/parametrisierung_anh%C3%A4nge/ermittlung_zust%C3%A4ndige_organisationseinheit_im_pvog/) unterscheidet Zuständige Stelle und Ansprechpunkt sowie Kriterien. Die [ARS-Schnittstelle zu einer Organisationseinheit](https://pvog.fitko.de/blog/neue-api-organisationunits/) benötigt zusätzlich den Leistungsschlüssel. Eine solche leistungsgebundene Beziehung darf nicht in eine uneingeschränkte Kategorie-Region-Zuordnung umgedeutet werden. Vor einem Bulkimport wären Zugang, Datenlizenz, Aktualisierung, Rollen und Vollständigkeit gesondert zu klären. Diese Arbeit behauptet keinen ausgeführten bundesweiten PVOG-Gesamtabzug.

Staatliche Bauämter sind keine automatisch zuständigen kommunalen Bauaufsichtsbehörden. Wasserwirtschaftsämter sind kein allgemeines kommunales Umweltamt. Sozialgerichte oder das Zentrum Bayern Familie und Soziales werden nicht als örtliches Sozialamt importiert. Auch in frei erreichbaren Diensten werden daher nicht alle ähnlich klingenden Layer genutzt.

## Kategorien mit zusätzlichem Personen- oder Aufgabenbezug

- **Krankenkasse:** Mitgliedschaft und Wahlrecht gemäß [§173 SGB V](https://www.gesetze-im-internet.de/sgb_5/__173.html) erlauben keine eindeutige Bestimmung durch den Wohnort.
- **Pflegekasse:** organisatorische Verbindung zur Krankenkasse gemäß [§46 SGB XI](https://www.gesetze-im-internet.de/sgb_11/__46.html); keine exklusiven Wohnortbezirke konstruieren.
- **Rentenversicherung:** die [Datenstelle der Rentenversicherung](https://www.dsrv.info/de/Navigation/20_Unsere_Verfahren/01_Nationaler_Datenaustausch/01_Rentenversicherungstraeger/Rentenversicherungstraeger_index_node.html) beschreibt trägerübergreifende Konten-/Versicherungsnummernprozesse. Ein Regionalträgername ist kein Beleg, dass jeder Bewohner dort versichert ist.
- **BAföG-Amt:** [§45 BAföG](https://www.gesetze-im-internet.de/baf_g/__45.html) unterscheidet Ausbildungsfälle, Ausbildungsstätte, Elternwohnsitz und Auslandsförderung. Ein allgemeines Wohnortpolygon würde Fälle falsch zuordnen.
- **BAMF:** [BAMF-NAvI](https://bamf-navi.bamf.de/de/Benutzeranleitung/) enthält Ansprechpartner und Standorte für verschiedene Aufgaben. Diese Standorte ergeben kein allgemeingültiges Wohnortpolygon für alle BAMF-Verfahren.
- **Bundesverwaltungsamt:** als aufgabenbezogene Bundesbehörde wird es nicht mit einem exklusiven örtlichen Bezirk modelliert. Eine vollständige Kategorie- und Punktausgabe muss hier zunächst das konkrete Anliegen erfragen.
- **Familienkasse, Sozialamt, Zoll, Standesamt, Bauamt, Straßenverkehrsbehörde und Umweltamt:** Leistungsart und weitere örtliche/sachliche Anknüpfung sind relevant. Der vorliegende Code gibt deshalb `context_required` aus, wenn kein belastbarer allgemeiner Gebietsbestand eingerichtet ist.

Die vollständige Liste aller 36 Kategorien einschließlich ihres Lieferstatus steht in [ABDECKUNG.md](ABDECKUNG.md). Leere Flächentabellen sind absichtlich sichtbar. Nach erfolgloser Flächensuche können echte Standortpunkte innerhalb eines konfigurierten Radius als ausdrücklich markierte Anlaufhinweise erscheinen; ihre Zuständigkeit wird nicht behauptet. Demoobjekte und erfundene Kreiszuständigkeiten werden nicht verwendet.


## Ergänzungen dieses Lieferstands

GEMFA wird als amtlicher BZSt-Gesamtexport eingelesen, mit den exakten VG25-Gemeindeschlüsseln verbunden und bei Mehrfachzuordnung bzw. widersprechenden Adressregeln konservativ ausgeschlossen. Die Flächen sind nachgewiesene Teilmengen von Finanzamtsbezirken. Die expliziten kommunalen Anredefelder ermöglichen außerdem eine begrenzte, bundesweit verteilte kommunale Zuordnung. Das [GovData-Metadatum](https://www.govdata.de/suche/daten/suche-nach-zustandigem-finanzamt) weist den GEMFA-Inhalt als amtliches Werk aus; die BKG-Geometrien behalten CC BY 4.0.

Hamburgs Finanzamtsbezirke und Brandenburgs Polizeiinspektionen wurden mit Capabilities, Schema und vollständigen GML-Daten geprüft und eingebunden. Thüringen stellt Schulamtsflächen sowie Gesundheits-, Veterinär- und Jugendamtsstandorte als INSPIRE-Dateien bereit. Hessen veröffentlicht die 15 Schulamtsbezirke ausdrücklich; diese werden über amtliche Gebietsschlüssel mit VG25 verbunden. Die zehn sächsischen Landratsämter stammen aus dem amtlichen Verwaltungsatlas-WMS, dessen tatsächliche GetFeatureInfo-Antwort Behördennamen und Landkreise nennt. Regierungsbehörden in BW, HE und NW werden nur über ausdrücklich veröffentlichte Namen und Gebiete verknüpft. CSV-Dateien, Nachweislinks und Prüfsummen sind Teil des Projekts.

Die Berliner Ressource „Ansprechpartner Bau- und Wohnungsaufsicht in Friedrichshain-Kreuzberg“ wurde über das amtliche Datenregister geprüft; die verlinkte GeoJSON-Datei lieferte HTTP 404. Der Eintrag zählt nicht als integrierte Flächen- oder Standortabdeckung. POI-Bund lieferte HTTP 403; das freie POI-Open bot zum Prüfzeitpunkt keine entsprechenden Behördenkategorien. Diese Produkte werden nicht als offen importiert ausgegeben.

Für die Standortergänzung werden amtliche Punktlayer und ausdrücklich benannte OpenStreetMap-Einträge verwendet. OSM ist keine amtliche Zuständigkeitsquelle. Namensmuster werden nur zusammen mit passenden office-/amenity-Tags ausgewertet, Stilllegungen werden ausgeschlossen. Für Ways und Relations ist die gespeicherte Koordinate der Quell-Bounding-Box-Mittelpunkt und nicht zwangsläufig der öffentliche Eingang. Der Abzug wird lokal zwischengespeichert und nicht für jede Resolverabfrage erneut angefordert. Die ODbL-Herkunft bleibt je Datensatz erhalten. Unvollständige Overpass-Antworten mit Fehlermeldung werden verworfen; fehlgeschlagene Großabfragen begründen keine Abdeckung.
