"""Tests for Family 6 (Procurement): genuine partial-receipt support
for purchases - the core "quantity integrity" the brief explicitly
asks to test. Confirms stock is applied incrementally (never
double-counted across multiple partial receipts) and that receiving
more than what's outstanding is rejected."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _make_ordered_purchase(client, material_id, supplier_id, quantity="100"):
    return client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material_id,
        "quantity": quantity, "unit": "Sheets", "rate": "500", "gst_percent": "18", "receipt_status": "Ordered",
    }).json()


def test_partial_receipt_moves_to_partially_received(client, test_user):
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "Partial Receipt Test Supplier"}).json()["id"]
    material = client.post("/api/materials/", json={
        "name": "Partial Receipt Test Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    purchase = _make_ordered_purchase(client, material["id"], supplier_id, "100")

    resp = client.post(f"/api/purchases/{purchase['id']}/receive", json={"quantity": "40"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["receipt_status"] == "Partially Received"
    assert float(data["quantity_received"]) == 40.0

    refreshed_material = client.get(f"/api/materials/{material['id']}").json()
    assert float(refreshed_material["current_stock"]) == 40.0


def test_second_partial_receipt_completes_it_without_double_counting(client, test_user):
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "Second Receipt Test Supplier"}).json()["id"]
    material = client.post("/api/materials/", json={
        "name": "Second Receipt Test Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    purchase = _make_ordered_purchase(client, material["id"], supplier_id, "100")

    client.post(f"/api/purchases/{purchase['id']}/receive", json={"quantity": "40"})
    second = client.post(f"/api/purchases/{purchase['id']}/receive", json={"quantity": "60"})
    assert second.status_code == 200
    assert second.json()["receipt_status"] == "Received"
    assert float(second.json()["quantity_received"]) == 100.0

    refreshed_material = client.get(f"/api/materials/{material['id']}").json()
    # Must be exactly 100 (40 + 60), not more - confirms no double-counting.
    assert float(refreshed_material["current_stock"]) == 100.0


def test_cannot_receive_more_than_remaining(client, test_user):
    """The core quantity-integrity check."""
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "Over Receive Test Supplier"}).json()["id"]
    material = client.post("/api/materials/", json={
        "name": "Over Receive Test Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    purchase = _make_ordered_purchase(client, material["id"], supplier_id, "50")

    resp = client.post(f"/api/purchases/{purchase['id']}/receive", json={"quantity": "999"})
    assert resp.status_code == 400
    assert "remains outstanding" in resp.json()["detail"]


def test_cannot_receive_more_after_partial_receipt_already_taken(client, test_user):
    """Two separate receives that together would exceed the ordered
    amount must be rejected on the second one."""
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "Cumulative Over Receive Supplier"}).json()["id"]
    material = client.post("/api/materials/", json={
        "name": "Cumulative Over Receive Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    purchase = _make_ordered_purchase(client, material["id"], supplier_id, "50")

    client.post(f"/api/purchases/{purchase['id']}/receive", json={"quantity": "30"})
    resp = client.post(f"/api/purchases/{purchase['id']}/receive", json={"quantity": "30"})
    assert resp.status_code == 400


def test_receiving_with_no_body_still_receives_everything_remaining(client, test_user):
    """Backward compatibility - existing callers that POST with no
    body at all must keep working exactly as before."""
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "No Body Receive Test Supplier"}).json()["id"]
    material = client.post("/api/materials/", json={
        "name": "No Body Receive Test Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    purchase = _make_ordered_purchase(client, material["id"], supplier_id, "75")

    resp = client.post(f"/api/purchases/{purchase['id']}/receive")
    assert resp.status_code == 200
    assert resp.json()["receipt_status"] == "Received"
    assert float(resp.json()["quantity_received"]) == 75.0


def test_purchase_created_as_received_has_quantity_received_prefilled(client, test_user):
    """Migration-backfill equivalent at creation time - a purchase
    created already-Received must show full quantity_received
    immediately, not zero."""
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "Prefilled Test Supplier"}).json()["id"]
    material = client.post("/api/materials/", json={
        "name": "Prefilled Test Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    }).json()
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-19T00:00:00", "supplier_id": supplier_id, "material_id": material["id"],
        "quantity": "20", "unit": "Sheets", "rate": "500", "gst_percent": "18",
    }).json()
    assert purchase["receipt_status"] == "Received"
    assert float(purchase["quantity_received"]) == 20.0
