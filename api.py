"""
HTTP-API für den Zuständigkeitsfinder.

Start:   uvicorn api:app --reload
Beispiele:
  /behoerde?kategorie=finanzamt&adresse=Schillerplatz 1, 55116 Mainz       (Kategorie -> Stelle mit Kontakt)
  /behoerde?kategorie=buergeramt&lat=49.9987&lon=8.2711&leika=99008001012000
  /zustaendigkeit?adresse=Jakob-Welder-Weg 18, 55128 Mainz&typ=arbeitsagentur (nur Zuständigkeitsflächen)
Doku:    /docs
"""
import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import behoerdenfinder as bf
import zustaendigkeit as zf

app = FastAPI(
    title="Zuständigkeitsfinder",
    version="0.3.0",
    description="Behördenkategorie + Adresse → örtlich zuständige Stelle mit Anschrift, Telefon und Onlinediensten. "
                "Daten: " + ", ".join(q.titel for q in zf.QUELLEN.values())
                + ", Portalverbund-Onlinegateway (PVOG).",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("ZF_CORS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class BehoerdeAnfrage(BaseModel):
    kategorie: str = Field(..., description="Schlüsselwort der Behördenkategorie, z. B. 'finanzamt' (siehe /kategorien)")
    adresse: str | None = Field(None, description="Vollständige Straßenadresse")
    lat: float | None = Field(None, description="Breitengrad WGS84 (statt Adresse, zusammen mit lon)")
    lon: float | None = Field(None, description="Längengrad WGS84")
    leika: list[str] | None = Field(None, description="Optional: LeiKa-Leistungsschlüssel (14-stellig), werden zuerst versucht")

    model_config = {"json_schema_extra": {"examples": [
        {"kategorie": "finanzamt", "adresse": "Schillerplatz 1, 55116 Mainz"},
        {"kategorie": "buergeramt", "lat": 49.9987, "lon": 8.2711, "leika": ["99008001012000"]},
    ]}}


def _behoerde(a: BehoerdeAnfrage) -> dict:
    try:
        return bf.finde_behoerde(a.kategorie, a.adresse, lat=a.lat, lon=a.lon, leika=a.leika)
    except bf.KategorieUnbekannt as e:
        raise HTTPException(422, {"fehler": str(e), "kategorien": list(bf.KATEGORIEN)})
    except zf.AdresseNichtGefunden as e:
        raise HTTPException(404, str(e))
    except ValueError as e:
        raise HTTPException(422, str(e))
    except zf.ZustaendigkeitError as e:
        raise HTTPException(502, str(e))


@app.get("/behoerde")
def behoerde(
    kategorie: str = Query(..., description="Schlüsselwort der Behördenkategorie, z. B. finanzamt"),
    adresse: str | None = Query(None, description="Vollständige Straßenadresse"),
    lat: float | None = None,
    lon: float | None = None,
    leika: list[str] | None = Query(None, description="Optional, mehrfach möglich: LeiKa-Leistungsschlüssel"),
):
    """Behördenkategorie + Ort → zuständige Stelle(n) mit Anschrift, Telefon, E-Mail, Öffnungszeiten und Onlinediensten."""
    return _behoerde(BehoerdeAnfrage(kategorie=kategorie, adresse=adresse, lat=lat, lon=lon, leika=leika))


@app.post("/behoerde")
def behoerde_post(anfrage: BehoerdeAnfrage):
    """Wie GET /behoerde, Parameter als JSON."""
    return _behoerde(anfrage)


@app.get("/kategorien")
def kategorien():
    """Die 36 Behördenkategorien mit Abdeckung (Zuständigkeitsflächen, PVOG, nicht räumlich)."""
    return bf.kategorien()


@app.get("/typen")
def typen():
    """Verfügbare Behördentypen."""
    return zf.typen()


@app.get("/quellen")
def quellen():
    """Konfigurierte Datenquellen (WFS) mit Lizenz und Quellenvermerk."""
    return zf.quellen()


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
