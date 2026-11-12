"""
HTTP-API für den Zuständigkeitsfinder.

Start:   uvicorn api:app --reload
Beispiel: /zustaendigkeit?adresse=Jakob-Welder-Weg 18, 55128 Mainz&typ=arbeitsagentur&typ=jobcenter
Doku:    /docs
"""
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

import zustaendigkeit as zf

app = FastAPI(
    title="Zuständigkeitsfinder",
    version="0.1.0",
    description="Adresse + Behördentyp → zuständige Stelle. Daten: BZB-Open (BKG).",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ZF_CORS", "*").split(","),
    allow_methods=["GET"],
)


@app.get("/typen")
def typen():
    """Verfügbare Behördentypen."""
    return zf.typen()


@app.get("/anliegen")
def anliegen():
    """Beispiel-Anliegen mit zugeordnetem Behördentyp (für Auswahllisten)."""
    return zf.anliegen()


@app.get("/zustaendigkeit")
def zustaendigkeit(
    adresse: str | None = Query(None, description="Vollständige Straßenadresse"),
    lat: float | None = None,
    lon: float | None = None,
    typ: list[str] | None = Query(None, description="Mehrfach möglich; ohne Angabe: alle"),
    geometrie: bool = False,
):
    try:
        return zf.finde_zustaendigkeit(adresse, lat=lat, lon=lon, typen=typ, mit_geometrie=geometrie)
    except zf.AdresseNichtGefunden as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except zf.ZustaendigkeitError as e:
        raise HTTPException(502, str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
