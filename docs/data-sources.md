# Datenquellen

Der MCP-Server nutzt standardmäßig zwei externe Dienste: BZB-Open des BKG für die Zuständigkeitsflächen und Nominatim (OpenStreetMap) für die Geokodierung. Weitere WFS werden per Konfiguration ergänzt, siehe [Datenquellen anbinden](datenquellen-anbinden.md).

## Zuständigkeitsflächen: BZB-Open (BKG)

| | |
|---|---|
| Produkt | [Behördenzuständigkeitsbereiche Open (BZB-Open)](https://gdz.bkg.bund.de/index.php/default/wfs-behoerdenzustaendigkeitsbereiche-open-wfs-bzb-open.html) |
| Dienst | WFS `https://sgx.geodatenzentrum.de/wfs_bzb_open` (Abruf als GeoJSON, `EPSG:4326`) |
| Inhalt | Agenturen für Arbeit, deren Geschäftsstellen, Jobcenter, Regionaldirektionen der BA, Amtsgerichte, Landgerichte, Oberlandesgerichte |
| Lizenz | [Datenlizenz Deutschland – Namensnennung 2.0](https://www.govdata.de/dl-de/by-2-0) |
| Quellenvermerk | © BKG (Jahr des Abrufs), dl-de/by-2-0, [Datenquellen BZB-Open](https://sgx.geodatenzentrum.de/web_public/gdz/datenquellen/datenquellen_bzb-open.pdf) |

Konfiguriert in [`quellen/bzb-open.toml`](../quellen/bzb-open.toml). So nutzt `zustaendigkeit.py` diesen und jeden weiteren WFS:

- **Layer:** `ba_arbeitsagenturen` ist fest eingetragen. Die übrigen Layer werden per Namenssuche (`layer_suche`) aus `GetCapabilities` ermittelt. Benennt das BKG Layer um, meldet das Tool einen Fehler für diesen Behördentyp, statt ein falsches Ergebnis zu liefern.
- **Abruf:** Ein Layer wird beim ersten Bedarf vollständig geladen, seitenweise zu je 1000 Features (je Quelle einstellbar). Fehlen Features gegenüber `totalFeatures`, bricht der Abruf mit Fehler ab.
- **Cache:** Die Flächen liegen 30 Tage als GeoJSON in `ZF_CACHE_DIR/<quelle>/` (Standard `~/.cache/zustaendigkeit`). Die Punkt-in-Polygon-Abfrage läuft danach lokal, ohne weitere Anfragen ans BKG. Zum Aktualisieren den Cache-Ordner löschen.
- **Achsen:** Vertauschte lat/lon-Achsen und Meterkoordinaten werden erkannt und korrigiert (ohne CRS-Angabe gilt `crs_fallback`, Standard EPSG:25832). Liegen die Daten nicht in Deutschland, gibt es einen Fehler.
- **Grenzlage:** Liegt ein Punkt auf einer Grenze oder in überlappenden Flächen, werden alle Treffer mit Hinweis zurückgegeben.

**Grenzen der Daten:** BZB-Open bildet örtliche Zuständigkeiten ab, aber keine Sonderzuständigkeiten (z. B. zentrale Mahngerichte oder konzentrierte Registergerichte) und keine Anschriften oder Öffnungszeiten. Stand und Genauigkeit stehen in der Quellenübersicht des BKG. Verbindlich ist immer die Auskunft der Behörde.

## Geokodierung: Nominatim (OpenStreetMap)

| | |
|---|---|
| Dienst | `https://nominatim.openstreetmap.org/search` (auf Deutschland beschränkt) |
| Daten | © [OpenStreetMap-Mitwirkende](https://www.openstreetmap.org/copyright), ODbL |
| Regeln | [Nominatim Usage Policy](https://operations.osmfoundation.org/policies/nominatim/): höchstens 1 Anfrage pro Sekunde, aussagekräftiger User-Agent, keine Autovervollständigung |

Der Server reiht Anfragen in einem Prozess nacheinander ein (1,1 s Abstand) und hält bis zu 1024 Ergebnisse im Speicher. Mehrere Prozesse oder Installationen stimmen sich dabei nicht ab. Für eine öffentliche Demo `ZF_USER_AGENT` mit einem echten Kontakt setzen. Für den Produktivbetrieb einen eigenen Geocoder verwenden, z. B. den [BKG-Geokodierungsdienst](https://gdz.bkg.bund.de/index.php/default/geokodierungsdienst-fur-adressen-und-geonamen-wfs-g.html) oder eine eigene Nominatim-Instanz.

Ist die Adresse nur auf Ortsebene gefunden worden, enthält das Ergebnis einen Hinweis. Innerhalb eines Ortes kann die Zuständigkeit wechseln.

## Datenschutz

- **Adresse:** Die eingegebene Adresse geht an Nominatim, nicht an das BKG oder andere WFS-Betreiber. Diese erhalten nur Layer-Abrufe ohne Bezug zur Anfrage.
- **Speicherung:** Der Server speichert Adressen nicht auf Platte. Sie stehen nur kurz im Speicher-Cache und gegebenenfalls in Zugriffslogs von Tunnel, Hosting und Nominatim.
- **LLM-Anbieter:** Wer den Server über einen Chat nutzt, gibt die Adresse auch an den jeweiligen LLM-Anbieter weiter.
- Keine vertraulichen Angaben in Suchanfragen verwenden.

## Kandidaten für Erweiterungen

Diese Quellen kommen für weitere Behördentypen in Frage. Vor einer Anbindung sind Abdeckung, Aktualität und Lizenz zu prüfen:

- **[Portalverbund Online-Gateway (PVOG)](https://pvog.fitko.de/):** Leistungen und zuständige Stellen aus den Verwaltungsportalen, z. B. für Kfz-Zulassung oder Bürgeramt. Zuordnung über den Amtlichen Regionalschlüssel (ARS); die Suchschnittstelle ist ohne Anmeldung nutzbar.
- **[BKG VG250](https://gdz.bkg.bund.de/index.php/default/open-data/wfs-verwaltungsgebiete-1-250-000-stand-01-01-wfs-vg250.html):** Gemeindegrenzen mit ARS, um eine Koordinate einer Gemeinde zuzuordnen. Als WFS direkt anbindbar, Beispiel in [Datenquellen anbinden](datenquellen-anbinden.md).
- **BZB (nicht Open) des BKG:** Bundespolizei, Staatsanwaltschaften, THW und Zoll. Nur für Nutzungsberechtigte; Vorlage für einen eigenen Dienst in `quellen/bzb-eigen.toml.example`.
- **BZSt-Finanzamtsuche** und Landesportale, wie in `Challenge.pdf` genannt.
