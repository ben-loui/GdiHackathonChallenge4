# Zuständigkeitsfinder für Chat-LLMs

[![Tests](https://github.com/ben-loui/GdiHackathonChallenge4/actions/workflows/tests.yml/badge.svg)](https://github.com/ben-loui/GdiHackathonChallenge4/actions/workflows/tests.yml)

Ein MCP-Server, mit dem Chat-LLMs wie Claude, Mistral oder ChatGPT die **örtlich zuständige Behörde zu einer Adresse** aus amtlichen Geodaten ermitteln, statt sie zu raten. Jede Antwort nennt ihre Quelle.

Das Projekt ist aus Challenge 4 „Zuständigkeitsfinder“ des [hack4GDI-DE](docs/original-requirements-de.md) entstanden. Statt einer eigenen Website stellen wir die Zuständigkeitsprüfung als Tool über das [Model Context Protocol](https://modelcontextprotocol.io) bereit.

```
„Ich bin arbeitslos und wohne Schillerplatz 1, 55116 Mainz. Wo melde ich mich?“
        │
        ▼
   LLM ──► MCP-Tool zustaendigkeit_finden(adresse, behoerdentypen=["arbeitsagentur"])
                │  Adresse → Koordinate          (Nominatim / OpenStreetMap)
                │  Punkt-in-Polygon              (BZB-Open, BKG-WFS)
                ▼
   „Zuständig ist die Agentur für Arbeit Mainz. Quelle: BZB-Open © BKG …“
```

**Abgedeckt:** Agentur für Arbeit und Geschäftsstellen, Jobcenter, Regionaldirektionen der BA, Amtsgerichte, Landgerichte, Oberlandesgerichte. Für andere Behörden liefert der Server bewusst nichts, und das LLM wird angewiesen, das offen zu sagen.

## Schnellstart (5 Minuten)

Voraussetzung: Python 3.11 oder neuer.

```bash
git clone https://github.com/ben-loui/GdiHackathonChallenge4.git
cd GdiHackathonChallenge4
make install                  # .venv + Abhängigkeiten
make server                   # MCP-Server: http://localhost:8000/mcp
```

In einem zweiten Terminal:

```bash
make smoke                    # verbindet sich wie ein LLM-Client und fragt Schillerplatz 1, Mainz ab
```

Ohne `make`: `python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt`, dann `.venv/bin/python mcp_server.py` und `.venv/bin/python scripts/smoke_test.py`.

### Mit einem LLM testen

| LLM / Client | Kürzester Weg |
|---|---|
| **Claude.ai, Mistral Le Chat, ChatGPT** | `make tunnel` (braucht `cloudflared`), dann die ausgegebene `https://…/mcp`-URL als Custom Connector eintragen |
| **Claude Code, Cursor, VS Code** | `make server` und das Repo öffnen. `.mcp.json`, `.cursor/mcp.json` und `.vscode/mcp.json` sind schon da |
| **Claude Desktop, LM Studio** | Eintrag in deren `mcp.json`, siehe Anleitung |
| **Mistral-API, OpenAI-API, Ollama, OpenRouter, …** | `python examples/llm_chat.py --anbieter mistral` (startet den Server selbst) |
| **Claude-API** | `python examples/claude_chat.py` |

Schritt-für-Schritt-Anleitungen, Testfragen und Fehlersuche: **[docs/llm-clients.md](docs/llm-clients.md)**

## Das Tool

`zustaendigkeit_finden` hat folgende Parameter:

- `adresse`: vollständige Straßenadresse, z. B. `"Domplatz 1, 55116 Mainz"`, **oder** `lat` und `lon` (WGS84)
- `behoerdentypen`: optional, z. B. `["jobcenter"]`. Ohne Angabe werden alle Typen geprüft

Die Antwort enthält den gefundenen Ort, pro Behördentyp die zuständige(n) Stelle(n) mit Rohattributen, Hinweise (ungenaue Adresse, Grenzlage) und die Quellenangabe. Zusätzlich gibt der Server dem LLM Anweisungen (`instructions`) mit: welche Behörden abgedeckt sind, wann es nach der Adresse fragen soll und dass es keine Anschriften erfinden darf.

## Projektaufbau

| Datei / Ordner | Zweck |
|---|---|
| `zustaendigkeit.py` | Kernlogik: Geokodierung, WFS-Abruf mit Cache, Punkt-in-Polygon |
| `mcp_server.py` | MCP-Server, Streamable HTTP (`/mcp`, `/health`) oder `--transport stdio` |
| `api.py` | Optionale REST-API (FastAPI) mit OpenAPI unter `/docs`, z. B. für GPT Actions |
| `examples/` | Beispiel-Chats für OpenAI-kompatible APIs und die Claude-API |
| `scripts/` | `smoke_test.py` (Verbindungstest), `tunnel.sh` (öffentliche URL) |
| `test_*.py`, `conftest.py` | Tests gegen einen Mock-WFS, ohne Internet |
| `Dockerfile`, `docker-compose.yml` | Container, optional mit Cloudflare-Tunnel |
| `docs/` | Client-Anleitungen, Datenquellen, Anforderungen der Challenge |
| `*.ipynb`, `*.py`, `notebooks/` | Notebooks und Übungen aus dem Hackathon. Die `.py`-Fassungen sind für REPLs wie Zed (`# %%`-Zellen) |

## Betrieb

```bash
make test                                            # Tests, offline
docker compose up -d                                 # Container auf Port 8000
docker compose --profile tunnel up -d                # zusätzlich öffentliche URL (docker compose logs tunnel)
uvicorn api:app --port 8001                          # REST-API statt MCP
```

| Variable | Wirkung |
|---|---|
| `PORT`, `HOST` | Adresse des MCP-Servers (Standard `0.0.0.0:8000`) |
| `ZF_TRANSPORT` | `http` (Standard) oder `stdio` |
| `ZF_VORLADEN=1` | Lädt alle Flächen beim Start, damit schon die erste Antwort schnell kommt |
| `ZF_CACHE_DIR` | Ort des Flächen-Caches (Standard `~/.cache/zustaendigkeit`, 30 Tage gültig) |
| `ZF_USER_AGENT` | User-Agent für Nominatim und WFS. Für öffentliche Demos einen echten Kontakt eintragen |
| `ZF_ALLOWED_HOSTS` | Erlaubte Host-Header, kommagetrennt (Schutz vor DNS-Rebinding bei festem Hosting) |
| `ZF_CORS` | Erlaubte Origins der REST-API |

API-Keys für die Beispiel-Chats stehen in `.env.example`.

## Vertrauenswürdigkeit und Grenzen

- **Quellen:** Zuständigkeitsflächen aus [BZB-Open](docs/data-sources.md) des BKG (dl-de/by-2-0), Geokodierung über OpenStreetMap/Nominatim. Beide stehen in jeder Antwort.
- **Keine Kontaktdaten:** Das Tool liefert keine Anschriften oder Öffnungszeiten. Ergänzt ein LLM sie, sollen sie als nicht aus dem Tool stammend gekennzeichnet sein.
- **Adressgenauigkeit:** Ein bloßer Ortsname kann falsch zugeordnet werden. Das Tool weist darauf hin, und das LLM soll nachfragen.
- **Sonderfälle:** Sonderzuständigkeiten (z. B. zentrale Mahngerichte) sind nicht abgebildet. Verbindlich ist die Auskunft der Behörde.
- **Nominatim:** höchstens eine Anfrage pro Sekunde. Für den Produktivbetrieb einen eigenen Geocoder einsetzen.
- **Datenschutz:** Adressen gehen an Nominatim und an den genutzten LLM-Anbieter, siehe [Datenquellen](docs/data-sources.md#datenschutz).

## Weiterentwickeln

Offene Ideen stehen in den [Issues](https://github.com/ben-loui/GdiHackathonChallenge4/issues). Neue Behördentypen werden in `BEHOERDENTYPEN` in `zustaendigkeit.py` eingetragen. Für andere Quellen als BZB-Open braucht es eine eigene Ladefunktion. Kandidaten stehen in [docs/data-sources.md](docs/data-sources.md#kandidaten-für-erweiterungen).

## Herkunft

Fork von [KTV02/GdiHackathonChallenge4](https://github.com/KTV02/GdiHackathonChallenge4). Der dort entwickelte Flask-Web-Prototyp ist hier entfernt und bleibt in der Git-Historie erhalten.
