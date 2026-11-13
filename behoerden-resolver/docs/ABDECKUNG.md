# Deutschlandweite Abdeckung und Quellen je Behördenkategorie

Stand der lokalen Messung: 2026-11-13T18:05:56.709169+00:00. **6,376 Flächeneinträge in 14 Kategorien; 767 Standorte in 22 Kategorien; 11,396 reine Verwaltungsgebietsreferenzen.** Alle 36 Kategorien werden unterstützt, aber nicht alle besitzen bundesweit nachgewiesene Zuständigkeitsflächen.

Die Mengen zählen Quellfeatures und Dienststellen einschließlich mehrfacher räumlicher Teile. Mehrere Quellen können dieselbe Institution enthalten. Ein Standort ist kein Nachweis für deren örtliche oder persönliche Zuständigkeit.

## Wie die Abdeckung gemessen wird

Der Flächenindikator zählt die Gemeindeschlüssel, deren VG25-Repräsentativpunkt von mindestens einem importierten Fachpolygon erfasst wird. Basis: **10974 unterschiedliche AGS** aus dem tatsächlich geladenen VG25-Gemeindelayer. Pro AGS werden vorhandene Teile vereinigt und `ST_PointOnSurface` gebildet; geprüft wird `ST_Covers`. Diese reproduzierbare Stichprobe misst weder Flächenanteil noch Bevölkerung, Straßen oder sämtliche Adressen einer Gemeinde. Ein Treffer kann eine nur teilweise abgedeckte Gemeinde betreffen. Selbst ein Wert von 100 % beweist keine lückenlose Fachzuständigkeit und keine Aktualität aller Gebiete. Dienstgrenzen haben unterschiedliche Generalisierung und Quelldatenstände.

Die Länderliste bei Flächen nennt Länder mit mindestens einem solchen Referenzpunkttreffer; bei Standorten nennt sie Länder, in denen die importierten Punkte tatsächlich liegen. Keine dieser Listen behauptet eine vollständige Landesabdeckung. Bundesweit angebotene BZB-Open-Datensätze gibt es für Amtsgericht, Landgericht, Jobcenter und Arbeitsagentur.

## Alle 36 Kategorien

