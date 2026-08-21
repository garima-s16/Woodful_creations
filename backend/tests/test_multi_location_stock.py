"""Focused tests for TRUE MULTI-LOCATION STOCK (Family 5's explicitly
flagged known remaining gap). Confirms per-location balances are
genuinely DERIVED from the existing StockLedgerEntry ledger - never a
second, independently maintained number - and that the material-wide
total always equals the sum of its location balances."""
from decimal import Decimal


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _make_locations(client):
    warehouse = client.post("/api/locations/", json={"name": "ML Warehouse"}).json()
    rack_a = client.post("/api/locations/", json={"name": "ML Rack A2", "parent_id": warehouse["id"]}).json()
    rack_b = client.post("/api/locations/", json={"name": "ML Rack B1", "parent_id": warehouse["id"]}).json()
    return rack_a, rack_b


def _location_stock(client, material_id):
    resp = client.get(f"/api/stock/locations/{material_id}")
    assert resp.status_code == 200
    return resp.json()


def test_receipt_into_two_different_locations(client, test_user):
    _login(client, test_user)
    rack_a, rack_b = _make_locations(client)
    material = client.post("/api/materials/", json={
        "name": "HDHMR 18mm Multi-Loc", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "ML Supplier"}).json()["id"]

    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "12", "unit": "Sheets", "rate": "500", "gst_percent": "18",
        "location_id": rack_a["id"],
    })
    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "6", "unit": "Sheets", "rate": "500", "gst_percent": "18",
        "location_id": rack_b["id"],
    })

    breakdown = _location_stock(client, material["id"])
    by_id = {row["location_id"]: Decimal(str(row["quantity"])) for row in breakdown["locations"]}
    assert by_id[rack_a["id"]] == Decimal("12")
    assert by_id[rack_b["id"]] == Decimal("6")
    assert Decimal(str(breakdown["total"])) == Decimal("18")
    assert sum(by_id.values()) == Decimal(str(breakdown["total"]))

    material_after = client.get(f"/api/materials/{material['id']}").json()
    assert Decimal(str(material_after["current_stock"])) == Decimal("18")


def test_issue_from_specific_location(client, test_user):
    _login(client, test_user)
    rack_a, rack_b = _make_locations(client)
    material = client.post("/api/materials/", json={
        "name": "Issue Multi-Loc Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "Issue ML Supplier"}).json()["id"]
    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "100", "gst_percent": "0", "location_id": rack_a["id"],
    })
    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "100", "gst_percent": "0", "location_id": rack_b["id"],
    })

    resp = client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "4",
        "unit": "Sheets", "location_id": rack_a["id"],
    })
    assert resp.status_code == 201

    breakdown = _location_stock(client, material["id"])
    by_id = {row["location_id"]: Decimal(str(row["quantity"])) for row in breakdown["locations"]}
    assert by_id[rack_a["id"]] == Decimal("6")
    assert by_id[rack_b["id"]] == Decimal("10")
    assert Decimal(str(breakdown["total"])) == Decimal("16")


def test_issue_cannot_exceed_specific_location_balance(client, test_user):
    _login(client, test_user)
    rack_a, rack_b = _make_locations(client)
    material = client.post("/api/materials/", json={
        "name": "Issue Overdraw Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "Overdraw Supplier"}).json()["id"]
    # Plenty of material-wide stock, but only at rack_b - rack_a has none.
    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "50", "unit": "Sheets", "rate": "100", "gst_percent": "0", "location_id": rack_b["id"],
    })

    resp = client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "5",
        "unit": "Sheets", "location_id": rack_a["id"],
    })
    assert resp.status_code == 400


def test_transfer_moves_quantity_between_locations(client, test_user):
    _login(client, test_user)
    rack_a, rack_b = _make_locations(client)
    material = client.post("/api/materials/", json={
        "name": "Transfer Ledger Multi-Loc", "unit": "Sheets", "opening_stock": 20, "minimum_stock": 1,
        "location_id": rack_a["id"],
    }).json()

    resp = client.post("/api/stock/transfers", json={
        "material_id": material["id"], "quantity": "8", "to_location_id": rack_b["id"],
    })
    assert resp.status_code == 201

    breakdown = _location_stock(client, material["id"])
    by_id = {row["location_id"]: Decimal(str(row["quantity"])) for row in breakdown["locations"]}
    assert by_id[rack_a["id"]] == Decimal("12")
    assert by_id[rack_b["id"]] == Decimal("8")
    assert Decimal(str(breakdown["total"])) == Decimal("20")

    # Total stock is unaffected by a transfer - reconciliation must still pass.
    verify = client.get(f"/api/stock/verify/{material['id']}").json()
    assert verify["matches"] is True


