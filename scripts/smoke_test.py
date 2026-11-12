"""
Smoke-Test: verbindet sich wie ein LLM-Client per MCP und ruft das Tool einmal auf.

    python scripts/smoke_test.py                                   # http://localhost:8000/mcp
    python scripts/smoke_test.py https://abc.trycloudflare.com/mcp # über den Tunnel
    python scripts/smoke_test.py --stdio                           # startet den Server selbst (stdio)
    python scripts/smoke_test.py --adresse "Domplatz 1, 55116 Mainz" --typ amtsgericht

Der erste Aufruf kann einige Sekunden dauern, weil die Zuständigkeitsflächen vom BKG-WFS geladen werden.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import anyio
from mcp.client import Client
from mcp.client.stdio import StdioServerParameters

ROOT = Path(__file__).resolve().parent.parent


def _ziel(args):
    if args.stdio:
        return StdioServerParameters(
            command=sys.executable, args=[str(ROOT / "mcp_server.py"), "--transport", "stdio"], cwd=str(ROOT)
        )
    return args.url


async def _lauf(args) -> int:
    ziel = _ziel(args)
    print(f"Verbinde mit {'stdio (lokaler Unterprozess)' if args.stdio else args.url} ...")
    async with Client(ziel, read_timeout_seconds=180) as c:
        tools = (await c.list_tools()).tools
        print("Tools:", ", ".join(t.name for t in tools))
        if not any(t.name == "zustaendigkeit_finden" for t in tools):
            print("FEHLER: Tool 'zustaendigkeit_finden' fehlt.")
            return 1

        params: dict = {"behoerdentypen": args.typ}
        if args.lat is not None and args.lon is not None:
            params |= {"lat": args.lat, "lon": args.lon}
        else:
            params["adresse"] = args.adresse
        print("Aufruf:", json.dumps(params, ensure_ascii=False))
        start = time.monotonic()
        r = await c.call_tool("zustaendigkeit_finden", params)
        dauer = time.monotonic() - start

    text = r.content[0].text if r.content else ""
    if r.is_error:
        print(f"FEHLER vom Tool ({dauer:.1f} s): {text}")
        return 1
    daten = json.loads(text)
    print(f"Ort: {daten['ort']['gefunden_als']}")
    for e in daten["ergebnisse"]:
        zeile = ", ".join(e["zustaendig"]) or "–"
        extra = e.get("fehler") or e.get("hinweis") or ""
        print(f"  {e['behoerde']}: {zeile}" + (f"  ({extra})" if extra else ""))
    print(f"Quelle: {daten['quelle']}")
    print(f"OK ({dauer:.1f} s)")
    return 0


def main() -> None:
    p = argparse.ArgumentParser(description="Smoke-Test für den Zuständigkeitsfinder-MCP-Server")
    p.add_argument("url", nargs="?", default="http://localhost:8000/mcp", help="MCP-Endpunkt (Standard: lokal)")
    p.add_argument("--stdio", action="store_true", help="Server als Unterprozess über stdio starten")
    p.add_argument("--adresse", default="Schillerplatz 1, 55116 Mainz")
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    p.add_argument("--typ", action="append", default=None,
                   help="Behördentyp, mehrfach möglich (Standard: arbeitsagentur und amtsgericht)")
    args = p.parse_args()
    args.typ = args.typ or ["arbeitsagentur", "amtsgericht"]
    try:
        sys.exit(anyio.run(_lauf, args))
    except Exception as e:  # Verbindungsfehler verständlich ausgeben
        while isinstance(e, BaseExceptionGroup) and e.exceptions:
            e = e.exceptions[0]
        print(f"FEHLER: {type(e).__name__}: {e}")
        if not args.stdio:
            print("Läuft der Server? Start mit: python mcp_server.py")
        sys.exit(1)


if __name__ == "__main__":
    main()