| Kategorie | Flächeneinträge | Gemeindeindikator | Länder mit Flächentreffern | Standorte und Länder | Quellen |
| --- | ---: | ---: | --- | --- | --- |
| `amtsgericht` | 650 | 10963/10974 (99.9 %) | BB, BE, BW, BY, HB, HE, HH, MV, NI, NW, RP, SH, SL, SN, ST, TH | 0; – | bzb_amtsgericht |
| `arbeitsagentur` | 146 | 10954/10974 (99.8 %) | BB, BE, BW, BY, HB, HE, HH, MV, NI, NW, RP, SH, SL, SN, ST, TH | 0; – | bzb_arbeitsagentur |
| `auslaenderbehoerde` | 0 | 0/10974 (0.0 %) | – | 0; – | Keine importierte Quelle |
| `bafoegamt` | 0 | Nicht allein räumlich bestimmbar | – | 0; – | Keine importierte Quelle |
| `bauamt` | 0 | Nicht allein räumlich bestimmbar | – | 0; – | Keine importierte Quelle |
| `buergeramt` | 0 | 0/10974 (0.0 %) | – | 0; – | Keine importierte Quelle |
| `bundesamt_migration` | 0 | Nicht allein räumlich bestimmbar | – | 0; – | Keine importierte Quelle |
| `bundesverwaltungsamt` | 0 | Nicht allein räumlich bestimmbar | – | 0; – | Keine importierte Quelle |
| `familienkasse` | 0 | Nicht allein räumlich bestimmbar | – | 0; – | Keine importierte Quelle |
| `finanzamt` | 530 | 10882/10974 (99.2 %) | BB, BW, BY, HB, HE, HH, MV, NI, NW, RP, SH, SL, SN, ST, TH | 104; BY, HE, RP | by_finanzamt; by_finanzamt_locations [Punkt]; gemfa_vg25; hh_finanzamt; osm_locations [Punkt] |
| `gesundheitsamt` | 0 | 0/10974 (0.0 %) | – | 25; HE, RP, TH | osm_locations [Punkt]; th_health_locations [Punkt] |
| `gewerbeamt` | 0 | 0/10974 (0.0 %) | – | 0; – | Keine importierte Quelle |
| `handwerkskammer` | 7 | 2221/10974 (20.2 %) | BY | 7; BY | by_handwerkskammer; by_handwerkskammer_locations [Punkt] |
| `ihk` | 10 | 2221/10974 (20.2 %) | BY | 10; BY | by_ihk; by_ihk_locations [Punkt] |
| `jobcenter` | 404 | 10955/10974 (99.8 %) | BB, BE, BW, BY, HB, HE, HH, MV, NI, NW, RP, SH, SL, SN, ST, TH | 2; HE | bzb_jobcenter; osm_locations [Punkt] |
| `jugendamt` | 0 | 0/10974 (0.0 %) | – | 24; HE, TH | osm_locations [Punkt]; th_health_locations [Punkt] |
| `krankenkasse` | 0 | Nicht allein räumlich bestimmbar | – | 0; – | Keine importierte Quelle |
| `kreisverwaltung` | 81 | 2611/10974 (23.8 %) | BY, SN | 71; BY | by_kreis; by_kreis_locations [Punkt]; sn_kreis |
| `landgericht` | 115 | 10963/10974 (99.9 %) | BB, BE, BW, BY, HB, HE, HH, MV, NI, NW, RP, SH, SL, SN, ST, TH | 0; – | bzb_landgericht |
| `ordnungsamt` | 0 | 0/10974 (0.0 %) | – | 1; HE | osm_locations [Punkt] |
| `pflegekasse` | 0 | Nicht allein räumlich bestimmbar | – | 0; – | Keine importierte Quelle |
| `polizei` | 279 | 2615/10974 (23.8 %) | BB, BY | 322; BB, BY, HE | bb_polizei; bb_polizei_locations [Punkt]; by_polizei; by_polizei_locations [Punkt]; osm_locations [Punkt] |
| `regierungsprs` | 19 | 4145/10974 (37.8 %) | BW, BY, HE, NW | 7; BY | by_regierung; by_regierung_locations [Punkt]; regierung_vg25 |
| `rentenversicherung` | 0 | Nicht allein räumlich bestimmbar | – | 1; RP | osm_locations [Punkt] |
| `schulamt` | 116 | 3251/10974 (29.6 %) | BY, HE, TH | 96; BY | by_schulamt; by_schulamt_locations [Punkt]; he_schulamt; th_schulamt |
| `sozialamt` | 0 | Nicht allein räumlich bestimmbar | – | 2; RP | osm_locations [Punkt] |
| `staatsanwaltschaft` | 22 | 2062/10974 (18.8 %) | BY | 22; BY | by_staatsanwaltschaft; by_staatsanwaltschaft_locations [Punkt] |
| `stadtverwaltung` | 3991 | 3969/10974 (36.2 %) | BB, BW, BY, HE, MV, NI, NW, RP, SH, SL, SN, ST, TH | 31; BY, HE, RP | by_kreis; by_kreis_locations [Punkt]; gemfa_vg25; osm_locations [Punkt] |
| `standesamt` | 0 | Nicht allein räumlich bestimmbar | – | 3; HE, RP | osm_locations [Punkt] |
| `strassenverkehrsbehoerde` | 0 | Nicht allein räumlich bestimmbar | – | 1; RP | osm_locations [Punkt] |
| `umweltamt` | 0 | Nicht allein räumlich bestimmbar | – | 4; HE, RP | osm_locations [Punkt] |
| `verwaltungsgericht` | 6 | 2221/10974 (20.2 %) | BY | 6; BY | by_verwaltungsgericht_gesetz; by_verwaltungsgericht_locations [Punkt] |
| `veterinaeramt` | 0 | 0/10974 (0.0 %) | – | 23; HE, TH | osm_locations [Punkt]; th_health_locations [Punkt] |
| `wohngeldstelle` | 0 | 0/10974 (0.0 %) | – | 0; – | Keine importierte Quelle |
| `zoll` | 0 | Nicht allein räumlich bestimmbar | – | 3; HE, RP | osm_locations [Punkt] |
| `zulassungsstelle` | 0 | 0/10974 (0.0 %) | – | 2; HE, RP | osm_locations [Punkt] |

