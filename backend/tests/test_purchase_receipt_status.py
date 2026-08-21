"""Tests for Purchase.receipt_status - stock must only increase on
actual receipt, never merely on placing an order. Also confirms the
default ("Received") behaves exactly as purchases always have."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_default_purchase_still_increases_stock_immediately(client, test_user):
    """Backward compatibility - omitting receipt_status must behave
    exactly as every purchase always has."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Default Receipt Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Default Receipt Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/purchases/", json={
        "date": "2026-08-15T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })
    assert resp.status_code == 201
    assert resp.json()["receipt_status"] == "Received"

    updated = client.get(f"/api/materials/{material['id']}").json()
    assert updated["current_stock"] == 15  # 5 opening + 10 immediately received


def test_ordered_purchase_does_not_increase_stock(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Ordered Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Ordered Test Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/purchases/", json={
        "date": "2026-08-15T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
        "receipt_status": "Ordered",
    })
    assert resp.status_code == 201
    assert resp.json()["receipt_status"] == "Ordered"

    unchanged = client.get(f"/api/materials/{material['id']}").json()
    assert unchanged["current_stock"] == 5  # unchanged - nothing has arrived yet


def test_marking_received_now_increases_stock(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Mark Received Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Mark Received Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1,
    }).json()
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-15T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
        "receipt_status": "Ordered",
    }).json()

    resp = client.post(f"/api/purchases/{purchase['id']}/receive")
    assert resp.status_code == 200
    assert resp.json()["receipt_status"] == "Received"

    updated = client.get(f"/api/materials/{material['id']}").json()
    assert updated["current_stock"] == 15  # 5 + 10, applied now


def test_cannot_receive_the_same_purchase_twice(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Double Receive Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Double Receive Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-15T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
        "receipt_status": "Ordered",
    }).json()

    first = client.post(f"/api/purchases/{purchase['id']}/receive")
    assert first.status_code == 200
    second = client.post(f"/api/purchases/{purchase['id']}/receive")
    assert second.status_code == 400

    # Confirm stock was only applied once, not twice.
    updated = client.get(f"/api/materials/{material['id']}").json()
    assert updated["current_stock"] == 10


def test_receiving_an_already_received_purchase_directly_also_rejected(client, test_user):
    """A purchase created as Received (the default) should also reject
    a /receive call - it's already done."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Already Received Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Already Received Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-15T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    }).json()

    resp = client.post(f"/api/purchases/{purchase['id']}/receive")
    assert resp.status_code == 400


def test_no_purchase_received_notification_for_ordered_status(client, test_user):
    """The PURCHASE_RECEIVED notification must only fire when stock
    actually changes, not merely when a purchase is placed as Ordered."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Notif Ordered Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Notif Ordered Material", "unit": "Sheets", "opening_stock": 100, "minimum_stock": 1,
    }).json()

    client.post("/api/purchases/", json={
        "date": "2026-08-15T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
        "receipt_status": "Ordered",
    })

    notifications = client.get("/api/notifications/").json()
    matches = [n for n in notifications if n["notification_type"] == "PURCHASE_RECEIVED"
               and "Notif Ordered Material" in n["title"]]
    assert len(matches) == 0


def test_receive_requires_master_or_manager(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Receive Perm Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Receive Perm Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-15T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
        "receipt_status": "Ordered",
    }).json()

    employee = client.post("/api/employees/", json={
        "name": "Receive Perm Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    limited_user = User(
        username="receivepermuser", email="receivepermuser@example.com", full_name="Limited User",
        password_hash=hash_password("LimitedPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(limited_user)
    db_session.commit()

    client.post("/api/auth/login", json={"identifier": "receivepermuser@example.com", "password": "LimitedPass1!"})
    resp = client.post(f"/api/purchases/{purchase['id']}/receive")
    assert resp.status_code == 403
