"""Order import - commit-to-DB persistence chain. Previously
untested: order-imports/commit had only ever been proven to return
HTTP 200, never proven to actually write a real Order (with its
line items and computed totals) to the database. Mirrors
test_inventory_import.py's pattern - re-fetch via a separate
client.get() call, which the app's per-request session override
makes a genuine fresh-session read-back, not just trusting the
commit response body."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def _create_client_and_product(client):
    client_id = client.post("/api/clients/", json={
        "name": "Order Import Test Client", "phone": "9000030001",
    }).json()["id"]
    product_id = client.post("/api/products/", json={
        "name": "Order Import Test Product", "product_type": "standard", "unit": "Nos",
    }).json()["id"]
    return client_id, product_id


def test_order_import_commit_creates_real_persisted_order(client, test_user):
    _login(client, test_user)
    client_id, product_id = _create_client_and_product(client)

    resp = client.post("/api/order-imports/commit", json={"orders": [{
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "tax_percent": "18",
        "items": [{
            "product_id": product_id, "description": "Imported line item",
            "quantity": "2", "unit": "Nos", "rate": "1000.00",
        }],
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 1
    assert body["error_count"] == 0
    order_id = body["results"][0]["order_id"]

    persisted = client.get(f"/api/orders/{order_id}").json()
    assert persisted["client_id"] == client_id
    # 2 * 1000 = 2000 subtotal, +18% tax = 2360
    assert float(persisted["order_value"]) == 2360.0
    assert len(persisted["items"]) == 1
    assert persisted["items"][0]["description"] == "Imported line item"
    assert float(persisted["items"][0]["quantity"]) == 2.0


def test_order_import_commit_rejects_invalid_product_id(client, test_user):
    _login(client, test_user)
    client_id, _ = _create_client_and_product(client)

    resp = client.post("/api/order-imports/commit", json={"orders": [{
        "client_id": client_id, "items": [{
            "product_id": 999999, "description": "Bad product row",
            "quantity": "1", "unit": "Nos", "rate": "500.00",
        }],
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created_count"] == 0
    assert body["error_count"] == 1
    assert "Invalid Product ID" in body["results"][0]["error"]


def test_order_import_commit_requires_master(client, db_session):
    employee = User(
        username="orderimportuser", email="orderimportuser@example.com", full_name="Order Import User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "orderimportuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/order-imports/commit", json={"orders": [{"client_id": 1, "items": []}]})
    assert resp.status_code == 403


def test_order_import_template_requires_master(client, db_session):
    employee = User(
        username="ordertemplateuser", email="ordertemplateuser@example.com", full_name="Order Template User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "ordertemplateuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.get("/api/order-imports/template")
    assert resp.status_code == 403


def test_order_import_template_unauthenticated_rejected(client):
    resp = client.get("/api/order-imports/template")
    assert resp.status_code in (401, 403)