Länderkürzel: BW Baden-Württemberg, BY Bayern, BE Berlin, BB Brandenburg, HB Bremen, HH Hamburg, HE Hessen, MV Mecklenburg-Vorpommern, NI Niedersachsen, NW Nordrhein-Westfalen, RP Rheinland-Pfalz, SL Saarland, SN Sachsen, ST Sachsen-Anhalt, SH Schleswig-Holstein, TH Thüringen.

## Fachliche Grenzen je Kategorie

- **Amtsgericht (`amtsgericht`)**: BZB Open: allgemeine Amtsgerichtsbezirke, keine zentralisierten Register-, Insolvenz- oder anderen Spezialzuständigkeiten. Standort-Radius als Anwendungsvorgabe: 60 km.
- **Agentur für Arbeit (`arbeitsagentur`)**: BZB Open: Agenturbezirke, keine konkrete Geschäftsstelle/Terminzuordnung. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Ausländerbehörde (`auslaenderbehoerde`)**: Gemeinde- oder Kreisgrenze ist ohne explizite Zuordnung kein belegter Ausländerbehördenbezirk. Standort-Radius als Anwendungsvorgabe: 50 km.
- **Amt für Ausbildungsförderung (`bafoegamt`)**: §45 BAföG: abhängig u.a. von Ausbildungsart/-stätte, Elternwohnsitz und Auslandsstaat; Wohnort allein reicht nicht. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Bauamt / Bauaufsichtsbehörde (`bauamt`)**: Bauaufsicht und staatliche Bauämter sind unterschiedliche Aufgaben. Staatsbauämter werden nicht als örtliche Bauaufsicht importiert. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Bürgeramt / Bürgerbüro (`buergeramt`)**: Bürgerbüros können freie Standortwahl und besondere Zuständigkeitsregeln haben; Gemeindegrenze allein genügt nicht. Standort-Radius als Anwendungsvorgabe: 20 km.
- **Bundesamt für Migration und Flüchtlinge (`bundesamt_migration`)**: Bundesbehörde; Außenstellenzuständigkeit hängt von Aufgabe und Verfahren ab. BAMF-NAvI enthält nicht nur Behördenstandorte. Standort-Radius als Anwendungsvorgabe: 100 km.
- **Bundesverwaltungsamt (`bundesverwaltungsamt`)**: Bundesweite aufgabenbezogene Bundesoberbehörde; kein exklusiver Wohnortbezirk. Konkrete Leistung für zuständige Organisationseinheit erforderlich. Standort-Radius als Anwendungsvorgabe: 150 km.
- **Familienkasse (`familienkasse`)**: Wohnsitz, Auslandsbezug und Sonderzuständigkeiten können entscheidend sein. Keine Ableitung aus Arbeitsagenturbezirken. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Finanzamt (`finanzamt`)**: Allgemeine Bezirke aus Bayern und Hamburg sowie bundesweit eindeutige GEMFA-Gemeindezuordnungen mit VG25. GEMFA-Geometrien sind ausdrücklich belegte Teilflächen; geteilte Gemeinden und widersprechende Adressregeln bleiben offen. Sondersteuerzuständigkeiten nicht aus dem Polygon ableiten. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Gesundheitsamt (`gesundheitsamt`)**: Landratsamt-Geometrien werden nicht ohne amtliche Fachzuordnung zu Gesundheitsämtern umgedeutet. Standort-Radius als Anwendungsvorgabe: 40 km.
- **Gewerbeamt (`gewerbeamt`)**: Keine importierte explizite Gewerbebehördenzuordnung; kommunale Verwaltungsverbände beachten. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Handwerkskammer (`handwerkskammer`)**: Amtliche Kammerbezirke in Bayern; Dienststellen bleiben als Quelleinträge getrennt, gegebenenfalls mehrere Treffer. Standort-Radius als Anwendungsvorgabe: 100 km.
- **Industrie- und Handelskammer (`ihk`)**: Amtliche Kammerbezirke in Bayern; Zugehörigkeit hängt zusätzlich von Betrieb und Tätigkeit ab. Standort-Radius als Anwendungsvorgabe: 100 km.
- **Jobcenter (`jobcenter`)**: BZB Open: Jobcenter-Bezirke; keine persönliche Anspruchsprüfung oder Ermittlung besonderer Fallzuständigkeiten. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Jugendamt (`jugendamt`)**: Örtliche Jugendhilfeträger und Ausnahmen müssen explizit zugeordnet werden; keine Kreispauschale. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Gesetzliche Krankenkasse (`krankenkasse`)**: Mitgliedschaft und Wahlrecht bestimmen den Träger; ein Wohnortpolygon bestimmt keine Krankenkasse. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Kreisverwaltung / Landratsamt (`kreisverwaltung`)**: Explizite Landratsämter in Bayern und Sachsen. Kreisfreie Städte werden als Stadtverwaltung geführt; VG25-Kreisgrenzen allein sind kein Behördennachweis. Standort-Radius als Anwendungsvorgabe: 50 km.
- **Landgericht (`landgericht`)**: BZB Open: allgemeine Landgerichtsbezirke; örtliche Anknüpfung hängt vom Verfahren ab. Standort-Radius als Anwendungsvorgabe: 100 km.
- **Ordnungsamt (`ordnungsamt`)**: Keine importierte, explizite Behörden-Gebiets-Zuordnung. Ordnungsbehörden nicht pauschal aus Gemeinden ableiten. Standort-Radius als Anwendungsvorgabe: 20 km.
- **Pflegekasse (`pflegekasse`)**: Zuständige Pflegekasse folgt der Krankenversicherung; keine fiktiven Gebietsmonopole. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Polizei (`polizei`)**: Polizeiinspektionen/-stationen in Bayern und Polizeiinspektionen Brandenburgs. Keine Übertragung auf Bundes-, Kriminal-, Verkehrs- oder andere Polizeifunktionen. Standort-Radius als Anwendungsvorgabe: 20 km.
- **Regierungspräsidium / Bezirksregierung (`regierungsprs`)**: Bayerische Regierungen sowie explizit zugeordnete Regierungspräsidien in Baden-Württemberg/Hessen und Bezirksregierungen in Nordrhein-Westfalen. Keine bundesweite Zuständigkeit aller Mittelbehörden; Spezialaufgaben können abweichen. Standort-Radius als Anwendungsvorgabe: 100 km.
- **Deutsche Rentenversicherung (`rentenversicherung`)**: Zuständiger Versicherungsträger ist aus Versicherungsverhältnis/-konto zu bestimmen, nicht allein aus Wohnortpolygon. Standort-Radius als Anwendungsvorgabe: 80 km.
- **Schulamt / Schulbehörde (`schulamt`)**: Schulamtsbezirke aus Bayern, Hessen und Thüringen. Schulart/Aufgabe prüfen; Thüringer Quelldatenstand 2024 ausdrücklich erhalten. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Sozialamt (`sozialamt`)**: Leistung, örtlicher und überörtlicher Sozialhilfeträger unterscheiden; keine allgemeine Kreiszuständigkeit erfinden. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Staatsanwaltschaft (`staatsanwaltschaft`)**: Explizite Staatsanwaltschaften in Bayern aus gemischtem Justizlayer. Keine Ableitung aus Landgerichtsbezirken außerhalb dieser Quelle. Standort-Radius als Anwendungsvorgabe: 100 km.
- **Stadtverwaltung / Gemeindeverwaltung (`stadtverwaltung`)**: Explizite Stadt-/Gemeindeverwaltungen aus GEMFA (nur Anrede Stadtverwaltung oder Gemeindeverwaltung) und bayerische kreisfreie Städte. Keine erfundenen Verbandsverwaltungsnamen aus Mitgliedsgemeinden. Standort-Radius als Anwendungsvorgabe: 20 km.
- **Standesamt (`standesamt`)**: Ereignis, Registerführung, Eheschließung und Wohnsitz können verschiedene Zuständigkeiten ergeben; Standesamtsverbände nicht mit Gemeinden gleichsetzen. Standort-Radius als Anwendungsvorgabe: 25 km.
- **Straßenverkehrsbehörde (`strassenverkehrsbehoerde`)**: Straßenverkehrsrecht, Fahrerlaubnis und Straßenbaulast unterscheiden; Kategorie allein bestimmt keine eindeutige Zuständigkeit. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Umweltamt / Untere Umweltbehörde (`umweltamt`)**: Untere Wasser-, Naturschutz-, Immissionsschutz- und andere Behörden haben unterschiedliche Zuständigkeiten. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Verwaltungsgericht (`verwaltungsgericht`)**: Bayern: örtliche Bezirke der sechs Verwaltungsgerichte aus Art. 1 Abs. 2 AGVwGO und VG25-Regierungsbezirken abgeleitet. Sachliche oder spezielle Verfahrenszuständigkeiten sind nicht eingeschlossen. Der Standortpunkt allein wird nicht als Gebiet verwendet. Standort-Radius als Anwendungsvorgabe: 150 km.
- **Veterinäramt (`veterinaeramt`)**: Keine importierte explizite Veterinärbehörden-Gebietszuordnung. Standort-Radius als Anwendungsvorgabe: 40 km.
- **Wohngeldstelle (`wohngeldstelle`)**: Explizite Wohngeldbehörden-Zuordnung fehlt; keine pauschale Gemeinde-/Kreiszuordnung. Standort-Radius als Anwendungsvorgabe: 30 km.
- **Hauptzollamt / Zoll (`zoll`)**: BKG BZB ohne Open ist zugangsbeschränkt. Zuständigkeit hängt u.a. von Zollverfahren und Steuerart ab; kein freier bundesweiter Import eingerichtet. Standort-Radius als Anwendungsvorgabe: 50 km.
- **Kfz-Zulassungsstelle (`zulassungsstelle`)**: Keine importierte explizite Zulassungsbezirks-/Behördenzuordnung. Kreisgeometrie reicht als Beleg nicht. Standort-Radius als Anwendungsvorgabe: 30 km.

