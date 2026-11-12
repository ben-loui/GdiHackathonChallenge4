# Zuständigkeitsfinder für Chat-LLMs (hack4GDI-DE, Challenge 4)

Dieses Projekt ist ein Werkzeug, mit dem Chat-LLMs wie Claude auf einen **geodatenbasierten Zuständigkeitsfinder** zugreifen. Damit können sie belastbare Angaben machen, statt die zuständige Stelle zu raten.

Grundlage ist Challenge 4 „Zuständigkeitsfinder“ des hack4GDI-DE (siehe `Challenge.pdf` und [Kurzanforderungen](docs/original-requirements-de.md)). Wir wandeln die Challenge ab: Statt einer eigenen Website stellen wir die Zuständigkeitsprüfung als **MCP-Server** (Model Context Protocol) bereit. Ein LLM ruft ihn als Tool auf und bekommt eine Antwort aus amtlichen Daten, mit Quellenangabe.

```
Nutzer:in fragt im Chat ──► LLM ──► MCP-Tool `zustaendigkeit_finden`
                                       │
                                       ├─ Adresse → Koordinate (Nominatim / OSM)
                                       └─ Punkt-in-Polygon gegen BZB-Open-Flächen (BKG-WFS)
                                       ▼
                       zuständige Stelle + Hinweise + Quelle
```

**Abgedeckte Behörden:** Agentur für Arbeit und deren Geschäftsstellen, Jobcenter, Regionaldirektionen der BA, Amtsgerichte, Landgerichte und Oberlandesgerichte. Für andere Behörden liefert der Server bewusst kein Ergebnis, und das LLM wird angewiesen, das offen zu sagen.

## Dateien

| Datei | Zweck |
|---|---|
| `zustaendigkeit.py` | Kernlogik: `finde_zustaendigkeit(adresse, typen=[...])`, WFS-Abruf mit lokalem Cache |
| `mcp_server.py` | MCP-Server (Streamable HTTP) unter `/mcp` mit dem Tool `zustaendigkeit_finden` |
| `api.py` | HTTP-API (FastAPI): `/zustaendigkeit`, `/typen`, `/anliegen`, `/health` |
| `test_mcp.py` | Tests für den MCP-Server, benötigen noch `test_zf.py` (siehe Offene Punkte) |
| `Dockerfile` | Container für den dauerhaften Betrieb des MCP-Servers |
| `zustaendigkeitsfinder.ipynb` | Notebook mit den Einzelschritten |
| `Uebung_Geodatenbasierter_Zustaendigkeitsfinder.ipynb` / `.py` / `.pdf` | Übung aus dem Hackathon. Die `.py`-Fassung ist für REPLs wie Zed (`# %%`-Zellen) |
| `notebooks/explore_bzb.ipynb` / `.py` | Erkundung des BZB-Open-WFS |
| `exercise_gdi_urban_comfort_de_student.ipynb` / `.py` | Allgemeine GDI-Übung des Hackathons |
| `docs/` | Kurzanforderungen der Challenge und Notizen zu Datenquellen |

## Lokal starten

Benötigt wird Python 3.11 oder neuer. Für Tests `requirements-dev.txt`, für die Notebooks `notebooks/requirements.txt` installieren.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

python mcp_server.py                 # MCP-Server: http://localhost:8000/mcp
uvicorn api:app --reload             # alternativ HTTP-API: http://localhost:8000/docs
```

Testen mit dem MCP Inspector: `npx @modelcontextprotocol/inspector`. Dort `http://localhost:8000/mcp` eintragen und das Tool aufrufen.

Der erste Aufruf pro Layer lädt die Flächen vom WFS und legt sie unter `~/.cache/zustaendigkeit` ab. Der Cache gilt 30 Tage, `ZF_CACHE_DIR` ändert den Ort. Danach läuft die Abfrage lokal.

## In Claude als Connector einbinden

Claude verbindet sich von Anthropics Servern aus, deshalb muss der MCP-Server aus dem Internet erreichbar sein:

```bash
cloudflared tunnel --url http://localhost:8000                                   # schnelle Demo-URL
docker build -t zf-mcp . && docker run -p 8000:8000 -v zf-data:/data zf-mcp     # dauerhaft
```

In Claude: *Einstellungen → Connectors → Benutzerdefinierten Connector hinzufügen*, Server `https://<domain>/mcp`, Authentifizierung „Keine“. Mit `ZF_ALLOWED_HOSTS=<domain>` prüft der Server zusätzlich den Host-Header.

## Umgebungsvariablen

| Variable | Wirkung |
|---|---|
| `PORT` | Port des MCP-Servers (Standard 8000) |
| `ZF_VORLADEN=1` | Lädt alle Flächen beim Start vor |
| `ZF_ALLOWED_HOSTS` | Erlaubte Host-Header, kommagetrennt |
| `ZF_CACHE_DIR` | Ort des Flächen-Caches |
| `ZF_USER_AGENT` | User-Agent für Nominatim und WFS. Vor einer öffentlichen Demo einen echten Kontakt eintragen |
| `ZF_CORS` | Erlaubte Origins der HTTP-API |

## Vertrauenswürdigkeit und Grenzen

- Die Zuständigkeitsflächen stammen aus **BZB-Open** des BKG (dl-de/by-2-0). Das Geocoding kommt von **OpenStreetMap/Nominatim**. Beide Quellen werden in jeder Antwort genannt.
- Das Ergebnis enthält Namen und Rohattribute, aber keine Anschriften oder Öffnungszeiten. Ergänzt das LLM solche Angaben, muss es sie als nicht aus dem Tool stammend kennzeichnen.
- Ein bloßer Ortsname kann falsch zugeordnet werden, weil Zuständigkeiten innerhalb eines Ortes wechseln. Das Tool weist auf ungenaue Adressen und Grenzlagen hin.
- Öffentliches Nominatim erlaubt höchstens eine Anfrage pro Sekunde. Für den Produktivbetrieb einen eigenen Geocoder einsetzen, z. B. die BKG-Geokodierung.

## Offene Punkte

- `test_zf.py` (Mock-WFS-Fixture) fehlt noch, deshalb laufen die Tests in `test_mcp.py` derzeit nicht.
- Weitere Behördentypen (z. B. Finanzamt, Kfz-Zulassung) mit passenden amtlichen Quellen ergänzen.
- `docs/data-sources.md` beschreibt noch Quellen des früheren Web-Ansatzes (PVOG) und sollte an den MCP-Ansatz angepasst werden.

## Herkunft

Fork von [KTV02/GdiHackathonChallenge4](https://github.com/KTV02/GdiHackathonChallenge4). Der dort entwickelte Flask-Web-Prototyp ist in diesem Repo entfernt und bleibt in der Git-Historie erhalten. Hier wird der MCP-Ansatz weiterentwickelt.
