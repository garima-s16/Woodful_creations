"""Tests for the delete-endpoint chain closed this turn - Material and
Supplier delete existed on the backend but were never called from any
frontend page, and neither guarded against deleting a record with real
transaction history (which would have raised an unhandled FK-
constraint error once exposed through the UI)."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_master_can_delete_unreferenced_material(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Delete Guard Unreferenced Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    resp = client.delete(f"/api/materials/{material['id']}")
    assert resp.status_code == 204


def test_cannot_delete_material_with_purchase_history(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Delete Guard Purchase Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Delete Guard Purchased Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-17T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })

    resp = client.delete(f"/api/materials/{material['id']}")
    assert resp.status_code == 400
    assert "purchase history" in resp.json()["detail"].lower()


def test_cannot_delete_material_with_issue_history(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Delete Guard Issued Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-17T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })

    resp = client.delete(f"/api/materials/{material['id']}")
    assert resp.status_code == 400
    assert "issue history" in resp.json()["detail"].lower()


def test_master_can_delete_unreferenced_supplier(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Delete Guard Unreferenced Supplier"}).json()
    resp = client.delete(f"/api/suppliers/{supplier['id']}")
    assert resp.status_code == 204


def test_cannot_delete_supplier_with_purchase_history(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Delete Guard Referenced Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Delete Guard Supplier Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-17T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "3", "unit": "Sheets", "rate": "400.00", "gst_percent": "18", "payment_status": "Paid",
    })

    resp = client.delete(f"/api/suppliers/{supplier['id']}")
    assert resp.status_code == 400
    assert "purchase history" in resp.json()["detail"].lower()


def test_cannot_delete_supplier_with_material_link(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Delete Guard Linked Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Delete Guard Linked Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "100.00",
    })

    resp = client.delete(f"/api/suppliers/{supplier['id']}")
    assert resp.status_code == 400
    assert "linked to materials" in resp.json()["detail"].lower()


def test_material_delete_is_strictly_master_only(client, test_user, db_session):
    """require_role("master") - any non-master role must be rejected,
    not just an obviously-unprivileged account."""
    from app.core.security import hash_password
    from app.models.user import User

    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Delete Guard Non-Master Test Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    non_master = User(
        username="deleteguarduser", email="deleteguarduser@example.com", full_name="Delete Guard User",
        password_hash=hash_password("UserPass1!"), role="user", is_active=True,
    )
    db_session.add(non_master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "deleteguarduser@example.com", "password": "UserPass1!"})

    resp = client.delete(f"/api/materials/{material['id']}")
    assert resp.status_code == 403
