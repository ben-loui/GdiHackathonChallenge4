# Datenquellen anbinden

Der Zuständigkeitsfinder kann beliebig viele WFS gleichzeitig nutzen. Jede Quelle ist eine TOML-Datei. Python-Code muss dafür nicht geändert werden: Behördentypen, Tool-Schema, LLM-Anweisungen und Quellenangaben entstehen aus der Konfiguration.

```
quellen/
├── bzb-open.toml               # Standard: BZB-Open des BKG (wird geladen)
└── bzb-eigen.toml.example      # Beispiel: eigener GeoServer mit BZB aus bzb-db (wird nicht geladen)
```

## Neue Quelle in drei Schritten

1. TOML-Datei anlegen, z. B. `quellen/vg250.toml`:

   ```toml
   [quelle]
   id = "vg250"
   kurzname = "VG250"
   titel = "Verwaltungsgebiete 1:250 000 (VG250)"
   herausgeber = "Bundesamt für Kartographie und Geodäsie (BKG)"
   wfs_url = "https://sgx.geodatenzentrum.de/wfs_vg250"
   lizenz = "dl-de/by-2-0"
   quellenvermerk = "VG250 © BKG (dl-de/by-2-0)"
   wfs_version = "2.0.0"

   [[behoerdentyp]]
   key = "landkreis"
   label = "Landkreis bzw. kreisfreie Stadt"
   layer_suche = "vg250_krs"
   name_attribut = "gen"
   ```

2. Prüfen:

   ```bash
   .venv/bin/python -c "import zustaendigkeit as zf; print(zf.finde_zustaendigkeit(lat=49.9987, lon=8.2711, typen=['landkreis']))"
   ```

3. Server neu starten. Die Typen stehen im Tool-Schema, in `/typen` und in den LLM-Anweisungen.

## Felder

### `[quelle]` (genau eine je Datei)

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `id` | ja | Eindeutiger Schlüssel aus `a-z`, `0-9`, `_`. Auch Name des Cache-Unterordners |
| `titel`, `herausgeber` | ja | Erscheinen in der Antwort unter `quellen` |
| `wfs_url` | ja | Basis-URL des WFS ohne Parameter |
| `quellenvermerk` | ja | Text, den das LLM als Quelle nennt |
| `kurzname` | | Kurzform für Server-Titel und Fehlermeldungen (sonst `id`) |
| `lizenz`, `info_url` | | Lizenz und Link auf Quellenverzeichnis oder Metadaten |
| `wfs_version` | | `1.1.0` (Standard) oder `2.0.0`. Bei 2.x werden `typeNames`/`count` statt `typeName`/`maxFeatures` gesendet |
| `output_format` | | GeoJSON-Format des Servers. Standard `application/json` (GeoServer, deegree, BKG). MapServer: `geojson`, QGIS Server: `application/vnd.geo+json` |
| `srs` | | Angefordertes CRS, Standard `EPSG:4326`. Der Dienst rechnet um |
| `crs_fallback` | | CRS für Meterkoordinaten, wenn die Antwort kein CRS nennt. Standard `EPSG:25832` |
| `seitengroesse` | | Features je Anfrage, Standard 1000. Kleiner wählen, wenn der Server weniger erlaubt |
| `auth_env` | | Name einer Umgebungsvariable mit `benutzer:passwort` für HTTP-Basic-Auth. Zugangsdaten nie in die TOML-Datei schreiben |

### `[[behoerdentyp]]` (eine oder mehrere)

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `key` | ja | Eindeutig über **alle** Quellen, aus `a-z`, `0-9`, `_`. So heißt der Typ im Tool |
| `label` | ja | Lesbarer Name, z. B. „Jobcenter“ |
| `layer` | eins von beiden | Fester Feature-Type-Name, z. B. `bzb-open:ba_arbeitsagenturen`. Spart den Abruf der Capabilities |
| `layer_suche` | eins von beiden | Suche in `GetCapabilities`: zuerst exakter Name mit oder ohne Namensraum (`bpol_inspektionen` trifft `bzb:bpol_inspektionen`, nicht `bzb:bpol_inspektionen_250`), sonst ein eindeutiger Teilstring. Bei mehreren Treffern gibt es einen Fehler |
| `name_attribut` | | Attribut mit dem Namen der zuständigen Stelle. Ohne Angabe gilt eine Heuristik (`name`, `bezeichnung`, `bez`, `lang`) |
| `uebergeordnet_attribut` | | Attribut mit der übergeordneten Stelle, z. B. Hauptzollamt zu einer Zollstelle. Erscheint als `uebergeordnet` in der Antwort |
| `anliegen` | | Beispiel-Anliegen, mit denen das LLM vom Anliegen auf den Typ schließt. Vor Produktivbetrieb fachlich prüfen |

