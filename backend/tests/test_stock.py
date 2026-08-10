def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_supplier(client):
    resp = client.post("/api/suppliers/", json={
        "supplier_code": "SUP-TEST", "name": "Test Supplier", "category": "Plywood",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_material(client, supplier_id):
    resp = client.post("/api/materials/", json={
        "material_code": "MAT-TEST", "name": "Test Ply", "category": "Plywood",
        "unit": "Sheets", "minimum_stock": 10, "average_rate": "1000.00",
        "supplier_id": supplier_id, "opening_stock": 50,
    })
    assert resp.status_code == 201
    return resp.json()


def test_material_starts_at_opening_stock(client, test_user):
    _login(client, test_user)
    supplier_id = _create_supplier(client)
    material = _create_material(client, supplier_id)
    assert material["current_stock"] == 50
    assert material["stock_status"] == "STOCK OK"


def test_purchase_increases_stock(client, test_user):
    _login(client, test_user)
    supplier_id = _create_supplier(client)
    material = _create_material(client, supplier_id)

    resp = client.post("/api/purchases/", json={
        "purchase_code": "PUR-TEST-001", "date": "2026-08-01T00:00:00", "supplier_id": supplier_id,
        "material_id": material["id"], "quantity": "20", "unit": "Sheets", "rate": "1000.00",
        "gst_percent": "18", "payment_status": "Paid",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["taxable_value"]) == 20000.0
    assert float(body["gst_amount"]) == 3600.0
    assert float(body["invoice_total"]) == 23600.0

    mat = client.get(f"/api/materials/{material['id']}").json()
    assert mat["current_stock"] == 70
    assert mat["total_purchased"] == 20


def test_issue_decreases_stock(client, test_user):
    _login(client, test_user)
    supplier_id = _create_supplier(client)
    material = _create_material(client, supplier_id)

    resp = client.post("/api/issues/", json={
        "issue_code": "ISS-TEST-001", "date": "2026-08-01T00:00:00",
        "material_id": material["id"], "quantity_issued": "15", "unit": "Sheets",
        "issued_to": "Ravi", "department": "Assembly",
    })
    assert resp.status_code == 201

    mat = client.get(f"/api/materials/{material['id']}").json()
    assert mat["current_stock"] == 35
    assert mat["total_issued"] == 15


def test_issue_rejects_insufficient_stock(client, test_user):
    _login(client, test_user)
    supplier_id = _create_supplier(client)
    material = _create_material(client, supplier_id)

    resp = client.post("/api/issues/", json={
        "issue_code": "ISS-TEST-002", "date": "2026-08-01T00:00:00",
        "material_id": material["id"], "quantity_issued": "999", "unit": "Sheets",
    })
    assert resp.status_code == 400


def test_low_stock_dashboard_reflects_minimum(client, test_user):
    _login(client, test_user)
    supplier_id = _create_supplier(client)
    material = _create_material(client, supplier_id)

    # Issue down to below minimum_stock (10)
    client.post("/api/issues/", json={
        "issue_code": "ISS-TEST-003", "date": "2026-08-01T00:00:00",
        "material_id": material["id"], "quantity_issued": "45", "unit": "Sheets",
    })

    dashboard = client.get("/api/dashboard/stock").json()
    assert dashboard["low_stock_items"] >= 1