def test_adjustment_at_specific_location(client, test_user):
    _login(client, test_user)
    rack_a, rack_b = _make_locations(client)
    material = client.post("/api/materials/", json={
        "name": "Adjustment Multi-Loc Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "Adj ML Supplier"}).json()["id"]
    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "100", "gst_percent": "0", "location_id": rack_a["id"],
    })

    resp = client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Damage", "quantity_delta": "-2",
        "reason": "Water damage at rack A2", "location_id": rack_a["id"],
    })
    assert resp.status_code == 201

    breakdown = _location_stock(client, material["id"])
    by_id = {row["location_id"]: Decimal(str(row["quantity"])) for row in breakdown["locations"]}
    assert by_id[rack_a["id"]] == Decimal("8")
    assert Decimal(str(breakdown["total"])) == Decimal("8")


def test_location_totals_and_reconciliation_after_mixed_activity(client, test_user):
    """receipt A, receipt B, issue from A, transfer A->B, adjustment at B -
    location totals must sum to the material-wide total at every step."""
    _login(client, test_user)
    rack_a, rack_b = _make_locations(client)
    material = client.post("/api/materials/", json={
        "name": "Mixed Activity Multi-Loc", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "Mixed Supplier"}).json()["id"]

    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "20", "unit": "Sheets", "rate": "100", "gst_percent": "0", "location_id": rack_a["id"],
    })
    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "100", "gst_percent": "0", "location_id": rack_b["id"],
    })
    # A: 20, B: 10, total 30
    client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "5",
        "unit": "Sheets", "location_id": rack_a["id"],
    })
    # A: 15, B: 10, total 25
    client.post("/api/stock/transfers", json={
        "material_id": material["id"], "quantity": "5", "from_location_id": rack_a["id"],
        "to_location_id": rack_b["id"],
    })
    # A: 10, B: 15, total 25
    client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Physical Count Increase", "quantity_delta": "3",
        "reason": "Recount at B1", "location_id": rack_b["id"],
    })
    # A: 10, B: 18, total 28

    breakdown = _location_stock(client, material["id"])
    by_id = {row["location_id"]: Decimal(str(row["quantity"])) for row in breakdown["locations"]}
    assert by_id[rack_a["id"]] == Decimal("10")
    assert by_id[rack_b["id"]] == Decimal("18")
    assert Decimal(str(breakdown["total"])) == Decimal("28")
    assert sum(by_id.values()) == Decimal(str(breakdown["total"]))

    material_after = client.get(f"/api/materials/{material['id']}").json()
    assert Decimal(str(material_after["current_stock"])) == Decimal("28")

    verify = client.get(f"/api/stock/verify/{material['id']}").json()
    assert verify["matches"] is True


def test_existing_stock_ledger_verification_still_works_with_locations(client, test_user):
    """Existing verify_stock_matches_ledger reconciliation must keep
    working exactly as before now that ledger entries carry location_id -
    a regression here would mean multi-location broke the ledger's
    original guarantee."""
    _login(client, test_user)
    rack_a, _ = _make_locations(client)
    material = client.post("/api/materials/", json={
        "name": "Verify Still Works Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "Verify Supplier"}).json()["id"]
    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "100", "gst_percent": "0", "location_id": rack_a["id"],
    })

    verify = client.get(f"/api/stock/verify/{material['id']}").json()
    assert verify["matches"] is True
    assert float(verify["current_stock"]) == 15.0


def test_no_location_falls_back_to_material_primary_location(client, test_user):
    """A material with no explicit location on receipt still shows up
    somewhere sensible in the per-location breakdown - never silently
    dropped from the total."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "No Location Material", "unit": "Sheets", "opening_stock": "7", "minimum_stock": "1",
    }).json()

    breakdown = _location_stock(client, material["id"])
    assert Decimal(str(breakdown["total"])) == Decimal("7")
    total_located = sum(Decimal(str(row["quantity"])) for row in breakdown["locations"])
    assert total_located == Decimal("7")
