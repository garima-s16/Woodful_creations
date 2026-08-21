"""Tests for Material.is_active and the dashboard's recent stock
movement feed - both gaps found during this turn's audit."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_material_defaults_to_active(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/materials/", json={
        "name": "Default Active Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    })
    assert resp.status_code == 201
    assert resp.json()["is_active"] is True


def test_material_can_be_deactivated_and_reactivated(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Deactivate Test Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()

    resp = client.put(f"/api/materials/{material['id']}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    resp2 = client.put(f"/api/materials/{material['id']}", json={"is_active": True})
    assert resp2.json()["is_active"] is True


def test_active_only_filter_excludes_inactive_materials(client, test_user):
    _login(client, test_user)
    active_material = client.post("/api/materials/", json={
        "name": "Active Only Filter Material A", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    inactive_material = client.post("/api/materials/", json={
        "name": "Active Only Filter Material B", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    client.put(f"/api/materials/{inactive_material['id']}", json={"is_active": False})

    filtered = client.get("/api/materials/", params={"active_only": True}).json()
    ids = [m["id"] for m in filtered]
    assert active_material["id"] in ids
    assert inactive_material["id"] not in ids


def test_default_material_list_still_includes_inactive_materials(client, test_user):
    """Backward compatibility - omitting active_only must behave
    exactly as before this field existed."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Unfiltered List Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    client.put(f"/api/materials/{material['id']}", json={"is_active": False})

    unfiltered = client.get("/api/materials/").json()
    assert any(m["id"] == material["id"] for m in unfiltered)


def test_recent_stock_movement_includes_purchases_and_issues(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Movement Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Movement Test Material", "unit": "Sheets", "opening_stock": "20", "minimum_stock": "1",
    }).json()

    client.post("/api/purchases/", json={
        "date": "2026-08-16T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })
    client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "5", "unit": "Sheets",
    })

    resp = client.get("/api/dashboard/stock")
    assert resp.status_code == 200
    movement = resp.json()["recent_stock_movement"]
    assert any(row["type"] == "IN" and row["material"] == "Movement Test Material" for row in movement)
    assert any(row["type"] == "OUT" and row["material"] == "Movement Test Material" for row in movement)


def test_recent_stock_movement_is_not_hardcoded(client, test_user):
    """The brief's explicit requirement - must reflect actual seeded
    transactions, not a fixed/fabricated list."""
    _login(client, test_user)
    before = client.get("/api/dashboard/stock").json()["recent_stock_movement"]

    supplier = client.post("/api/suppliers/", json={"name": "Not Hardcoded Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Not Hardcoded Movement Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-16T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "3", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })

    after = client.get("/api/dashboard/stock").json()["recent_stock_movement"]
    assert after != before
    assert any(row["material"] == "Not Hardcoded Movement Material" for row in after)
