"""Estimate import - commit-to-DB persistence chain. Previously
untested: estimate-imports/commit had only ever been proven to
return HTTP 200, never proven to actually write a real Estimate
(with its line items and computed totals) to the database. Mirrors
test_inventory_import.py's pattern - re-fetch via a separate
client.get() call, which the app's per-request session override
makes a genuine fresh-session read-back, not just trusting the
commit response body."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def _create_client_and_product(client):
    client_id = client.post("/api/clients/", json={
        "name": "Estimate Import Test Client", "phone": "9000040001",
    }).json()["id"]
    product_id = client.post("/api/products/", json={
        "name": "Estimate Import Test Product", "product_type": "standard", "unit": "Nos",
    }).json()["id"]
    return client_id, product_id


def test_estimate_import_commit_creates_real_persisted_estimate(client, test_user):
    _login(client, test_user)
    client_id, product_id = _create_client_and_product(client)

    resp = client.post("/api/estimate-imports/commit", json={"estimates": [{
        "client_id": client_id, "estimate_date": "2026-08-19T00:00:00", "tax_percent": "18",
        "items": [{
            "product_id": product_id, "description": "Imported estimate line item",
            "quantity": "3", "unit": "Nos", "rate": "1000.00",
        }],
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 1
    assert body["error_count"] == 0
    estimate_id = body["results"][0]["estimate_id"]

    persisted = client.get(f"/api/estimates/{estimate_id}").json()
    assert persisted["client_id"] == client_id
    # 3 * 1000 = 3000 subtotal, +18% tax = 3540
    assert float(persisted["total_cost"]) == 3540.0
    assert len(persisted["line_items"]) == 1
    assert persisted["line_items"][0]["description"] == "Imported estimate line item"
    assert float(persisted["line_items"][0]["quantity"]) == 3.0


def test_estimate_import_commit_rejects_invalid_product_id(client, test_user):
    _login(client, test_user)
    client_id, _ = _create_client_and_product(client)

    resp = client.post("/api/estimate-imports/commit", json={"estimates": [{
        "client_id": client_id, "items": [{
            "product_id": 999999, "description": "Bad product row",
            "quantity": "1", "unit": "Nos", "rate": "500.00",
        }],
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["error_count"] == 1


def test_estimate_import_commit_requires_master(client, db_session):
    employee = User(
        username="estimportuser", email="estimportuser@example.com", full_name="Estimate Import User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "estimportuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/estimate-imports/commit", json={"estimates": [{"client_id": 1, "items": []}]})
    assert resp.status_code == 403


def test_estimate_import_template_requires_master(client, db_session):
    employee = User(
        username="esttemplateuser", email="esttemplateuser@example.com", full_name="Estimate Template User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "esttemplateuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.get("/api/estimate-imports/template")
    assert resp.status_code == 403


def test_estimate_import_template_unauthenticated_rejected(client):
    resp = client.get("/api/estimate-imports/template")
    assert resp.status_code in (401, 403)
