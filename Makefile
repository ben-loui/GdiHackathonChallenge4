# Kurzbefehle. Alle Ziele nutzen das virtuelle Environment .venv.
PY := .venv/bin/python
PORT ?= 8000

.PHONY: install server stdio smoke tunnel test docker clean-cache

install:            ## .venv anlegen und alles für Server, Tests und Beispiele installieren
	python3 -m venv .venv
	$(PY) -m pip install -q --upgrade pip
	$(PY) -m pip install -q -r requirements-dev.txt

server:             ## MCP-Server auf http://localhost:$(PORT)/mcp
	$(PY) mcp_server.py --port $(PORT) --vorladen

smoke:              ## Beispielabfrage gegen den laufenden Server (URL=... für Tunnel)
	$(PY) scripts/smoke_test.py $(or $(URL),http://localhost:$(PORT)/mcp)

tunnel:             ## Server + öffentliche HTTPS-URL über cloudflared
	PORT=$(PORT) ./scripts/tunnel.sh

test:               ## Tests (offline)
	$(PY) -m pytest

docker:             ## Container bauen und starten
	docker compose up -d --build

clean-cache:        ## Zwischengespeicherte Zuständigkeitsflächen löschen
	rm -rf $${ZF_CACHE_DIR:-$$HOME/.cache/zustaendigkeit}
