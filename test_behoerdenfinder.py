"""Tests: Behördenkategorie + Ort -> Stelle mit Kontakt (VG250- und PVOG-Mock aus conftest.py, ohne Internet)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import api
import behoerdenfinder as bf
import conftest
import pvog

TESTSTADT = {"lat": 50.5, "lon": 8.5}  # Gemeinde Teststadt, ARS 064120000000
TESTDORF = {"lat": 50.5, "lon": 9.5}   # Gemeinde Testdorf, ARS 064350001001

KATEGORIEN_DES_PROJEKTS = [
    "finanzamt", "stadtverwaltung", "ordnungsamt", "buergeramt", "standesamt", "auslaenderbehoerde",
    "amtsgericht", "landgericht", "verwaltungsgericht", "polizei", "staatsanwaltschaft", "zoll", "jugendamt",
    "sozialamt", "jobcenter", "arbeitsagentur", "familienkasse", "wohngeldstelle", "bauamt",
    "strassenverkehrsbehoerde", "zulassungsstelle", "gesundheitsamt", "veterinaeramt", "umweltamt",
    "gewerbeamt", "ihk", "handwerkskammer", "rentenversicherung", "krankenkasse", "pflegekasse", "bafoegamt",
    "schulamt", "kreisverwaltung", "regierungsprs", "bundesamt_migration", "bundesverwaltungsamt",
]


# --------------------------------------------------------------------------- #
# Kategorien
# --------------------------------------------------------------------------- #
def test_alle_36_kategorien_des_projekts_sind_konfiguriert():
    assert list(bf.KATEGORIEN) == KATEGORIEN_DES_PROJEKTS


@pytest.mark.parametrize("eingabe, key", [
    ("finanzamt", "finanzamt"), ("Finanzamt", "finanzamt"), ("  FINANZAMT ", "finanzamt"),
    ("Bürgerbüro", "buergeramt"), ("buergerbuero", "buergeramt"), ("Bürgeramt / Bürgerbüro", "buergeramt"),
    ("Landratsamt", "kreisverwaltung"), ("Kfz-Zulassungsstelle", "zulassungsstelle"), ("BAMF", "bundesamt_migration"),
    ("Veterinäramt", "veterinaeramt"), ("regierungsprs", "regierungsprs"), ("Bezirksregierung", "regierungsprs"),
])
def test_kategorie_aus_schluesselwort_label_oder_synonym(eingabe, key):
    assert bf.kategorie_fuer(eingabe).key == key


def test_unbekannte_kategorie_mit_vorschlag():
    with pytest.raises(bf.KategorieUnbekannt, match="Meinten Sie: finanzamt"):
        bf.kategorie_fuer("finanzamtt")
    with pytest.raises(bf.KategorieUnbekannt, match="Erlaubt: finanzamt"):
        bf.kategorie_fuer("Hundefriseur")


def test_konfiguration_alle_leistungsschluessel_14_stellig():
    assert all(len(l) == 14 and l.isdigit() for k in bf.KATEGORIEN.values() for l in k.leistungen)


@pytest.mark.parametrize("toml, meldung", [
    ('[[kategorie]]\nkey="a"\nlabel="Amt A"\n[[kategorie]]\nkey="b"\nlabel="Amt B"\nsynonyme=["Amt A"]\n', "gehört schon"),
    ('[[kategorie]]\nkey="a"\nlabel="A"\nleistungen=["123"]\n', "14-stellig"),
    ('[[kategorie]]\nkey="a"\nlabel="A"\nflaeche=["x"]\n', "unbekannte Felder"),
    ('', "keine"),
])
def test_kategorien_konfigurationsfehler(tmp_path, toml, meldung):
    datei = tmp_path / "k.toml"
    datei.write_text(toml, encoding="utf-8")
    with pytest.raises(bf.zf.KonfigurationsFehler, match=meldung):
        bf.lade_kategorien(datei)


def test_kategorien_uebersicht_zeigt_abdeckung(zf):
    k = {e["key"]: e for e in bf.kategorien()}
    assert k["amtsgericht"]["flaechen"] == ["amtsgericht"] and k["amtsgericht"]["pvog"]
    assert k["staatsanwaltschaft"]["flaechen_nicht_konfiguriert"] == ["staatsanwaltschaft"]
    assert not k["staatsanwaltschaft"]["abgedeckt"]  # nur mit eigenem BZB-Dienst
    assert not k["krankenkasse"]["abgedeckt"] and not k["krankenkasse"]["raeumlich"]


# --------------------------------------------------------------------------- #
# PVOG-Client
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("roh, sauber", [
    ("00.00.KVMZ.05.52.01 Führerschein/Zulassungswesen", "Führerschein/Zulassungswesen"),
    ("Stadt Ingelheim - 32/2 Pass- und Meldewesen", "Stadt Ingelheim - Pass- und Meldewesen"),
    ("32/0 Allgemeine Ordnungsaufgaben", "Allgemeine Ordnungsaufgaben"),
    ("Finanzamt Mainz", "Finanzamt Mainz"),
    ("Polizeiinspektion 11 München", "Polizeiinspektion 11 München"),
    ("Kundenzentrum Chorweiler", "Kundenzentrum Chorweiler"),
])
def test_titel_ohne_interne_aktenzeichen(roh, sauber):
    assert pvog.bereinige_titel(roh) == sauber


def test_stelle_aus_oe_kontakt_und_platzhalter():
    s = pvog.stelle_aus_oe(conftest.PVOG_OES["OE.buergerbuero"], {"name": "Zuständige Stelle"})
    assert s["name"] == "Bürgerbüro" and s["titel_original"] == "32/2 Bürgerbüro"
    assert s["anschrift"]["strasse"] == "Rathausplatz 1" and s["anschrift"]["ort"] == "64283 Teststadt"
    assert s["telefon"] == ["06151 1150"] and s["email"] == ["buergerbuero@teststadt.de"]
    assert s["traeger"] == "Stadt Teststadt" and s["oeffnungszeiten"] == "Mo 8–12 Uhr"
    leer = pvog.stelle_aus_oe(conftest.PVOG_OES["OE.alle"])
    assert "strasse" not in leer["anschrift"]  # "keine Straße" ist ein Platzhalter


def test_pvog_falsche_schluessel():
    with pytest.raises(ValueError, match="ARS"):
        pvog.zustaendige_stellen("0641", ["99008001012000"])
    with pytest.raises(ValueError, match="LeiKa"):
        pvog.zustaendige_stellen("064120000000", ["99008"])


# --------------------------------------------------------------------------- #
# Behördenfinder
# --------------------------------------------------------------------------- #
def test_pvog_stelle_mit_kontakt_und_onlinedienst(pvog_mock):
    a = bf.finde_behoerde("Bürgerbüro", **TESTSTADT)
    assert a["kategorie"] == {"key": "buergeramt", "label": "Bürgeramt / Bürgerbüro"}
    assert a["ort"]["gemeinde"] == "Teststadt" and a["ort"]["ars"] == "064120000000"
    [s] = a["stellen"]
    assert s["name"] == "Bürgerbüro" and s["telefon"] == ["06151 1150"] and s["methode"] == "pvog"
    assert a["eindeutig"] and a["onlinedienste"] == [{"titel": "Termin buchen", "url": "https://termine.test/ts"}]
    assert a["leistung"]["leika"] == "99008001012000" and a["leistung"]["portal_url"] == "https://portal.test/perso"
    assert {q["id"] for q in a["quellen"]} == {"vg250", "pvog"}
    assert ("/v3/servicedescriptions/leikaid", {"leikaIds": "99008001012000", "ars": "064120000000", "size": 5}) in pvog_mock.aufrufe


def test_flaeche_und_pvog_werden_zusammengefuehrt(pvog_mock):
    a = bf.finde_behoerde("amtsgericht", **TESTSTADT)
    [s] = a["stellen"]
    assert s["name"] == "Amtsgericht Mitte"  # Name aus der Fläche (BZB-Open)
    assert s["methode"] == "flaeche+pvog" and s["telefon"] == ["06151 1200"]
    assert set(s["quellen"]) == {"bzb_open", "pvog"} and a["eindeutig"]
    assert {q["id"] for q in a["quellen"]} == {"bzb_open", "vg250", "pvog"}


def test_pvog_ohne_gegenstueck_ist_ergaenzend(pvog_mock, monkeypatch):
    monkeypatch.setitem(conftest.PVOG_LEISTUNGEN, ("99038001017000", "064120000000"),
                        conftest.PVOG_LEISTUNGEN[("99107108017000", "064120000000")])
    a = bf.finde_behoerde("arbeitsagentur", **TESTSTADT)
    assert [(s["name"], s.get("ergaenzend", False)) for s in a["stellen"]] == [
        ("AG West", False), ("Bundesagentur für Arbeit (BA), Servicecenter", True)]
    assert a["eindeutig"]  # ergänzende Stellen zählen nicht


def test_mehrere_ansprechpunkte_ohne_allzustaendigkeit_und_doppelte(pvog_mock):
    a = bf.finde_behoerde("buergeramt", **TESTDORF)
    assert [s["name"] for s in a["stellen"]] == ["Bürgerbüro Nord", "Bürgerbüro Süd"]
    assert not a["eindeutig"]
    assert any("mehrere Stellen" in h for h in a["hinweise"])
    assert any("nur Ansprechpunkte" in h for h in a["hinweise"])


def test_uebergebener_leistungsschluessel_zuerst_dann_leitleistung(pvog_mock):
    a = bf.finde_behoerde("buergeramt", **TESTSTADT, leika="99999999999999")
    assert pvog_mock.leika_abfragen() == ["99999999999999", "99008001012000"]
    assert a["leistung"]["leika"] == "99008001012000"
    assert any("übergebenen Leistungsschlüssel" in h for h in a["hinweise"])


def test_ungueltiger_leistungsschluessel(pvog_mock):
    with pytest.raises(ValueError, match="14-stellig"):
        bf.finde_behoerde("buergeramt", **TESTSTADT, leika="123")


def test_pvog_ausfall_liefert_flaeche_und_hinweis(pvog_mock):
    pvog_mock.kaputt = True
    a = bf.finde_behoerde("amtsgericht", **TESTSTADT)
    assert [s["name"] for s in a["stellen"]] == ["Amtsgericht Mitte"] and a["stellen"][0]["methode"] == "flaeche"
    assert any("PVOG nicht erreichbar" in h for h in a["hinweise"])


def test_nicht_raeumliche_kategorie_ohne_geokodierung(pvog_mock):
    a = bf.finde_behoerde("Krankenkasse", adresse="Teststraße 1")  # geocode ist gesperrt -> darf nicht laufen
    assert a["ort"] is None and a["stellen"] == [] and "eigene Krankenkasse" in a["hinweise"][0]
    assert pvog_mock.aufrufe == []


def test_kreis_und_regierungsbezirk_aus_vg250(pvog_mock):
    a = bf.finde_behoerde("Landratsamt", **TESTDORF)
    assert a["stellen"][0]["name"] == "Landkreis Testkreis"
    r = bf.finde_behoerde("regierungsprs", **TESTSTADT)
    assert r["stellen"][0]["name"] == "Regierungspräsidium Darmstadt"  # Hessen: sn_l 06
    assert r["stellen"][0]["gebiet"] == "Regierungsbezirk Darmstadt"


def test_ort_ausserhalb_der_gemeinden(pvog_mock):
    a = bf.finde_behoerde("buergeramt", lat=53.0, lon=11.5)
    assert a["ort"].get("ars") is None and a["stellen"] == []
    assert any("ARS" in h for h in a["hinweise"])
    assert pvog_mock.aufrufe == []


def test_kategorie_hinweis_und_fehlende_quelle(pvog_mock):
    a = bf.finde_behoerde("staatsanwaltschaft", **TESTSTADT)
    assert a["stellen"] == [] and a["hinweise"][0].startswith("Strafanzeigen")


# --------------------------------------------------------------------------- #
# REST
# --------------------------------------------------------------------------- #
client = TestClient(api.app)


def test_rest_get_und_post(pvog_mock):
    r = client.get("/behoerde", params={"kategorie": "Bürgerbüro", **TESTSTADT})
    assert r.status_code == 200 and r.json()["stellen"][0]["name"] == "Bürgerbüro"
    r = client.post("/behoerde", json={"kategorie": "buergeramt", **TESTSTADT, "leika": ["99008001012000"]})
    assert r.status_code == 200 and r.json()["leistung"]["leika"] == "99008001012000"


def test_rest_fehler(pvog_mock, monkeypatch):
    r = client.get("/behoerde", params={"kategorie": "finanzamtt", **TESTSTADT})
    assert r.status_code == 422 and "finanzamt" in r.json()["detail"]["kategorien"]
    assert client.post("/behoerde", json={"kategorie": "buergeramt"}).status_code == 422  # ohne Ort

    def nicht_gefunden(adresse):
        raise bf.zf.AdresseNichtGefunden("Keine Koordinate.")

    monkeypatch.setattr(bf.zf, "geocode", nicht_gefunden)
    assert client.get("/behoerde", params={"kategorie": "buergeramt", "adresse": "Nirgendwo"}).status_code == 404


def test_rest_kategorien():
    daten = client.get("/kategorien").json()
    assert [k["key"] for k in daten] == KATEGORIEN_DES_PROJEKTS
