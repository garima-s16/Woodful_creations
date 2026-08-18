"""Tests proving decimal stock quantities genuinely survive end-to-end -
Section 3.5's explicit requirement that materials measured in kg/
litres/metres must never be silently rounded via int(quantity)."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_material_can_be_created_with_decimal_opening_stock(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/materials/", json={
        "name": "Decimal Opening Stock Adhesive", "unit": "Kg", "opening_stock": "2.5", "minimum_stock": "1.5",
    })
    assert resp.status_code == 201
    assert float(resp.json()["current_stock"]) == 2.5
    assert float(resp.json()["minimum_stock"]) == 1.5


def test_purchase_of_decimal_quantity_does_not_truncate_stock(client, test_user):
    """The exact scenario the brief names: 2.5 kg of adhesive must
    remain 2.5, never silently become 2."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Decimal Purchase Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Decimal Purchase Adhesive", "unit": "Kg", "opening_stock": "0", "minimum_stock": "1",
    }).json()

    client.post("/api/purchases/", json={
        "date": "2026-08-15T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "2.5", "unit": "Kg", "rate": "200.00", "gst_percent": "18", "payment_status": "Paid",
    })

    updated = client.get(f"/api/materials/{material['id']}").json()
    assert float(updated["current_stock"]) == 2.5
    assert float(updated["total_purchased"]) == 2.5


def test_multiple_decimal_purchases_accumulate_precisely(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Multi Decimal Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Multi Decimal Material", "unit": "Litres", "opening_stock": "0", "minimum_stock": "1",
    }).json()

    for qty in ["1.25", "0.75", "2.5"]:
        client.post("/api/purchases/", json={
            "date": "2026-08-15T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
            "quantity": qty, "unit": "Litres", "rate": "100.00", "gst_percent": "18", "payment_status": "Paid",
        })

    updated = client.get(f"/api/materials/{material['id']}").json()
    assert float(updated["current_stock"]) == 4.5  # 1.25 + 0.75 + 2.5


def test_issuing_decimal_quantity_does_not_truncate_stock(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Decimal Issue Material", "unit": "Metres", "opening_stock": "10", "minimum_stock": "1",
    }).json()

    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "material_id": material["id"],
        "quantity_issued": "3.75", "unit": "Metres",
    })

    updated = client.get(f"/api/materials/{material['id']}").json()
    assert float(updated["current_stock"]) == 6.25  # 10 - 3.75
    assert float(updated["total_issued"]) == 3.75


def test_cannot_issue_more_than_available_decimal_stock(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Decimal Overissue Material", "unit": "Kg", "opening_stock": "2.5", "minimum_stock": "1",
    }).json()

    resp = client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "material_id": material["id"],
        "quantity_issued": "3.0", "unit": "Kg",
    })
    assert resp.status_code == 400


def test_stock_transfer_preserves_decimal_quantity(client, test_user):
    _login(client, test_user)
    location = client.post("/api/locations/", json={"name": "Decimal Transfer Location"}).json()
    material = client.post("/api/materials/", json={
        "name": "Decimal Transfer Material", "unit": "Kg", "opening_stock": "5.5", "minimum_stock": "1",
    }).json()

    resp = client.post("/api/stock/transfers", json={
        "material_id": material["id"], "quantity": "2.25", "to_location_id": location["id"],
    })
    assert resp.status_code == 201
    assert float(resp.json()["quantity"]) == 2.25


def test_stock_adjustment_preserves_decimal_quantity(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Decimal Adjustment Material", "unit": "Kg", "opening_stock": "5.5", "minimum_stock": "1",
    }).json()

    resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Physical Count Increase",
        "quantity_delta": "0.75", "reason": "Recount found extra fractional stock",
    })
    assert resp.status_code == 201
    assert float(resp.json()["stock_before"]) == 5.5
    assert float(resp.json()["stock_after"]) == 6.25


def test_negative_decimal_adjustment_error_message_does_not_crash(client, test_user):
    """The exact bug that was caught and fixed - a decimal
    quantity_delta through the :+d format specifier used to raise
    ValueError instead of returning a proper 400."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Negative Decimal Guard Material", "unit": "Kg", "opening_stock": "1.5", "minimum_stock": "1",
    }).json()

    resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Damage",
        "quantity_delta": "-2.5", "reason": "Water damage",
    })
    assert resp.status_code == 400  # not 500 - the format string must not crash
    assert "2.5" in resp.json()["detail"]
