> Historical team notes from the original README. Kept for reference; the [current README](../README.md) describes the application as it stands.

# Challenge 4 „Zuständigkeitsfinder“ – Kurzanforderungen

**Quellen:** **C** = Challenge-PDF, Wiki-Stand 22.10.2026. **L** = GDI-DE, *Geodatendienste im Internet*, 4. Auflage, September 2019 (Impressum: L96).

## 1. Challenge: erwarteter Umfang

**Ziele**:

- Einen **Prototyp** entwickeln, der für einen **Standort oder eine Adresse** die zuständige Behörde ermittelt. [C1]
- Vorhandene relevante Geodatenquellen finden, technisch nutzbar machen und verknüpfen, räumliche Zuständigkeiten modellieren. [C1]
- Ergebnisse verständlich und nutzerfreundlich bereitstellen sowie die zugrunde liegenden Geodaten transparent darstellen. [C1]

**Ausdrücklich optional:** KI-gestützte Suche für bürgerfreundliche Fragestellungen. [C2]

**Genannte Umsetzungsbausteine:** Geocodierung, räumliche Analyse und interaktive Karten. Point-in-Polygon ist ein Beispielverfahren. Python, Jupyter, GeoPandas, Shapely, Leaflet, OpenLayers und MapLibre sind hilfreiche Kenntnisse. [C2]

**Nicht festgelegt:** Mindestzahl an Behördentypen/Datenquellen, bundesweite Vollständigkeit, konkrete Programmiersprache, eigener OGC-Server oder INSPIRE-Konformitätsnachweis. Finanzamt, Jobcenter, Gericht, Schule und Polizei sind Beispielfragen, die genannten Datenquellen sind Rechercheansätze.[C1–2]

## 2. Praktische Empfehlungen aus dem Leitfaden

Die folgenden Punkte übertragen den Leitfaden auf unser Projekt, sie sind **keine offiziellen Challenge-Anforderungen**. Projektspezifische Ergänzungen sind als „Ableitung“ markiert.

| Thema | Praktische Umsetzung | Beleg |
|---|---|---|
| **Datenquellen** | Challenge nennt BKG **BZB/BZB-Open**, Geodatenkatalog Deutschland, GovData, Open.NRW, OpenData Bayern, weitere Landesportale und Fachbehörden; Beispieldaten: BZSt-Finanzamtsuche. Geoportal.de bietet die GDI-Recherche. Je Quelle fachliche Eignung, Abdeckung, Aktualität, tatsächlichen Datenzugang und Nutzungsbedingungen prüfen. | C1–2; L21–23, 70–72 |
| **Datenmodell** | Heterogene Geometrien und Sachdaten harmonisieren. **Ableitung:** Behörde, Zuständigkeitsthema, Gebietsgeometrie und Quell-ID verknüpfen,Verwaltungs-/PLZ-Grenzen nur bei fachlich belegter Zuständigkeit verwenden. | C1; L12–14, 44–47 |
| **OGC: Suche** | Katalog-/Metadatenrecherche über **CSW** (`GetRecords`, `GetRecordById`); `GetCapabilities` beschreibt unterstützte Funktionen. Ein Katalogtreffer ersetzt nicht den Bezug des eigentlichen Datensatzes. | L27–28, 54–55 |
| **OGC: Analyse** | Für Gebietsanalysen **Vektorobjekte** über **WFS** (`DescribeFeatureType`, `GetFeature`) oder geeignete Dateien beziehen. WFS-Filter begrenzen räumlich/fachlich die Datenmenge. Ein WMS-Kartenbild allein liefert keine analysierbaren Gebietsgeometrien. | L34–36, 58–59 |
| **OGC: Darstellung** | **WMS**: flexible Kartenbilder (`GetMap`), Sachauskunft nur bei optionalem `GetFeatureInfo`. **WMTS**: schnelle vorberechnete Kacheln (`GetTile`), dafür festgelegte Darstellung/Koordinatenbezüge. Layer, Formate und unterstützte CRS anhand der Capabilities prüfen. | L28–33, 56–58 |
| **Koordinaten & Geocodierung** | Adressen über einen geeigneten Geocoder räumlich zuordnen. CRS/EPSG jeder Quelle dokumentieren, Punkt und Zuständigkeitsgeometrien vor Analyse in einen gemeinsamen Bezug transformieren. Transformationsgenauigkeit und Viewer-Unterstützung prüfen. Ein bestimmtes EPSG-System wird für die Challenge nicht vorgeschrieben. | C1–2; L19, 30, 40, 57, 61, 73 |
| **Metadaten** | Datensätze **und** Dienste beschreiben: Titel, Herkunft/Qualität, Stand, Raum-/Zeitbezug, Maßstab/Genauigkeit, CRS, Format/Datenmodell, Bezugsquelle, Nutzungsbedingungen und Kontakt. Möglichst gemeinsam mit Daten automatisch pflegen. Für GDI-Anbindung nennt L ISO 19115/19119/19139 und GDI-DE-Metadatenkonventionen. | L21–23, 47–52, 55 |
| **Datenhaltung & Betrieb** | Für kleine Bestände reichen Dateien bzw. **GeoPackage**, nötigenfalls räumliche Datenbank. Ein separater Auskunftsbestand kann Primärsysteme schützen und entlasten, muss aber regelmäßig aktualisiert werden. Zuständigkeit für Pflege/Betrieb festlegen. | L44–47, 53–54 |
| **Dienstqualität** | Verfügbarkeit, Antwortzeit und gleichzeitige Nutzung planen und messen. Räumliche Indizes, Filter, Paging und Kacheln einsetzen. **Ableitung:** Ausfälle/veraltete Daten sichtbar melden. Die im PDF genannten INSPIRE-Service-Level, etwa 99 % Verfügbarkeit, sind keine dort belegte Hackathonpflicht. | C1–2; L62–66 |
| **Sicherheit** | BSI-Grundschutz als Orientierung; Schreib-/Administrationszugriffe authentifizieren und autorisieren, bei Bedarf Sicherheitsproxy vorschalten, Zugangsdaten über TLS übertragen. Sensible Primärdaten vor Veröffentlichung herausfiltern. | L47, 66–68 |
| **Datenschutz & Lizenzen** | L behandelt Personenbezug auch durch Datenverknüpfung sowie Schutz/Anonymisierung und die Beachtung der Datenlizenzen. **Ableitung:** Suchadressen möglichst ohne dauerhafte Speicherung verarbeiten und Weitergabe an externe Geocoder transparent machen. Lizenz/Attribution je Quelle dokumentieren. Kostenfreiheit allein klärt keine Nutzungsrechte. L nennt u. a. Creative Commons und Datenlizenz Deutschland. | L45, 69, 79 |
