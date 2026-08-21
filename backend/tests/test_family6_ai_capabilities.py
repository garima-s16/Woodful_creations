"""Tests for Family 6's explicitly-named AI capabilities: identify
delayed deliveries (using the new expected_delivery_date field) and
summarize suppliers."""
from datetime import datetime, timedelta


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_delayed_delivery_identified(client, test_user):
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "Delayed Delivery Test Supplier"}).json()["id"]
    material = client.post("/api/materials/", json={
        "name": "Delayed Delivery Test Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    past_date = (datetime.utcnow() - timedelta(days=3)).strftime("%Y-%m-%dT00:00:00")
    client.post("/api/purchases/", json={
        "date": "2026-08-10T00:00:00", "expected_delivery_date": past_date, "supplier_id": supplier_id,
        "material_id": material["id"], "quantity": "10", "unit": "Sheets", "rate": "500",
        "gst_percent": "18", "receipt_status": "Ordered",
    })

    resp = client.post("/api/chat/", json={"message": "show delayed deliveries"})
    assert resp.status_code == 200
    assert "1 delivery overdue" in resp.json()["response"]


def test_purchase_with_no_expected_date_not_counted_as_delayed(client, test_user):
    """Honest AI behavior - a purchase never given a delivery
    expectation must not be claimed as delayed."""
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "No Expected Date Test Supplier"}).json()["id"]
    material = client.post("/api/materials/", json={
        "name": "No Expected Date Test Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-10T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500", "gst_percent": "18", "receipt_status": "Ordered",
    })

    resp = client.post("/api/chat/", json={"message": "any delayed deliveries"})
    assert resp.status_code == 200
    assert "no deliveries" in resp.json()["response"].lower()


def test_delayed_deliveries_requires_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Delayed Delivery Permission Employee"}).json()
    user = User(
        username="delayeddeliverypermuser", email="delayeddeliverypermuser@example.com",
        full_name="Delayed Delivery Perm User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "delayeddeliverypermuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": "delayed deliveries"})
    assert "master account" in resp.json()["response"].lower()


def test_summarize_supplier_via_prefix_phrasing(client, test_user):
    _login(client, test_user)
    client.post("/api/suppliers/", json={"name": "Century Plywood Dealer"})
    resp = client.post("/api/chat/", json={"message": "summarize supplier century plywood dealer"})
    assert resp.status_code == 200
    assert "Century Plywood Dealer" in resp.json()["response"]


def test_summarize_supplier_via_suffix_phrasing(client, test_user):
    """Regression guard for the real bug caught while building this -
    the "X supplier summary" phrasing must extract the supplier name,
    not the literal word "summary"."""
    _login(client, test_user)
    client.post("/api/suppliers/", json={"name": "Greenpanel Distributor"})
    resp = client.post("/api/chat/", json={"message": "greenpanel distributor supplier summary"})
    assert resp.status_code == 200
    assert "Greenpanel Distributor" in resp.json()["response"]


def test_summarize_supplier_shows_financials_for_master_only(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "Financial Redaction Test Supplier"}).json()["id"]
    material = client.post("/api/materials/", json={
        "name": "Supplier Summary Financial Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-10T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "1000", "gst_percent": "18",
    })
    master_resp = client.post("/api/chat/", json={"message": "summarize supplier financial redaction test supplier"})
    assert "Rs" in master_resp.json()["response"]

    employee = client.post("/api/employees/", json={"name": "Supplier Summary RBAC Employee"}).json()
    user = User(
        username="suppliersummaryrbacuser", email="suppliersummaryrbacuser@example.com",
        full_name="Supplier Summary RBAC User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "suppliersummaryrbacuser@example.com", "password": "EmpPass1!"})
    employee_resp = client.post("/api/chat/", json={"message": "summarize supplier financial redaction test supplier"})
    assert "Rs" not in employee_resp.json()["response"]
