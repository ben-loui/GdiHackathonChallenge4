"""
MCP-Server: Zuständigkeitsfinder als Werkzeug für Chat-LLMs (z. B. Claude als Custom Connector).

Start:     python mcp_server.py                     -> http://localhost:8000/mcp (Streamable HTTP)
           python mcp_server.py --transport stdio   -> für lokale Clients, die den Server selbst starten
Umgebung:  PORT (8000), HOST (0.0.0.0), ZF_TRANSPORT (http|stdio), ZF_VORLADEN=1 (Flächen beim Start laden),
           ZF_QUELLEN (Quellen-Konfiguration, Standard: Ordner quellen/),
           ZF_ALLOWED_HOSTS="meine-domain.de,abc.trycloudflare.com" (optionaler Host-Header-Schutz)
Benötigt:  mcp>=2 (Python-SDK), zustaendigkeit.py im selben Ordner
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations
from starlette.requests import Request
from starlette.responses import JSONResponse

import behoerdenfinder as bf
import zustaendigkeit as zf

log = logging.getLogger("zustaendigkeit.mcp")

Behoerdentyp = Literal[tuple(zf.BEHOERDENTYPEN)]  # aus quellen/*.toml


def _aufzaehlung(teile: list[str]) -> str:
    return teile[0] if len(teile) == 1 else ", ".join(teile[:-1]) + " und " + teile[-1]


_labels = _aufzaehlung([t.label for t in zf.BEHOERDENTYPEN.values()])
_quellen_kurz = _aufzaehlung([q.name for q in zf.QUELLEN.values()])
_anliegen_text = "\n".join(f"- {a} -> {t}" for a, t in zf.ANLIEGEN.items()) or "- (keine Beispiele konfiguriert)"
_vermerke = "; ".join(q.quellenvermerk for q in zf.QUELLEN.values())

_kategorien_text = ", ".join(f"{k.key} ({k.label})" for k in bf.KATEGORIEN.values())

INSTRUCTIONS = f"""\
Dieser Server ermittelt die örtlich zuständige Stelle in Deutschland aus amtlichen Daten.

Werkzeuge:
- behoerde_finden (erste Wahl): Behördenkategorie + Adresse -> zuständige Stelle MIT Anschrift, Telefon,
  E-Mail, Öffnungszeiten und Onlinediensten (Zuständigkeitsflächen + Portalverbund PVOG).
  Kategorien: {_kategorien_text}.
- zustaendigkeit_finden: nur der Name aus amtlichen Zuständigkeitsflächen ({_quellen_kurz}) für:
  {_labels}.

Vorgehen:
1. Leite aus dem Anliegen die Behördenkategorie ab. Beispiele:
{_anliegen_text}
   Für Behörden außerhalb der Kategorien liefert der Server nichts – sag das offen.
2. Ohne vollständige Straßenadresse (Straße, Hausnummer, PLZ oder Ort) frage nach. Nur ein Ortsname
   kann zu einem falschen Ergebnis führen, weil Zuständigkeiten innerhalb eines Ortes wechseln.
3. Gib Name und Kontaktdaten genau so wieder, wie sie geliefert werden; erfinde keine Anschriften,
   Telefonnummern oder Öffnungszeiten. Ist "eindeutig" false, nenne die in Frage kommenden Stellen
   und dass die Zuständigkeit z. B. vom Stadtteil abhängen kann. Weise auf "hinweise" hin.
