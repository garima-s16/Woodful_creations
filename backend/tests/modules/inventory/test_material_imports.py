"""Material import - commit-to-DB persistence chain. Previously
untested: material-imports/commit had only ever been proven to return
HTTP 200, never proven to actually write to the database. Mirrors
test_inventory_import.py's (the Purchase importer's) pattern -
re-fetch via a separate client.get() call, which the app's
per-request session override makes a genuine fresh-session
read-back, not just trusting the commit response body.

A sibling of test_product_imports.py/test_order_imports.py/
test_estimate_imports.py/test_rate_card_imports.py/
test_holiday_imports.py - one file per import domain, matching each
domain's own route module. Previously misplaced inside
test_inventory_import.py (the Purchase importer's file) - material-
imports and purchase-imports are two distinct route modules even
though both are inventory-adjacent."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def test_material_import_commit_creates_real_persisted_material(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Material Import Commit Supplier"}).json()

    resp = client.post("/api/material-imports/commit", json={"rows": [{
        "name": "Material Import Commit Test Material", "unit": "Sheets",
        "supplier_id": supplier["id"], "opening_stock": "12", "minimum_stock": "2",
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_materials"] == 1
    assert body["error"] is None
    new_id = body["material_ids"][0]

    persisted = client.get(f"/api/materials/{new_id}").json()
    assert persisted["name"] == "Material Import Commit Test Material"
    assert persisted["current_stock"] == 12.0
    assert persisted["minimum_stock"] == 2.0
    assert persisted["supplier_id"] == supplier["id"]


def test_material_import_commit_reuses_matched_material_without_duplicating(client, test_user):
    _login(client, test_user)
    existing = client.post("/api/materials/", json={
        "name": "Material Import Match Test Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/material-imports/commit", json={"rows": [{
        "name": "Material Import Match Test Material", "unit": "Sheets",
        "matched_material_id": existing["id"],
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_materials"] == 0
    assert body["matched_existing"] == 1

    all_matching = client.get("/api/materials/", params={"search": "Material Import Match Test Material"}).json()
    assert len(all_matching) == 1  # no duplicate created


def test_material_import_commit_requires_master(client, db_session):
    employee = User(
        username="matimportuser", email="matimportuser@example.com", full_name="Material Import User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "matimportuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/material-imports/commit", json={"rows": [{"name": "Unauthorized Material", "unit": "Sheets"}]})
    assert resp.status_code == 403


def test_material_import_template_requires_master(client, db_session):
    employee = User(
        username="mattemplateuser", email="mattemplateuser@example.com", full_name="Material Template User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "mattemplateuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.get("/api/material-imports/template")
    assert resp.status_code == 403


def test_material_import_template_unauthenticated_rejected(client):
    resp = client.get("/api/material-imports/template")
    assert resp.status_code in (401, 403)