Unbekannte Felder (z. B. Tippfehler), doppelte `id`/`key` und fehlende Pflichtfelder brechen den Start mit einer Meldung ab, die Datei und Eintrag nennt.

## Welche Dateien geladen werden

`ZF_QUELLEN` enthält Dateien oder Ordner, kommagetrennt. Aus Ordnern werden alle `*.toml` in alphabetischer Reihenfolge gelesen, `*.toml.example` nicht. Ohne `ZF_QUELLEN` gilt der Ordner `quellen/`.

```bash
ZF_QUELLEN=quellen,/etc/zustaendigkeit/quellen python mcp_server.py   # BZB-Open + eigene Quellen
ZF_QUELLEN=/etc/zustaendigkeit/quellen python mcp_server.py           # nur eigene Quellen
```

Im Container: Ordner einbinden und `ZF_QUELLEN` setzen, siehe Kommentare in `docker-compose.yml`.

## Anforderungen an einen eigenen WFS

- **Flächen:** Polygone oder Multipolygone, je Feature eine zuständige Stelle. Überlappungen sind erlaubt und werden als „Grenzlage oder Überlappung“ gemeldet.
- **GeoJSON-Ausgabe** für `GetFeature`, mit `startIndex`-Paging. Mit `totalFeatures` oder `numberMatched` prüft der Client, ob alle Features angekommen sind.
- **Lage:** Die Daten müssen in Deutschland liegen. Vertauschte Achsen und Meterkoordinaten werden erkannt und korrigiert.
- **Größe:** Ein Layer wird vollständig geladen und 30 Tage in `ZF_CACHE_DIR/<id>/` zwischengespeichert. Für bundesweite Flächen ist das unkritisch (BZB-Open: 3–12 MB je Layer). Sehr große Layer verlängern nur den ersten Abruf, danach läuft die Abfrage lokal.

## Beispiel: eigene BZB-Datenbank (`bzb-db`)

Das PostGIS-Schema `bzb_ows` aus `bzb-db` (Bundespolizei, Staatsanwaltschaften, THW, Zoll) ist mit GeoServer sofort als WFS nutzbar:

1. Datenbank laden: `bzb-db/laden.sh`
2. GeoServer: Workspace `bzb`, PostGIS-Store auf Schema `bzb_ows` mit Dienstkonto (z. B. Rolle `bzb_leser`), Layer aus den Views außer `datensatz` veröffentlichen.
3. `cp quellen/bzb-eigen.toml.example quellen/bzb-eigen.toml`, `wfs_url` anpassen, bei geschütztem Dienst `auth_env` setzen.

Die Beispieldatei enthält 16 Behördentypen mit passenden `name_attribut`- und `uebergeordnet_attribut`-Werten, z. B. `zst_lang`/`hza_lang` für Zollstellen.

> **Lizenz:** BZB (nicht Open) ist nur für Bundesbehörden und Nutzungsberechtigte nach § 4 V GeoBund freigegeben, je nach Vertrag nur für einzelne Themen. Einen öffentlich erreichbaren MCP-Server oder einen Tunnel nicht mit dieser Quelle betreiben, wenn das nicht ausdrücklich erlaubt ist.

## Antwortformat

Jedes Ergebnis nennt seine Quelle, und `quellen` listet nur die tatsächlich abgefragten Dienste:

```json
{
  "ort": {"lat": 49.9987, "lon": 8.2711, "anzeige": "…", "hinweise": []},
  "ergebnisse": [
    {"typ": "jobcenter", "label": "Jobcenter", "quelle": "bzb_open", "layer": "bzb-open:ba_jobcenter",
     "treffer": [{"name": "Jobcenter Mainz, Stadt", "attribute": {"…": "…"}}]},
    {"typ": "landkreis", "label": "Landkreis bzw. kreisfreie Stadt", "quelle": "vg250", "layer": "vg250:vg250_krs",
     "treffer": [{"name": "Mainz", "attribute": {"…": "…"}}]}
  ],
  "quellen": [
    {"id": "bzb_open", "titel": "…", "herausgeber": "…", "dienst": "…", "lizenz": "dl-de/by-2-0", "quellenvermerk": "…", "info_url": "…"},
    {"id": "vg250", "…": "…"}
  ],
  "geocoding": null
}
```

Der MCP-Server fasst die Quellenvermerke im Feld `quelle` zusammen, z. B. `"BZB-Open © BKG (dl-de/by-2-0); VG250 © BKG (dl-de/by-2-0)"`. Die REST-API listet die konfigurierten Quellen unter `GET /quellen`.
