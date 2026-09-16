"""Catalog domain tests: product cost/margin properties, and
product/rate-card import commit-to-DB persistence. Combines the
former test_products.py, test_product_imports.py and
test_rate_card_imports.py."""
from tests.helpers import _login
from app.platform.security import hash_password
from app.modules.auth.auth import User

# --- test_products.py ---
"""Tests for Product's own cost/margin computed properties - no
dedicated file existed for these despite several already being on the
model (suggested_cost_price, suggested_selling_price, margin,
actual_margin_percent). Focuses on the two added for P0.1 section 2:
bom_cost (what the BOM says material should cost right now,
at real current Material.average_rate prices) and
bom_cost_variance (how far the manually-entered material_cost
has drifted from that)."""

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

# --- test_product_imports.py ---
"""Product import - commit-to-DB persistence chain. Previously
untested: product-imports/commit had only ever been proven to return
HTTP 200, never proven to actually write to the database. Mirrors
test_inventory_import.py's pattern for the Purchase/Material
importers - re-fetch via a separate client.get() call, which the
app's per-request session override makes a genuine fresh-session
read-back, not just trusting the commit response body."""

def test_product_import_commit_creates_real_persisted_product(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/product-imports/commit", json={"rows": [{
        "name": "Product Import Commit Test Product", "product_type": "standard",
        "unit": "Nos", "cost_price": "5000.00", "selling_price": "7500.00",
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_products"] == 1
    assert body["error"] is None
    new_id = body["product_ids"][0]

    persisted = client.get(f"/api/products/{new_id}").json()
    assert persisted["name"] == "Product Import Commit Test Product"
    assert float(persisted["cost_price"]) == 5000.0
    assert float(persisted["selling_price"]) == 7500.0


def test_product_import_commit_reuses_matched_product_without_duplicating(client, test_user):
    _login(client, test_user)
    existing = client.post("/api/products/", json={
        "name": "Product Import Match Test Product", "product_type": "standard", "unit": "Nos",
    }).json()

    resp = client.post("/api/product-imports/commit", json={"rows": [{
        "name": "Product Import Match Test Product", "unit": "Nos",
        "matched_product_id": existing["id"],
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_products"] == 0
    assert body["matched_existing"] == 1

    all_matching = client.get("/api/products/", params={"search": "Product Import Match Test Product"}).json()
    assert len(all_matching) == 1


def test_product_import_commit_requires_master(client, db_session):
    employee = User(
        username="prodimportuser", email="prodimportuser@example.com", full_name="Product Import User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "prodimportuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/product-imports/commit", json={"rows": [{"name": "Unauthorized Product", "unit": "Nos"}]})
    assert resp.status_code == 403


def test_product_import_template_requires_master(client, db_session):
    employee = User(
        username="prodtemplateuser", email="prodtemplateuser@example.com", full_name="Product Template User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "prodtemplateuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.get("/api/product-imports/template")
    assert resp.status_code == 403


def test_product_import_template_unauthenticated_rejected(client):
    resp = client.get("/api/product-imports/template")
    assert resp.status_code in (401, 403)

# --- test_rate_card_imports.py ---
"""Rate card import - commit-to-DB persistence chain. Previously
untested: rate-card-imports/commit had only ever been proven to
return HTTP 200, never proven to actually write a real RateCard row
to the database, or that an update genuinely follows the
create-new-version discipline (deactivate old, create new
superseding row) rather than mutating history in place. Mirrors
test_inventory_import.py's pattern - re-fetch via a separate
client.get() call, which the app's per-request session override
makes a genuine fresh-session read-back, not just trusting the
commit response body."""

def _valid_row(**overrides):
    row = {
        "category": "Material", "item_name": "Rate Import Test Item", "uom": "Sheet",
        "woodful_selling_rate": "1500.00", "source_type": "MANUAL_VERIFIED", "confidence": "HIGH",
    }
    row.update(overrides)
    return row


def test_rate_card_import_commit_creates_real_persisted_rate(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/rate-card-imports/commit", json={"rows": [_valid_row()]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["error"] is None
    rate_id = body["rate_ids"][0]

    persisted = client.get(f"/api/rate-cards/{rate_id}").json()
    assert persisted["item_name"] == "Rate Import Test Item"
    assert float(persisted["woodful_selling_rate"]) == 1500.0
    assert persisted["is_active"] is True


def test_rate_card_import_commit_update_deactivates_old_and_creates_new(client, test_user):
    """An update must never mutate the matched row's price fields in
    place - it deactivates that row and creates a new one that
    supersedes it, preserving rate history."""
    _login(client, test_user)
    first = client.post("/api/rate-card-imports/commit", json={"rows": [_valid_row(item_name="Rate Import Update Test Item")]})
    original_id = first.json()["rate_ids"][0]

    second = client.post("/api/rate-card-imports/commit", json={"rows": [_valid_row(
        item_name="Rate Import Update Test Item", woodful_selling_rate="1800.00", matched_rate_id=original_id,
    )]})
    assert second.status_code == 200
    body = second.json()
    assert body["updated"] == 1
    new_id = body["rate_ids"][0]
    assert new_id != original_id

    old_persisted = client.get(f"/api/rate-cards/{original_id}").json()
    assert old_persisted["is_active"] is False
    assert float(old_persisted["woodful_selling_rate"]) == 1500.0  # history preserved, not mutated

    new_persisted = client.get(f"/api/rate-cards/{new_id}").json()
    assert new_persisted["is_active"] is True
    assert float(new_persisted["woodful_selling_rate"]) == 1800.0
    assert new_persisted["supersedes_id"] == original_id


def test_rate_card_import_commit_requires_master(client, db_session):
    employee = User(
        username="rateimportuser", email="rateimportuser@example.com", full_name="Rate Import User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "rateimportuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/rate-card-imports/commit", json={"rows": [_valid_row()]})
    assert resp.status_code == 403
