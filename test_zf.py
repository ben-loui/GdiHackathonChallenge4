"""Tests der Kernlogik `zustaendigkeit.py` gegen den Mock-WFS aus conftest.py."""
from __future__ import annotations

import pytest


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #
def test_eindeutiger_treffer(zf):
    erg = zf.finde_zustaendigkeit(lat=50.5, lon=8.5, typen=["arbeitsagentur"])
    e = erg["ergebnisse"][0]
    assert [t["name"] for t in e["treffer"]] == ["AG West"]
    assert e["treffer"][0]["attribute"]["dst_nr"] == "111"
    assert "hinweis" not in e
    assert [q["id"] for q in erg["quellen"]] == ["bzb_open"]
    assert erg["quellen"][0]["herausgeber"].startswith("Bundesamt")
    assert e["quelle"] == "bzb_open"
    assert erg["geocoding"] is None


def test_grenzlage_liefert_beide_flaechen_und_hinweis(zf):
    e = zf.finde_zustaendigkeit(lat=50.5, lon=9.0, typen=["arbeitsagentur"])["ergebnisse"][0]
    assert sorted(t["name"] for t in e["treffer"]) == ["AG Ost", "AG West"]
    assert "Mehrere Flächen" in e["hinweis"]


def test_punkt_ausserhalb_der_flaechen(zf):
    e = zf.finde_zustaendigkeit(lat=50.5, lon=8.5, typen=["jobcenter"])["ergebnisse"][0]
    assert e["treffer"] == []
    assert "Keine Fläche" in e["hinweis"]


def test_layer_wird_aus_capabilities_ermittelt(zf):
    assert zf.layer_fuer("jobcenter") == "bzb-open:ba_jobcenter"
    assert zf.layer_fuer("arbeitsagentur") == "bzb-open:ba_arbeitsagenturen"


def test_fehlender_layer_wird_als_fehler_gemeldet_ohne_abbruch(zf):
    erg = zf.finde_zustaendigkeit(lat=50.5, lon=8.5, typen=["oberlandesgericht", "arbeitsagentur"])
    olg, aa = erg["ergebnisse"]
    assert "Kein Layer" in olg["fehler"]
    assert aa["treffer"][0]["name"] == "AG West"


def test_vertauschte_achsen_werden_korrigiert(zf):
    e = zf.finde_zustaendigkeit(lat=50.5, lon=8.5, typen=["amtsgericht"])["ergebnisse"][0]
    assert [t["name"] for t in e["treffer"]] == ["Amtsgericht Mitte"]


def test_paging_laedt_alle_features(zf, mock_wfs, monkeypatch):
    monkeypatch.setattr(zf, "SEITENGROESSE", 2)
    gdf = zf.lade_flaechen("bzb_open", "bzb-open:justiz_landgerichte")
    assert len(gdf) == 5
    seiten = [a for a in mock_wfs.aufrufe if a["request"] == "GetFeature"]
    assert [a["startIndex"] for a in seiten] == [0, 2, 4]


def test_dateicache_verhindert_erneuten_abruf(zf, mock_wfs):
    zf.lade_flaechen("bzb_open", "bzb-open:ba_arbeitsagenturen")
    zf._flaechen.clear()  # Speicher leeren, Datei bleibt
    zf.lade_flaechen("bzb_open", "bzb-open:ba_arbeitsagenturen")
    assert sum(a["request"] == "GetFeature" for a in mock_wfs.aufrufe) == 1


def test_unbekannter_typ(zf):
    with pytest.raises(ValueError, match="Unbekannte"):
        zf.finde_zustaendigkeit(lat=50.5, lon=8.5, typen=["kfz"])


def test_koordinate_ausserhalb_deutschlands(zf):
    with pytest.raises(ValueError, match="außerhalb"):
        zf.finde_zustaendigkeit(lat=8.5, lon=50.5)


def test_ohne_adresse_und_koordinate(zf):
    with pytest.raises(ValueError):
        zf.finde_zustaendigkeit()


def test_adresse_wird_geokodiert(zf, monkeypatch):
    monkeypatch.setattr(zf, "geocode", lambda a: zf.Ort(50.5, 8.5, "Teststraße 1, Testort", ["Hinweis"]))
    erg = zf.finde_zustaendigkeit("Teststraße 1", typen=["arbeitsagentur"])
    assert erg["ort"]["anzeige"] == "Teststraße 1, Testort"
    assert erg["ort"]["hinweise"] == ["Hinweis"]
    assert "OpenStreetMap" in erg["geocoding"]
    assert erg["ergebnisse"][0]["treffer"][0]["name"] == "AG West"


def test_geometrie_optional(zf):
    e = zf.finde_zustaendigkeit(lat=50.5, lon=8.5, typen=["arbeitsagentur"], mit_geometrie=True)
    assert e["ergebnisse"][0]["treffer"][0]["geometrie"]["type"] == "Polygon"
