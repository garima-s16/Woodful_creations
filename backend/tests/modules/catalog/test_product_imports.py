"""Product import - commit-to-DB persistence chain. Previously
untested: product-imports/commit had only ever been proven to return
HTTP 200, never proven to actually write to the database. Mirrors
test_inventory_import.py's pattern for the Purchase/Material
importers - re-fetch via a separate client.get() call, which the
app's per-request session override makes a genuine fresh-session
read-back, not just trusting the commit response body."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


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
