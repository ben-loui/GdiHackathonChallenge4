import json
from pathlib import Path
import pytest
from behoerden_resolver.catalog import categories, category, plan, sources
from behoerden_resolver.db import resolve


def test_all_36_categories_and_existing_interface():
    rows = categories()
    assert len(rows) == len({r["id"] for r in rows}) == 36
    existing = Path(__file__).parents[2] / "behoerden-matcher/data/categories.json"
    if existing.exists():
        assert {r["id"] for r in rows} == {r["id"] for r in json.loads(existing.read_text())}
    assert category("Kreisverwaltung")["id"] == "kreisverwaltung"
    assert category("Bürgeramt")["id"] == "buergeramt"
    with pytest.raises(ValueError):
        category("irgendein Amt")


def test_nonspatial_does_not_need_database_or_fabricate_polygons():
    for code in ("rentenversicherung", "krankenkasse", "pflegekasse", "bundesverwaltungsamt"):
        result = resolve(code, 8.27, 50)
        assert result["status"] == "non_spatial"
        assert result["matches"] == []
    assert resolve("bafoegamt", 8.27, 50)["status"] == "context_required"
    assert resolve("bundesamt_migration", 8.27, 50)["status"] == "context_required"


@pytest.mark.parametrize("lon,lat", [(float("nan"), 50), (8, float("inf")), (181, 50), (8, 91)])
def test_invalid_coordinates_rejected_even_for_nonspatial(lon, lat):
    with pytest.raises(ValueError):
        resolve("krankenkasse", lon, lat)


def test_boundaries_are_not_authority_assignments():
    assert all(s["kind"] == "boundary_reference" for s in sources() if s["id"].startswith("vg25"))
    assert any(r["semantics"] == "boundary_reference" for r in plan("kreisverwaltung")["wfs"])
    assert all("wfs_bzb?" not in s.get("endpoint", "") and not s.get("endpoint", "").endswith("wfs_bzb") for s in sources())
    assert not any(s['semantics']=='authority' for s in plan('verwaltungsgericht')['wfs'])
    assert all(s['semantics']=='authority_point' for s in plan('verwaltungsgericht')['wfs'])
    assert plan("verwaltungsgericht")["local_derivations"][0]["id"] == "by_verwaltungsgericht_gesetz"
