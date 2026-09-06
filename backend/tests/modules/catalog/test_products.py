"""Tests for Product's own cost/margin computed properties - no
dedicated file existed for these despite several already being on the
model (suggested_cost_price, suggested_selling_price, margin,
actual_margin_percent). Focuses on the two added for P0.1 section 2:
bom_cost (what the BOM says material should cost right now,
at real current Material.average_rate prices) and
bom_cost_variance (how far the manually-entered material_cost
has drifted from that)."""
from tests.helpers import _login


def test_bom_cost_derives_from_real_material_rates(client, test_user):
    _login(client, test_user)
    sheet = client.post("/api/materials/", json={
        "name": "BOM Cost Sheet", "unit": "Sheets", "opening_stock": "10", "average_rate": "1500.00",
    }).json()
    hinge = client.post("/api/materials/", json={
        "name": "BOM Cost Hinge", "unit": "Pieces", "opening_stock": "100", "average_rate": "25.00",
    }).json()
    product = client.post("/api/products/", json={
        "name": "BOM Cost Product", "unit": "Piece",
        "materials_used": [
            {"material_id": sheet["id"], "quantity_required": "3"},
            {"material_id": hinge["id"], "quantity_required": "4"},
        ],
    }).json()

    # 3 x 1500 + 4 x 25 = 4600
    assert product["bom_cost"] == 4600.0


def test_bom_cost_is_none_without_any_bom(client, test_user):
    _login(client, test_user)
    product = client.post("/api/products/", json={"name": "No BOM Product", "unit": "Piece"}).json()
    assert product["bom_cost"] is None
    assert product["bom_cost_variance"] is None


def test_bom_cost_variance_flags_a_stale_manual_estimate(client, test_user):
    """P0.1 section 2's comparison example - the manually-entered
    material_cost can drift from what the BOM says it should cost
    today; the variance must say by how much and in which direction."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Variance Sheet", "unit": "Sheets", "opening_stock": "10", "average_rate": "2000.00",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Variance Product", "unit": "Piece", "material_cost": "5000.00",
        "materials_used": [{"material_id": material["id"], "quantity_required": "3"}],
    }).json()

    # BOM says 3 x 2000 = 6000, manual estimate was 5000 - variance +1000
    # (the BOM-derived figure is 1000 higher than the manual estimate).
    assert product["bom_cost"] == 6000.0
    assert product["bom_cost_variance"] == 1000.0


def test_bom_cost_reflects_updated_material_rate(client, test_user):
    """The same P0.1 'no stale requirement' guarantee already proven
    for shortage calculations - this property is computed fresh from
    current Material.average_rate on every fetch, never stored."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Rate Update Sheet", "unit": "Sheets", "opening_stock": "10", "average_rate": "1000.00",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Rate Update Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "2"}],
    }).json()
    assert product["bom_cost"] == 2000.0

    client.put(f"/api/materials/{material['id']}", json={"average_rate": "1800.00"})

    refreshed = client.get(f"/api/products/{product['id']}").json()
    assert refreshed["bom_cost"] == 3600.0
