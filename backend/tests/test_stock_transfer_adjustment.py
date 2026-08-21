def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_transfer_moves_material_location(client, test_user):
    _login(client, test_user)
    warehouse = client.post("/api/locations/", json={"name": "Transfer Test Warehouse"}).json()
    rack_a = client.post("/api/locations/", json={"name": "Rack A", "parent_id": warehouse["id"]}).json()
    rack_b = client.post("/api/locations/", json={"name": "Rack B", "parent_id": warehouse["id"]}).json()
    material = client.post("/api/materials/", json={
        "name": "Transfer Test Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
        "location_id": rack_a["id"],
    }).json()

    resp = client.post("/api/stock/transfers", json={
        "material_id": material["id"], "quantity": 5, "to_location_id": rack_b["id"],
    })
    assert resp.status_code == 201
    assert resp.json()["from_location_id"] == rack_a["id"]
    assert resp.json()["to_location_id"] == rack_b["id"]

    updated = client.get(f"/api/materials/{material['id']}").json()
    assert updated["location_id"] == rack_b["id"]
    assert "Rack B" in updated["location"]


def test_cannot_transfer_more_than_available_stock(client, test_user):
    _login(client, test_user)
    location = client.post("/api/locations/", json={"name": "Overtransfer Test Location"}).json()
    material = client.post("/api/materials/", json={
        "name": "Overtransfer Test Material", "unit": "Sheets", "opening_stock": 3, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/stock/transfers", json={
        "material_id": material["id"], "quantity": 10, "to_location_id": location["id"],
    })
    assert resp.status_code == 400


def test_adjustment_increases_stock_with_correct_before_after(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Adjustment Increase Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Physical Count Increase",
        "quantity_delta": 3, "reason": "Recount found extra sheets",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["stock_before"] == 10
    assert body["stock_after"] == 13

    updated = client.get(f"/api/materials/{material['id']}").json()
    assert updated["current_stock"] == 13


def test_adjustment_cannot_take_stock_negative(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Negative Guard Material", "unit": "Sheets", "opening_stock": 2, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Damage",
        "quantity_delta": -5, "reason": "Water damage in storage",
    })
    assert resp.status_code == 400

    unchanged = client.get(f"/api/materials/{material['id']}").json()
    assert unchanged["current_stock"] == 2


def test_adjustment_decrease_for_damage_works(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Damage Adjustment Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Damage",
        "quantity_delta": -2, "reason": "Two sheets damaged in transit",
    })
    assert resp.status_code == 201
    assert resp.json()["stock_after"] == 8


def test_transfer_and_adjustment_require_master_or_manager(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Stock Perm Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Perm Test Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
    }).json()
    location = client.post("/api/locations/", json={"name": "Perm Test Location"}).json()
    limited_user = User(
        username="stockpermuser", email="stockpermuser@example.com", full_name="Limited Stock User",
        password_hash=hash_password("LimitedPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(limited_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "stockpermuser@example.com", "password": "LimitedPass1!"})
    assert resp.status_code == 200

    transfer_resp = client.post("/api/stock/transfers", json={
        "material_id": material["id"], "quantity": 1, "to_location_id": location["id"],
    })
    assert transfer_resp.status_code == 403

    adjustment_resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Correction", "quantity_delta": 1, "reason": "Test",
    })
    assert adjustment_resp.status_code == 403


def test_material_still_gets_business_id_on_transfer_and_adjustment(client, test_user):
    _login(client, test_user)
    location = client.post("/api/locations/", json={"name": "Business ID Test Location"}).json()
    material = client.post("/api/materials/", json={
        "name": "Business ID Stock Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1,
    }).json()

    transfer = client.post("/api/stock/transfers", json={
        "material_id": material["id"], "quantity": 1, "to_location_id": location["id"],
    }).json()
    assert len(transfer["business_id"]) == 10

    adjustment = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Correction", "quantity_delta": 1, "reason": "Test",
    }).json()
    assert len(adjustment["business_id"]) == 10