4. Nenne als Quelle die Angabe im Feld "quelle" des Ergebnisses (z. B. {_vermerke}; PVOG).
"""

server = MCPServer(
    name="zustaendigkeitsfinder",
    title=f"Zuständigkeitsfinder ({_quellen_kurz})",
    description=f"Örtlich zuständige Stelle zu einer Adresse in Deutschland: {_labels}.",
    instructions=INSTRUCTIONS,
    version="0.2.0",
)


def _kompakt(erg: dict) -> dict:
    """Ergebnis fürs LLM: Name zuerst, Rohattribute behalten, Geometrie weglassen."""
    def eintrag(e: dict) -> dict:
        treffer = e.get("treffer", [])
        out = {"behoerde": e["label"], "zustaendig": [t["name"] for t in treffer]}
        if any("uebergeordnet" in t for t in treffer):
            out["uebergeordnet"] = [t.get("uebergeordnet") for t in treffer]
        out["details"] = [t["attribute"] for t in treffer]
        for k in ("hinweis", "fehler"):
            if e.get(k):
                out[k] = e[k]
        return out

    vermerke = [q["quellenvermerk"] for q in erg["quellen"]]
    if erg.get("geocoding"):
        vermerke.append("Geocoding " + erg["geocoding"])
    return {
        "ort": {"gefunden_als": erg["ort"]["anzeige"], "lat": erg["ort"]["lat"],
                "lon": erg["ort"]["lon"], "hinweise": erg["ort"]["hinweise"]},
        "ergebnisse": [eintrag(e) for e in erg["ergebnisse"]],
        "quelle": "; ".join(vermerke),
    }


@server.tool(
    name="zustaendigkeit_finden",
    title="Zuständige Stelle zu einer Adresse finden",
    description=f"""Ermittelt für eine Adresse in Deutschland die örtlich zuständige Stelle: {_labels}.

Args:
    adresse: Vollständige Straßenadresse, z. B. "Jakob-Welder-Weg 18, 55128 Mainz".
    behoerdentypen: Welche Behörden gesucht werden. Ohne Angabe: alle. Möglichst nur die zum Anliegen passenden.
    lat: Breitengrad (WGS84), alternativ zur Adresse; nur zusammen mit lon.
    lon: Längengrad (WGS84), alternativ zur Adresse; nur zusammen mit lat.
""",
    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                idempotent_hint=True, open_world_hint=True),
)
def zustaendigkeit_finden(
    adresse: str | None = None,
    behoerdentypen: list[Behoerdentyp] | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    try:
        erg = zf.finde_zustaendigkeit(adresse, lat=lat, lon=lon, typen=behoerdentypen)
    except zf.AdresseNichtGefunden as e:
        raise ToolError(f"{e} Bitte Straße, Hausnummer und PLZ oder Ort prüfen.") from e
    except ValueError as e:
        raise ToolError(str(e)) from e
    except zf.ZustaendigkeitError as e:
        raise ToolError(f"Datendienst gerade nicht verfügbar: {e}") from e
    return _kompakt(erg)


_OHNE = {"pvog_id", "titel_original"}


@server.tool(
    name="behoerde_finden",
    title="Zuständige Behörde mit Kontaktdaten finden",
    description=f"""Ermittelt zu einer Behördenkategorie und einer Adresse in Deutschland die örtlich zuständige
Stelle mit Anschrift, Telefon, E-Mail, Öffnungszeiten und Onlinediensten.

Args:
    kategorie: Schlüsselwort der Behördenkategorie, z. B. "finanzamt", "buergeramt", "zulassungsstelle".
        Erlaubt: {", ".join(bf.KATEGORIEN)}.
    adresse: Vollständige Straßenadresse, z. B. "Schillerplatz 1, 55116 Mainz".
    lat: Breitengrad (WGS84), alternativ zur Adresse; nur zusammen mit lon.
    lon: Längengrad (WGS84), alternativ zur Adresse; nur zusammen mit lat.
    leika: Optional: LeiKa-Leistungsschlüssel (14-stellig) der konkreten Leistung, falls bekannt.
