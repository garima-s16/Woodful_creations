def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_order_with_items_computes_order_value_from_items(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Items Test Client"}).json()["id"]

    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "10000.00",
        "items": [
            {"description": "Wardrobe", "category": "Furniture", "quantity": "1", "unit": "Nos", "rate": "85000.00"},
            {"description": "Installation", "category": "Installation", "quantity": "1", "unit": "Lot", "rate": "10000.00"},
        ],
    })
    assert resp.status_code == 201
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["amount"] == "85000.00"
    assert body["order_value"] == "95000.00"
    assert body["balance"] == "85000.00"  # 95000 - 10000 advance
    assert body["items_subtotal"] == "95000.00"


def test_item_amount_is_server_computed(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Item Trust Client"}).json()["id"]

    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "0",
        "items": [{"description": "Test Item", "quantity": "4", "rate": "500.00", "amount": "999999.00"}],
    })
    assert resp.status_code == 201
    assert resp.json()["items"][0]["amount"] == "2000.00"


def test_order_created_from_estimate_copies_items_and_links_back(client, test_user):
    """Priority 1B's exact workflow: Estimate -> Estimate Items -> Order
    -> Order Items, with the estimate linked back to the order it produced."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate To Order Client"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [
            {"description": "Modular Kitchen", "category": "Furniture", "quantity": "1", "unit": "Lot", "rate": "250000.00"},
            {"description": "Hardware", "category": "Hardware", "quantity": "1", "unit": "Lot", "rate": "30000.00"},
        ],
    }).json()

    order_resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "50000.00",
        "from_estimate_id": estimate["id"],
    })
    assert order_resp.status_code == 201
    order = order_resp.json()
    assert len(order["items"]) == 2
    assert order["order_value"] == "280000.00"
    descriptions = {item["description"] for item in order["items"]}
    assert descriptions == {"Modular Kitchen", "Hardware"}
    # Each copied item traces back to the estimate line it came from.
    assert all(item["source_estimate_item_id"] is not None for item in order["items"])

    # The estimate itself is now linked to the order it produced.
    estimate_after = client.get(f"/api/estimates/{estimate['id']}").json()
    assert estimate_after["order_id"] == order["id"]


def test_order_without_items_still_works_with_flat_order_value(client, test_user):
    """Backward compatibility - an order can still be created the old
    way, with just a flat order_value and no items."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Flat Order Value Client"}).json()["id"]

    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00",
        "order_value": "50000.00", "advance": "10000.00",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["items"] == []
    assert body["items_subtotal"] is None
    assert body["order_value"] == "50000.00"


def test_updating_order_items_replaces_full_set_and_recomputes_value(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Update Order Items Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "0",
        "items": [{"description": "Original Item", "quantity": "1", "rate": "10000.00"}],
    }).json()

    resp = client.put(f"/api/orders/{order['id']}", json={
        "items": [{"description": "New Item", "quantity": "2", "rate": "7000.00"}],
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["description"] == "New Item"
    assert body["order_value"] == "14000.00"
    assert body["balance"] == "14000.00"


def test_order_still_gets_business_id_with_items(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Business ID Items Client"}).json()["id"]
    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "advance": "0",
        "items": [{"description": "Item", "quantity": "1", "rate": "1000.00"}],
    })
    assert resp.status_code == 201
    assert len(resp.json()["business_id"]) == 10


def test_payment_status_reflects_actual_payment_state(client, test_user):
    """Priority 3's explicit requirement - Payment Status derived from
    the same authoritative balance/total_received fields, not a
    separately-maintained column that could drift out of sync."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Status Client"}).json()["id"]

    unpaid = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "50000.00", "advance": "0",
    }).json()
    assert unpaid["payment_status"] == "Unpaid"

    partially_paid = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "50000.00", "advance": "20000.00",
    }).json()
    assert partially_paid["payment_status"] == "Partially Paid"

    paid = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "50000.00", "advance": "50000.00",
    }).json()
    assert paid["payment_status"] == "Paid"

    # Recording an additional payment against the partially-paid order
    # must move it to Paid - proving payment_status stays in sync via
    # the same recompute_totals() path, not a stale snapshot.
    client.post("/api/payments/", json={
        "date": "2026-08-14T00:00:00", "order_id": partially_paid["id"],
        "payment_type": "Progress Payment", "payment_mode": "Bank", "amount": "30000.00",
    })
    updated = client.get(f"/api/orders/{partially_paid['id']}").json()
    assert updated["payment_status"] == "Paid"
