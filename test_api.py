"""Tests der HTTP-API (`api.py`) gegen den Mock-WFS aus conftest.py."""
from fastapi.testclient import TestClient

import api

client = TestClient(api.app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_typen_und_anliegen():
    keys = {t["key"] for t in client.get("/typen").json()}
    assert {"arbeitsagentur", "jobcenter", "amtsgericht"} <= keys
    assert all("typ" in a for a in client.get("/anliegen").json())


def test_zustaendigkeit_mit_koordinate(zf):
    r = client.get("/zustaendigkeit", params={"lat": 50.5, "lon": 8.5, "typ": "arbeitsagentur"})
    assert r.status_code == 200
    assert r.json()["ergebnisse"][0]["treffer"][0]["name"] == "AG West"


def test_unbekannter_typ_422(zf):
    r = client.get("/zustaendigkeit", params={"lat": 50.5, "lon": 8.5, "typ": "kfz"})
    assert r.status_code == 422


def test_adresse_nicht_gefunden_404(zf, monkeypatch):
    def nf(a):
        raise zf.AdresseNichtGefunden("Keine Koordinate.")

    monkeypatch.setattr(zf, "geocode", nf)
    assert client.get("/zustaendigkeit", params={"adresse": "Nirgendwo 1"}).status_code == 404


def test_dienstfehler_502(zf, monkeypatch):
    def kaputt(params):
        raise zf.DienstFehler("WFS nicht erreichbar")

    monkeypatch.setattr(zf, "_get", kaputt)
    r = client.get("/zustaendigkeit", params={"lat": 50.5, "lon": 8.5, "typ": "jobcenter"})
    # Fehler pro Typ bricht die Antwort nicht ab, sondern steht im Ergebnis.
    assert r.status_code == 200
    assert "WFS nicht erreichbar" in r.json()["ergebnisse"][0]["fehler"]
