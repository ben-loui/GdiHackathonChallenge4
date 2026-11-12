# Zuständigkeitsfinder an LLM-Clients anbinden

Der MCP-Server stellt ein Tool bereit: `zustaendigkeit_finden(adresse | lat+lon, behoerdentypen)`. Es gibt drei Wege, ihn an ein LLM anzubinden:

| Weg | Für | Server muss … |
|---|---|---|
| **Remote-Connector** (Streamable HTTP) | Claude.ai, Mistral Le Chat, ChatGPT | aus dem Internet per HTTPS erreichbar sein → [Tunnel](#1-server-starten) |
| **Lokaler MCP-Client** (HTTP oder stdio) | Claude Desktop, Claude Code, Cursor, VS Code, LM Studio | lokal laufen bzw. wird vom Client gestartet |
| **Beispiel-Chat** (Function Calling) | Mistral-API, OpenAI-API, Ollama, OpenRouter, jede OpenAI-kompatible API, Claude-API | wird vom Skript selbst gestartet |

## 1. Server starten

```bash
source .venv/bin/activate
python mcp_server.py                      # lokal: http://localhost:8000/mcp
python scripts/smoke_test.py              # prüft Verbindung und Beispielabfrage
```

Für Web-Clients eine öffentliche URL erzeugen. Die Anbieter verbinden sich von ihren eigenen Servern aus, `localhost` funktioniert dort nicht.

```bash
brew install cloudflared                  # einmalig (macOS)
./scripts/tunnel.sh                       # gibt https://<zufall>.trycloudflare.com/mcp aus
python scripts/smoke_test.py https://<zufall>.trycloudflare.com/mcp
```

Alternativ mit Docker: `docker compose --profile tunnel up -d`, die URL steht dann in `docker compose logs tunnel`.

Quick-Tunnel-URLs ändern sich bei jedem Start. Nach einem Neustart muss die URL im Connector aktualisiert werden.

## 2. Web-Chats

### Claude.ai

1. *Einstellungen → Connectors → Benutzerdefinierten Connector hinzufügen*
2. Name `Zustaendigkeitsfinder`, URL `https://<zufall>.trycloudflare.com/mcp`, ohne Authentifizierung
3. Im Chat über das Tools-Menü (Schieberegler-Symbol) den Connector aktivieren

Ob und wie viele eigene Connectors möglich sind, hängt vom Claude-Tarif ab. In Team- und Enterprise-Organisationen fügt sie ein Admin hinzu.

### Mistral Le Chat

1. *Intelligence → Connectors → + Add Connector → Custom MCP Connector*
2. Name ohne Leer- und Sonderzeichen, z. B. `zustaendigkeitsfinder`, dazu die URL `https://<zufall>.trycloudflare.com/mcp`
3. *Connect*, Authentifizierung: keine
4. Im Chat den Connector im Tools-Menü einschalten

In Team-Organisationen muss ein Admin den Connector anlegen. Siehe [Mistral-Doku zu MCP-Connectors](https://docs.mistral.ai/le-chat/knowledge-integrations/connectors/mcp-connectors).

### ChatGPT

1. *Einstellungen → Apps & Connectors → Erweitert → Entwicklermodus* einschalten
2. *Connector erstellen*: URL `https://<zufall>.trycloudflare.com/mcp`, Authentifizierung „Keine“
3. Im Chat den Entwicklermodus wählen und den Connector aktivieren

Der Entwicklermodus ist nicht in allen Tarifen verfügbar, und die Menüpfade ändern sich häufig. Siehe [OpenAI-Doku](https://developers.openai.com/api/docs/guides/developer-mode).

## 3. Lokale Clients

### Claude Code

Im Repo liegt bereits `.mcp.json`. Server starten (`python mcp_server.py`), dann `claude` im Repo-Ordner aufrufen und den Projekt-Server bestätigen. Ohne die Datei:

```bash
claude mcp add --transport http zustaendigkeitsfinder http://localhost:8000/mcp
```

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) bzw. `%APPDATA%\Claude\claude_desktop_config.json` (Windows). Claude Desktop startet den Server selbst über stdio. Pfade absolut angeben:

```json
{
  "mcpServers": {
    "zustaendigkeitsfinder": {
      "command": "/ABSOLUTER/PFAD/GdiHackathonChallenge4/.venv/bin/python",
      "args": ["/ABSOLUTER/PFAD/GdiHackathonChallenge4/mcp_server.py", "--transport", "stdio"]
    }
  }
}
```

Danach Claude Desktop neu starten.

### Cursor und VS Code

`.cursor/mcp.json` und `.vscode/mcp.json` liegen im Repo und zeigen auf `http://localhost:8000/mcp`. Server starten und das Repo öffnen. In VS Code erscheint der Server unter *MCP: List Servers*, in Cursor unter *Settings → MCP*.

### LM Studio

*Program → Install → Edit mcp.json* und eintragen:

```json
{ "mcpServers": { "zustaendigkeitsfinder": { "url": "http://localhost:8000/mcp" } } }
```

Ein Modell mit Tool-Unterstützung laden, z. B. Qwen3.

### MCP Inspector (ohne LLM)

```bash
npx @modelcontextprotocol/inspector
```

Transport „Streamable HTTP“, URL `http://localhost:8000/mcp`, *Connect → Tools → zustaendigkeit_finden*.

## 4. APIs ohne MCP-Client: Beispiel-Chats

Die Skripte starten den MCP-Server selbst. Es muss nichts laufen.

```bash
export MISTRAL_API_KEY=...
python examples/llm_chat.py --anbieter mistral

ollama pull qwen3 && python examples/llm_chat.py --anbieter ollama                      # komplett lokal
python examples/llm_chat.py --anbieter openai --frage "Welches Jobcenter ist für Domplatz 1, 55116 Mainz zuständig?"
python examples/llm_chat.py --anbieter eigen --base-url https://.../v1 --modell <name>   # LLM_API_KEY setzen

pip install "anthropic[mcp]" && export ANTHROPIC_API_KEY=...
python examples/claude_chat.py
```

| `--anbieter` | Basis-URL | Key-Variable | Standardmodell |
|---|---|---|---|
| `mistral` | `https://api.mistral.ai/v1` | `MISTRAL_API_KEY` | `mistral-large-latest` |
| `openai` | `https://api.openai.com/v1` | `OPENAI_API_KEY` | `gpt-4.1-mini` |
| `openrouter` | `https://openrouter.ai/api/v1` | `OPENROUTER_API_KEY` | mit `--modell` angeben |
| `ollama` | `http://localhost:11434/v1` | – | `qwen3` |
| `lmstudio` | `http://localhost:1234/v1` | – | mit `--modell` angeben |
| `eigen` | `--base-url` / `LLM_BASE_URL` | `LLM_API_KEY` | `--modell` / `LLM_MODEL` |

Das Modell braucht Function-Calling-Unterstützung. Mit `--server http://localhost:8000/mcp` oder einer Tunnel-URL wird ein laufender Server verwendet.

## 5. Testfragen

An diesen Fragen sieht man, ob das LLM das Tool richtig nutzt und ehrlich bleibt:

| Frage | Erwartung |
|---|---|
| Ich bin arbeitslos geworden und wohne Schillerplatz 1, 55116 Mainz. Wo muss ich mich melden? | Tool-Aufruf mit `arbeitsagentur`. Antwort: Agentur für Arbeit Mainz, mit Quelle |
| Welches Amtsgericht ist für Domplatz 1, 55116 Mainz zuständig? | `amtsgericht` → Amtsgericht Mainz |
| Wo beantrage ich Grundsicherung? Ich wohne in der Kaiserstraße 1, 60311 Frankfurt am Main. | `jobcenter` |
| Welches Jobcenter ist für mich zuständig? Ich wohne in Mainz. | Rückfrage nach der vollständigen Adresse oder Hinweis auf die ungenaue Adresse |
| Wo melde ich mein Auto an? Ich wohne Schillerplatz 1, 55116 Mainz. | Sagt offen, dass das Tool Kfz-Zulassung nicht abdeckt, und erfindet nichts |

Wenn ein Web-Chat das Tool nicht von selbst nutzt, hilft ein Hinweis in der Frage, z. B. „Nutze den Zuständigkeitsfinder“. Nicht jeder Client gibt die Server-Anweisungen (`instructions`) an das Modell weiter.

## Fehlersuche

| Problem | Lösung |
|---|---|
| Connector meldet „nicht erreichbar“ | `python scripts/smoke_test.py <URL>` ausführen. Läuft der Tunnel noch? Ist die URL aktuell und endet auf `/mcp`? |
| `421 Misdirected Request` / Host-Fehler | `ZF_ALLOWED_HOSTS` leer lassen oder die Tunnel-Domain eintragen |
| Erste Antwort dauert lange | Die Flächen werden einmalig vom BKG-WFS geladen. Mit `--vorladen` bzw. `ZF_VORLADEN=1` geschieht das schon beim Start |
| „Geocoding fehlgeschlagen“ / 429 | Nominatim erlaubt eine Anfrage pro Sekunde. Mit `ZF_USER_AGENT` einen echten Kontakt setzen |
| Modell ruft kein Tool auf | Ein Modell mit Function-Calling verwenden und das Tool in der Frage erwähnen |