## Flächen haben Vorrang vor Standorten

Die automatische Abfrage prüft relevante live erreichbare Fach-WFS und, wenn dort keine Fläche passt, lokale fachlich belegte Ergänzungen. Erst wenn die abgeschlossene Flächensuche keinen Treffer liefert, wird der lokale Standortindex mit geodätischer Entfernung abgefragt. Ein WFS-Fehler gilt nicht als leere Flächenabdeckung: Die Abfrage meldet den Fehler und gibt keinen verdeckten Standortersatz aus. Lokaler Betrieb ist ausdrücklich mit `--backend local` wählbar.

Standorte bleiben echte Punkte. Es werden keine Zuständigkeitskreise um Büros erzeugt. Antworten enthalten `fallback_used=true`, `match_type=nearest_point_fallback`, `distance_m`, den verwendeten Radius, `jurisdiction_verified=false` und einen Warntext. Standardmäßig werden höchstens drei mögliche Anlaufstellen zurückgegeben. `--no-point-fallback` schaltet dies ab; `--radius-km` passt den Radius zwischen größer 0 und höchstens 300 km an. Die Kategorienradien sind nachvollziehbare Anwendungsvorgaben, keine amtlichen Entfernungsregeln.

Bei Krankenkasse, Pflegekasse, Rentenversicherung und Bundesverwaltungsamt bleibt der Status `non_spatial`; bei weiteren aufgabenabhängigen Kategorien `context_required`. Ein gegebenenfalls ausgegebener Standort ist nur eine Kontaktmöglichkeit. Er ersetzt weder Mitgliedschaft noch Leistung, Verfahren, Schulart oder sonstigen fehlenden Kontext.

