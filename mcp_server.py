"""
MCP-Server: Zuständigkeitsfinder als Werkzeug für Chat-LLMs (z. B. Claude als Custom Connector).

Start:     python mcp_server.py            -> http://0.0.0.0:8000/mcp
Umgebung:  PORT (8000), ZF_VORLADEN=1 (Flächen beim Start laden),
           ZF_ALLOWED_HOSTS="meine-domain.de,abc.trycloudflare.com" (optionaler Host-Header-Schutz)
Benötigt:  mcp>=2 (Python-SDK), zustaendigkeit.py im selben Ordner
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Literal

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

import zustaendigkeit as zf

log = logging.getLogger("zustaendigkeit.mcp")

Behoerdentyp = Literal[
    "arbeitsagentur", "geschaeftsstelle", "jobcenter", "regionaldirektion",
    "amtsgericht", "landgericht", "oberlandesgericht",
]

_anliegen_text = "\n".join(f"- {a} -> {t}" for a, t in zf.ANLIEGEN.items())

INSTRUCTIONS = f"""\
Dieser Server ermittelt die örtlich zuständige Stelle in Deutschland anhand amtlicher
Zuständigkeitsflächen (BZB-Open des BKG).

Abgedeckt sind NUR: Agentur für Arbeit, deren Geschäftsstellen, Jobcenter, Regionaldirektionen der
Bundesagentur für Arbeit sowie Amtsgerichte, Landgerichte und Oberlandesgerichte.
Für andere Behörden (z. B. Bürgeramt, Kfz-Zulassung, Finanzamt, Ausländerbehörde) liefert der Server
nichts – sag das offen, statt ein Ergebnis zu konstruieren.

Vorgehen:
1. Leite aus dem Anliegen den passenden Behördentyp ab. Beispiele:
{_anliegen_text}
2. Ohne vollständige Straßenadresse (Straße, Hausnummer, PLZ oder Ort) frage nach. Nur ein Ortsname
   kann zu einem falschen Ergebnis führen, weil Zuständigkeiten innerhalb eines Ortes wechseln.
3. Gib den Namen der zuständigen Stelle an und weise auf Hinweise im Ergebnis hin (Grenzlage,
   ungenaue Adresse). Das Ergebnis enthält keine Anschriften oder Öffnungszeiten; die musst du
   ggf. anderweitig recherchieren und als solche kennzeichnen.
4. Nenne als Quelle: BZB-Open © BKG; Geocoding © OpenStreetMap-Mitwirkende.
"""

server = MCPServer(
    name="zustaendigkeitsfinder",
    title="Zuständigkeitsfinder (BZB-Open)",
    description="Örtlich zuständige Arbeitsagentur, Jobcenter oder Gericht zu einer Adresse in Deutschland.",
    instructions=INSTRUCTIONS,
    version="0.1.0",
)


def _kompakt(erg: dict) -> dict:
    """Ergebnis fürs LLM: Name zuerst, Rohattribute behalten, Geometrie weglassen."""
    return {
        "ort": {"gefunden_als": erg["ort"]["anzeige"], "lat": erg["ort"]["lat"],
                "lon": erg["ort"]["lon"], "hinweise": erg["ort"]["hinweise"]},
        "ergebnisse": [
            {
                "behoerde": e["label"],
                "zustaendig": [t["name"] for t in e.get("treffer", [])],
                "details": [t["attribute"] for t in e.get("treffer", [])],
                **({"hinweis": e["hinweis"]} if e.get("hinweis") else {}),
                **({"fehler": e["fehler"]} if e.get("fehler") else {}),
            }
            for e in erg["ergebnisse"]
        ],
        "quelle": "BZB-Open © BKG (dl-de/by-2-0); Geocoding © OpenStreetMap-Mitwirkende",
    }


@server.tool(
    name="zustaendigkeit_finden",
    title="Zuständige Stelle zu einer Adresse finden",
    annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False,
                                idempotent_hint=True, open_world_hint=True),
)
def zustaendigkeit_finden(
    adresse: str | None = None,
    behoerdentypen: list[Behoerdentyp] | None = None,
    lat: float | None = None,
    lon: float | None = None,
) -> dict:
    """Ermittelt für eine Adresse in Deutschland die örtlich zuständige Agentur für Arbeit,
    Geschäftsstelle, Jobcenter, Regionaldirektion, Amtsgericht, Landgericht oder Oberlandesgericht.

    Args:
        adresse: Vollständige Straßenadresse, z. B. "Jakob-Welder-Weg 18, 55128 Mainz".
        behoerdentypen: Welche Behörden gesucht werden. Ohne Angabe: alle. Möglichst nur die zum Anliegen passenden.
        lat: Breitengrad (WGS84), alternativ zur Adresse; nur zusammen mit lon.
        lon: Längengrad (WGS84), alternativ zur Adresse; nur zusammen mit lat.
    """
    try:
        erg = zf.finde_zustaendigkeit(adresse, lat=lat, lon=lon, typen=behoerdentypen)
    except zf.AdresseNichtGefunden as e:
        raise ToolError(f"{e} Bitte Straße, Hausnummer und PLZ oder Ort prüfen.") from e
    except ValueError as e:
        raise ToolError(str(e)) from e
    except zf.ZustaendigkeitError as e:
        raise ToolError(f"Datendienst gerade nicht verfügbar: {e}") from e
    return _kompakt(erg)


def _vorladen():
    for typ in zf.BEHOERDENTYPEN:
        try:
            zf.lade_flaechen(zf.layer_fuer(typ))
            log.info("Vorgeladen: %s", typ)
        except Exception as e:  # Start nicht blockieren
            log.warning("Vorladen %s fehlgeschlagen: %s", typ, e)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    if os.environ.get("ZF_VORLADEN") == "1":
        threading.Thread(target=_vorladen, daemon=True).start()

    hosts = [h.strip() for h in os.environ.get("ZF_ALLOWED_HOSTS", "").split(",") if h.strip()]
    security = (
        TransportSecuritySettings(enable_dns_rebinding_protection=True,
                                  allowed_hosts=hosts + ["localhost:*", "127.0.0.1:*"])
        if hosts else TransportSecuritySettings(enable_dns_rebinding_protection=False)
    )
    server.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8000")),
        stateless_http=True,
        json_response=True,
        transport_security=security,
    )
