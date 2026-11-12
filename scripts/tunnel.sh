#!/usr/bin/env bash
# Startet den MCP-Server (falls er nicht schon läuft) und einen Cloudflare-Quick-Tunnel.
# Gibt die öffentliche URL aus, die man in Claude.ai, Le Chat oder ChatGPT einträgt.
#
#   ./scripts/tunnel.sh            # Port 8000
#   PORT=8010 ./scripts/tunnel.sh
#
# Voraussetzung: cloudflared (macOS: brew install cloudflared,
# sonst https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/).
# Quick-Tunnel-URLs sind zufällig und gelten nur, solange das Skript läuft. Für Demos gedacht.
set -euo pipefail
cd "$(dirname "$0")/.."

PORT="${PORT:-8000}"
PY="${PYTHON:-python3}"
[ -x .venv/bin/python ] && PY=.venv/bin/python

if ! command -v cloudflared >/dev/null 2>&1; then
  echo "cloudflared fehlt. macOS: brew install cloudflared" >&2
  echo "Andere Systeme: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" >&2
  exit 1
fi

PIDS=()
aufraeumen() { for p in "${PIDS[@]:-}"; do [ -n "$p" ] && kill "$p" 2>/dev/null || true; done; }
trap aufraeumen EXIT INT TERM

if curl -fs "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "MCP-Server läuft bereits auf Port $PORT."
else
  echo "Starte MCP-Server auf Port $PORT (Log: mcp_server.log) ..."
  "$PY" mcp_server.py --port "$PORT" --vorladen >mcp_server.log 2>&1 &
  PIDS+=($!)
  for _ in $(seq 1 30); do curl -fs "http://127.0.0.1:$PORT/health" >/dev/null 2>&1 && break; sleep 1; done
  curl -fs "http://127.0.0.1:$PORT/health" >/dev/null || { echo "Server startet nicht, siehe mcp_server.log" >&2; exit 1; }
fi

TUNNEL_LOG="$(mktemp)"
cloudflared tunnel --no-autoupdate --url "http://127.0.0.1:$PORT" >"$TUNNEL_LOG" 2>&1 &
PIDS+=($!)

URL=""
for _ in $(seq 1 60); do
  URL="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$TUNNEL_LOG" | head -1 || true)"
  [ -n "$URL" ] && break
  sleep 1
done
[ -n "$URL" ] || { echo "Keine Tunnel-URL erhalten:" >&2; cat "$TUNNEL_LOG" >&2; exit 1; }

cat <<INFO

  MCP-Server öffentlich erreichbar:

      $URL/mcp

  Diese URL als Custom Connector in Claude.ai, Mistral Le Chat oder ChatGPT eintragen
  (Authentifizierung: keine). Anleitung: docs/llm-clients.md
  Test:  $PY scripts/smoke_test.py $URL/mcp

  Beenden mit Ctrl+C.
INFO

wait