## GEMFA und kommunale Zuordnungen

Der offizielle BZSt-GEMFA-Export ist vollständig eingelesen und mit den VG25-Gemeinden verknüpft. Finanzamtsflächen entstehen nur für eindeutig zugeordnete ganze Gemeinden ohne widersprechende Adressausnahme. Geteilte Städte und nicht auflösbare Schlüssel werden ausgelassen und im Snapshot auditiert. Die vereinigten Flächen sind **belegte Teilmengen eines Finanzamtsbezirks**, nicht zwangsläufig der vollständige Bezirk (`geometry_completeness=verified_municipality_subset_of_jurisdiction`). Für die räumliche Anfrage bleibt dort eine Abdeckungslücke. Bayern und Hamburg liefern zusätzlich echte Fachpolygone. Steuerart und Sonderzuständigkeit werden nicht allein aus dem Ort entschieden.

Für Stadtverwaltungen werden ausschließlich explizite GEMFA-Felder mit Anrede Stadtverwaltung oder Gemeindeverwaltung genutzt. Verbandsgemeinde-, Amts- oder Verwaltungsgemeinschaftsnamen werden nicht aus der einzelnen Mitgliedsgemeinde erfunden. Weitere Ergänzungen stammen aus ausdrücklich belegten regionalen Zuordnungen in Sachsen, Hessen, Baden-Württemberg und Nordrhein-Westfalen sowie aus Thüringer Schulamtsflächen.

