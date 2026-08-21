"""Tests for the stock ledger architecture (Family 5's explicit
"major architectural priority"): every stock-affecting event writes
a permanent, traceable ledger entry, and Material.current_stock
genuinely reconciles with opening_stock + the full ledger at every
step - not merely claimed, actually verified via
verify_stock_matches_ledger after each mutation type and in
combination."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_ledger_reconciles_after_purchase_receipt(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Ledger Purchase Test Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "5",
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "Ledger Purchase Test Supplier"}).json()["id"]
    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "20", "unit": "Sheets", "rate": "500", "gst_percent": "18",
    })

    verify = client.get(f"/api/stock/verify/{material['id']}").json()
    assert verify["matches"] is True
    assert float(verify["current_stock"]) == 30.0  # 10 opening + 20 received
    assert verify["ledger_entry_count"] == 1


def test_ledger_entry_traces_back_to_the_purchase(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Ledger Trace Test Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "Ledger Trace Test Supplier"}).json()["id"]
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "15", "unit": "Sheets", "rate": "500", "gst_percent": "18",
    }).json()

    ledger = client.get("/api/stock/ledger", params={"material_id": material["id"]}).json()
    assert len(ledger) == 1
    assert ledger[0]["entry_type"] == "Receipt"
    assert ledger[0]["reference_type"] == "purchase"
    assert ledger[0]["reference_id"] == purchase["id"]
    assert float(ledger[0]["quantity_delta"]) == 15.0


def test_ledger_reconciles_after_partial_receipt_then_completion(client, test_user):
    """The most complex real path this session built - two separate
    receive calls on the same purchase - must still leave the ledger
    perfectly reconciled."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Ledger Partial Receipt Test Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "Ledger Partial Receipt Test Supplier"}).json()["id"]
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "100", "unit": "Sheets", "rate": "500", "gst_percent": "18", "receipt_status": "Ordered",
    }).json()

    client.post(f"/api/purchases/{purchase['id']}/receive", json={"quantity": "40"})
    client.post(f"/api/purchases/{purchase['id']}/receive", json={"quantity": "60"})

    verify = client.get(f"/api/stock/verify/{material['id']}").json()
    assert verify["matches"] is True
    assert float(verify["current_stock"]) == 100.0
    assert verify["ledger_entry_count"] == 2


def test_ledger_reconciles_after_issue(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Ledger Issue Test Material", "unit": "Sheets", "opening_stock": "50", "minimum_stock": "5",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "12", "unit": "Sheets",
    })

    verify = client.get(f"/api/stock/verify/{material['id']}").json()
    assert verify["matches"] is True
    assert float(verify["current_stock"]) == 38.0


def test_ledger_reconciles_after_adjustment(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Ledger Adjustment Test Material", "unit": "Sheets", "opening_stock": "20", "minimum_stock": "5",
    }).json()
    client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Damage", "quantity_delta": "-3", "reason": "Water damage",
    })

    verify = client.get(f"/api/stock/verify/{material['id']}").json()
    assert verify["matches"] is True
    assert float(verify["current_stock"]) == 17.0


def test_ledger_reconciles_after_full_journey(client, test_user):
    """The complete real journey: opening stock, a purchase receipt,
    an issue, a partial return, and a damage adjustment - the ledger
    must reconcile after every single step, not just individually."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Ledger Full Journey Test Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "5",
    }).json()
    supplier_id = client.post("/api/suppliers/", json={"name": "Ledger Full Journey Test Supplier"}).json()["id"]

    client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "40", "unit": "Sheets", "rate": "500", "gst_percent": "18",
    })
    assert client.get(f"/api/stock/verify/{material['id']}").json()["matches"] is True

    issue = client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "material_id": material["id"], "quantity_issued": "15", "unit": "Sheets",
    }).json()
    assert client.get(f"/api/stock/verify/{material['id']}").json()["matches"] is True

    client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Return from Issue",
        "quantity_delta": "5", "reason": "Unused sheets returned", "related_issue_id": issue["id"],
    })
    verify_after_return = client.get(f"/api/stock/verify/{material['id']}").json()
    assert verify_after_return["matches"] is True

    client.post("/api/stock/adjustments", json={
        "material_id": material["id"], "adjustment_type": "Damage", "quantity_delta": "-2", "reason": "Damaged in storage",
    })
    final = client.get(f"/api/stock/verify/{material['id']}").json()
    assert final["matches"] is True
    # 10 opening + 40 received - 15 issued + 5 returned - 2 damaged = 38
    assert float(final["current_stock"]) == 38.0
    assert final["ledger_entry_count"] == 4