""",
    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                idempotent_hint=True, open_world_hint=True),
)
def behoerde_finden(
    kategorie: str,
    adresse: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    leika: list[str] | None = None,
) -> dict:
    try:
        a = bf.finde_behoerde(kategorie, adresse, lat=lat, lon=lon, leika=leika)
    except zf.AdresseNichtGefunden as e:
        raise ToolError(f"{e} Bitte Straße, Hausnummer und PLZ oder Ort prüfen.") from e
    except ValueError as e:
        raise ToolError(str(e)) from e
    except zf.ZustaendigkeitError as e:
        raise ToolError(f"Datendienst gerade nicht verfügbar: {e}") from e
    ort = a["ort"] and {"gefunden_als": a["ort"]["anzeige"], "gemeinde": a["ort"].get("gemeinde"),
                        "hinweise": a["ort"]["hinweise"]}
    return {
        "kategorie": a["kategorie"]["label"],
        "ort": ort,
        "stellen": [{k: v for k, v in s.items() if k not in _OHNE} for s in a["stellen"]],
        "eindeutig": a["eindeutig"],
        "leistung": a["leistung"] and a["leistung"]["name"],
        "onlinedienste": a["onlinedienste"],
        "hinweise": a["hinweise"],
        "quelle": "; ".join(q["quellenvermerk"] for q in a["quellen"]),
    }


@server.custom_route("/health", methods=["GET"], include_in_schema=False)
async def health(_request: Request) -> JSONResponse:
    """Für Docker-Healthcheck, Tunnel und Hosting-Plattformen. Prüft nur den Server, nicht den WFS."""
    return JSONResponse({
        "status": "ok",
        "server": server.name,
        "version": server.version,
        "mcp_endpunkt": "/mcp",
        "quellen": sorted(zf.QUELLEN),
        "geladene_layer": zf.geladene_layer(),
    })


def _vorladen():
    for typ in zf.BEHOERDENTYPEN:
        if not zf.vorladbar(typ):  # Punktabfrage, z. B. VG250-Gemeinden
            continue
        try:
            zf.lade_flaechen_fuer(typ)
            log.info("Vorgeladen: %s", typ)
        except Exception as e:  # Start nicht blockieren
            log.warning("Vorladen %s fehlgeschlagen: %s", typ, e)


def _argumente(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Zuständigkeitsfinder als MCP-Server.",
        epilog="Beispiele: 'python mcp_server.py' (HTTP auf Port 8000), "
               "'python mcp_server.py --transport stdio' (für Claude Desktop, Cursor, LM Studio).",
    )
    p.add_argument("--transport", choices=["http", "stdio"],
                   default=os.environ.get("ZF_TRANSPORT", "http"),
                   help="http = Streamable HTTP unter /mcp (Standard), stdio = Unterprozess eines lokalen Clients")
    p.add_argument("--host", default=os.environ.get("HOST", "0.0.0.0"), help="Nur für http (Standard 0.0.0.0)")
    p.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8000")), help="Nur für http (Standard 8000)")
    p.add_argument("--vorladen", action="store_true", default=os.environ.get("ZF_VORLADEN") == "1",
                   help="Alle Zuständigkeitsflächen beim Start im Hintergrund laden")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _argumente(argv)
    # Logs immer nach stderr: bei stdio gehört stdout ausschließlich dem MCP-Protokoll.
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    if args.vorladen:
        threading.Thread(target=_vorladen, daemon=True).start()

    if args.transport == "stdio":
        server.run(transport="stdio")
        return

    hosts = [h.strip() for h in os.environ.get("ZF_ALLOWED_HOSTS", "").split(",") if h.strip()]
    security = (
        TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                  allowed_hosts=hosts + ["localhost:*", "127.0.0.1:*"])
        if hosts else TransportSecuritySettings(enable_dns_rebinding_protection=False)
    )
    log.info("MCP-Endpunkt: http://%s:%d/mcp", "localhost" if args.host == "0.0.0.0" else args.host, args.port)
    server.run(
        transport="streamable-http",
        host=args.host,
        port=args.port,
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )


if __name__ == "__main__":
    main()