## Quellen und Lizenzen

Jede nachfolgende Zeile nennt die tatsächlich konfigurierte Quelle. Endpunkt, Layer, Filter, Namensregel, Aktualitätshinweise und Lizenz stehen zusätzlich im maschinenlesbaren [Quellenmanifest](../src/behoerden_resolver/resources/sources.json). Snapshots enthalten ihre historische Quellkonfiguration und Rohantwortprüfsummen. [delivery-manifest.json](../data/delivery-manifest.json) listet die tatsächlich ausgelieferten vollständigen Snapshots.

- **`bzb_amtsgericht`** — DE; authority; dl-de/by-2-0. [Quelle](https://gdz.bkg.bund.de/index.php/default/wfs-behoerdenzustaendigkeitsbereiche-open-wfs-bzb-open.html); WFS `https://sgx.geodatenzentrum.de/wfs_bzb_open`, Layer `bzb-open:gerichte_amtsgerichte`.
- **`bzb_landgericht`** — DE; authority; dl-de/by-2-0. [Quelle](https://gdz.bkg.bund.de/index.php/default/wfs-behoerdenzustaendigkeitsbereiche-open-wfs-bzb-open.html); WFS `https://sgx.geodatenzentrum.de/wfs_bzb_open`, Layer `bzb-open:gerichte_landgerichte`.
- **`bzb_jobcenter`** — DE; authority; dl-de/by-2-0. [Quelle](https://gdz.bkg.bund.de/index.php/default/wfs-behoerdenzustaendigkeitsbereiche-open-wfs-bzb-open.html); WFS `https://sgx.geodatenzentrum.de/wfs_bzb_open`, Layer `bzb-open:ba_jobcenter`.
- **`bzb_arbeitsagentur`** — DE; authority; dl-de/by-2-0. [Quelle](https://gdz.bkg.bund.de/index.php/default/wfs-behoerdenzustaendigkeitsbereiche-open-wfs-bzb-open.html); WFS `https://sgx.geodatenzentrum.de/wfs_bzb_open`, Layer `bzb-open:ba_arbeitsagenturen`.
- **`vg25_krs`** — DE; boundary_reference; CC-BY-4.0. [Quelle](https://gdz.bkg.bund.de/index.php/default/wfs-verwaltungsgebiete-1-25-000-stand-31-12-wfs-vg25.html); WFS `https://sgx.geodatenzentrum.de/wfs_vg25`, Layer `vg25:vg25_krs`.
- **`vg25_rbz`** — DE; boundary_reference; CC-BY-4.0. [Quelle](https://gdz.bkg.bund.de/index.php/default/wfs-verwaltungsgebiete-1-25-000-stand-31-12-wfs-vg25.html); WFS `https://sgx.geodatenzentrum.de/wfs_vg25`, Layer `vg25:vg25_rbz`.
- **`vg25_gem`** — DE; boundary_reference; CC-BY-4.0. [Quelle](https://gdz.bkg.bund.de/index.php/default/wfs-verwaltungsgebiete-1-25-000-stand-31-12-wfs-vg25.html); WFS `https://sgx.geodatenzentrum.de/wfs_vg25`, Layer `vg25:vg25_gem`.
- **`by_kreis`** — DE-BY; authority; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmi-wfs`, Layer `stmi:KreisverwaltungsbehoerdenFlaeche`.
- **`by_regierung`** — DE-BY; authority; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmi-wfs`, Layer `stmi:RegierungenFlaeche`.
- **`by_polizei`** — DE-BY; authority; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmi-wfs`, Layer `stmi:PolizeiinspektionenFlaeche`.
- **`by_finanzamt`** — DE-BY; authority; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmfh-wfs`, Layer `stmfh:SteuerverwaltungFlaeche`.
- **`by_staatsanwaltschaft`** — DE-BY; authority; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmj-wfs`, Layer `stmj:LandgerichteStaatsanwaltschaftenFlaeche`.
- **`by_schulamt`** — DE-BY; authority; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmuk-wfs`, Layer `stmuk:SchulaemterFlaeche`.
- **`by_ihk`** — DE-BY; authority; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_sonstige_institutionen-wfs`, Layer `Sonstige:IndustrieHandelskammernFlaeche`.
- **`by_handwerkskammer`** — DE-BY; authority; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_sonstige_institutionen-wfs`, Layer `Sonstige:HandwerkskammernFlaeche`.
- **`by_verwaltungsgericht_gesetz`** — DE-BY; authority; CC-BY-4.0; statutory assignment from official legislation (§5 UrhG). [Quelle](https://www.gesetze-bayern.de/Content/Document/BayAGVwGO-1); Datenzugang `https://www.gesetze-bayern.de/Content/Document/BayAGVwGO-1`.
- **`hh_finanzamt`** — DE-HH; authority; dl-de/zero-2-0. [Quelle](https://www.geoportal.de/info/1998EDF3-C86D-4FBD-9CC5-B230E40EF47B); WFS `https://geodienste.hamburg.de/HH_WFS_Finanzamtbezirke`, Layer `de.hh.up:finanzamtbezirke`.
- **`bb_polizei`** — DE-BB; authority; dl-de/by-2-0. [Quelle](https://www.govdata.de/suche/daten/zustandigkeitsbereiche-der-polizei-brandenburgedb67); WFS `https://inspire.brandenburg.de/services/polbb_wfs`, Layer `app:inspektionen`.
- **`gemfa_vg25`** — DE; authority; GEMFA officialWork (§5 Abs.1 UrhG) + VG25 CC-BY-4.0. [Quelle](https://www.bzst.de/DE/Service/Behoerdenwegweiser/Finanzamtsuche/finanzamtsuche_node.html); Datenzugang `https://www.bzst.de/SharedDocs/Downloads/DE/GemFA/gemfa_xml_export_datei.zip?__blob=publicationFile`.
- **`th_schulamt`** — DE-TH; authority; CC-BY-4.0. [Quelle](https://geomis.geoportal-th.de/geonetwork/srv/api/records/3a88540e-36ea-46f7-b70f-47c1db95cda9); Datenzugang `https://www.geoproxy.geoportal-th.de/download-service/extern/giz/INSPIREus_Schulamtsbezirke_EPSG25832.gml`.
- **`he_schulamt`** — DE-HE; authority; CC-BY-4.0. [Quelle](https://schulaemter.hessen.de/ueber-uns/schulamtsbezirke); Datenzugang `https://schulaemter.hessen.de/ueber-uns/schulamtsbezirke`.
- **`regierung_vg25`** — DE-BW|DE-HE|DE-NW; authority; CC-BY-4.0. [Quelle](https://www.baden-wuerttemberg.de/de/unser-land/von-der-gemeinde-bis-zum-ministerium); Datenzugang `https://www.baden-wuerttemberg.de/de/unser-land/von-der-gemeinde-bis-zum-ministerium`.
- **`sn_kreis`** — DE-SN; authority; VG25 CC-BY-4.0 + Verwaltungsatlas Sachsen dl-de/by-2-0. [Quelle](https://geodienste.sachsen.de/wms_smr_kommunales/guest?SERVICE=WMS&REQUEST=GetCapabilities); Datenzugang `https://geodienste.sachsen.de/wms_smr_kommunales/guest?SERVICE=WMS&REQUEST=GetCapabilities`.
- **`by_finanzamt_locations`** — DE-BY; authority_point; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmfh-wfs`, Layer `stmfh:SteuerverwaltungStandort`.
- **`by_kreis_locations`** — DE-BY; authority_point; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmi-wfs`, Layer `stmi:KreisverwaltungsbehoerdenStandort`.
- **`by_regierung_locations`** — DE-BY; authority_point; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmi-wfs`, Layer `stmi:RegierungenStandort`.
- **`by_verwaltungsgericht_locations`** — DE-BY; authority_point; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmi-wfs`, Layer `stmi:VerwaltungsgerichtsbarkeitStandort`.
- **`by_polizei_locations`** — DE-BY; authority_point; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmi-wfs`, Layer `stmi:PolizeiinspektionenStandort`.
- **`by_staatsanwaltschaft_locations`** — DE-BY; authority_point; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmj-wfs`, Layer `stmj:LandgerichteStaatsanwaltschaftenStandort`.
- **`by_schulamt_locations`** — DE-BY; authority_point; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_stmuk-wfs`, Layer `stmuk:SchulaemterStandort`.
- **`by_ihk_locations`** — DE-BY; authority_point; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_sonstige_institutionen-wfs`, Layer `Sonstige:IndustrieHandelskammernStandort`.
- **`by_handwerkskammer_locations`** — DE-BY; authority_point; CC-BY-4.0. [Quelle](https://geoportal.bayern.de/geoportalbayern/seiten/dienste); WFS `https://gdiserv.bayern.de/srv1970/services/verwaltungsatlas_sonstige_institutionen-wfs`, Layer `Sonstige:HandwerkskammernStandort`.
- **`bb_polizei_locations`** — DE-BB; authority_point; dl-de/by-2-0. [Quelle](https://www.govdata.de/suche/daten/zustandigkeitsbereiche-der-polizei-brandenburgedb67); WFS `https://inspire.brandenburg.de/services/polbb_wfs`, Layer `app:standorte`.
- **`th_health_locations`** — DE-TH; authority_point; CC-BY-4.0. [Quelle](https://geomis.geoportal-th.de/geonetwork/srv/api/records/dbee18e3-3b3b-4e9c-a38c-ec875ac82d92); Datenzugang `https://www.geoproxy.geoportal-th.de/download-service/extern/giz/INSPIRE_US_TMASGFF_EPSG_25832.gml`.
- **`osm_locations`** — DE-RP|DE-HE; authority_point; ODbL-1.0. [Quelle](https://www.openstreetmap.org/copyright); Datenzugang `https://overpass-api.de/api/interpreter`.

**OSM-Abdeckung:** Nur ein vollständig geladener Suchbereich von 10 km um 50.0 N, 8.27 E im Raum Mainz/Wiesbaden ist integriert. Deutschlandweite und 16-Stadt-Abfragen überschritten die Zeitlimits und wurden verworfen. Die Punktabdeckung darf daher nicht als bundesweit vollständig bezeichnet werden. Die Quelle wird nur ausdrücklich aktualisiert, nicht im Standard-Refresh und nicht bei jeder Standortsuche.

Die Datenlizenzen gelten unabhängig von der MIT-Lizenz des Programmcodes. OpenStreetMap-Daten sind gemeinschaftlich gepflegt und unter ODbL 1.0 lizenziert; Namensnennung und die einschlägigen Weitergabepflichten bleiben bei Nutzung der Standortdaten bestehen. Amtliche Punkte und OSM-Punkte werden mit ihrer jeweiligen Quelle und Qualität ausgewiesen.

## Aktualität und offene Quellen

Abrufdatum und fachlicher Datenstand sind verschieden. Der GEMFA-Export stammt vom 2. November 2026. Die Thüringer Gesundheits-, Veterinär- und Jugendamtsstandorte tragen im Atom-Eintrag den Stand 16. September 2022, die Schulamtsdatei den Stand 17. Juni 2024. Diese älteren Daten werden als solche mitgeführt. Gesetzliche und redaktionelle Zuordnungen sind am 13. November 2026 geprüft; ein Geometrieabruf erneuert diese Prüfung nicht.

BZB ohne Open und POI-Bund werden wegen Zugangsbeschränkungen nicht als freie Daten importiert. Der direkte bayerische Verwaltungsgerichtsflächenlayer enthält andere Institutionen und bleibt ausgeschlossen. Eine Berliner Bauaufsichtsressource wurde gefunden, war beim Abruf aber nicht mehr vorhanden. Weitere kommunale Zuordnungen sind offen; eine nicht integrierte Quelle wird nicht als nachgewiesene Abdeckung gezählt. [Recherche](RECHERCHE.md) und [Validierung](VALIDIERUNG.md) erläutern diese Entscheidungen.

## Geometriekontrolle

- `authorities`: 6376 Datensätze; 0 ungültige Geometrien; 2508 als repariert markiert.
- `boundaries`: 11396 Datensätze; 0 ungültige Geometrien; 6122 als repariert markiert.
- `locations`: 767 Datensätze; 0 ungültige Geometrien; 0 als repariert markiert.

Polygonreparaturen nutzen GEOS make_valid, behalten alle Flächenteile und können kollabierte Reste ohne Fläche entfernen. Originalantworten und Reparaturkennzeichen bleiben erhalten. Die vollständigen Quellengeometrien werden bei Abfragen zurückgegeben; der Gemeindeindikator verändert keine Daten.
