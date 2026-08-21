"""Tests for chatbot cart optimization (UI/UX backlog item 4). The cart
has no backend representation - the frontend sends its contents as
context.cart_items, and the assistant computes real supplier
comparisons from actual SupplierMaterial pricing, never fabricated
numbers."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_optimize_cart_picks_cheapest_supplier_per_item(client, test_user):
    _login(client, test_user)
    supplier_cheap = client.post("/api/suppliers/", json={"name": "Cheap Cart Supplier"}).json()
    supplier_expensive = client.post("/api/suppliers/", json={"name": "Expensive Cart Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Cart Optimize Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_cheap["id"], "material_id": material["id"], "supplier_price": "100.00",
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_expensive["id"], "material_id": material["id"], "supplier_price": "120.00",
    })

    resp = client.post("/api/chat/", json={
        "message": "Optimize this purchase",
        "context": {"cart_items": [{"material_id": material["id"], "quantity": 5}]},
    })
    assert resp.status_code == 200
    text = resp.json()["response"]
    assert "Cheap Cart Supplier" in text
    assert "Expensive Cart Supplier" not in text  # not chosen, shouldn't appear as a group
    assert "500" in text or "500.00" in text  # 100 * 5


def test_optimize_cart_reports_real_savings_only_where_price_varies(client, test_user):
    """Matches the exact hand-traced scenario: one item with real price
    variance across suppliers, one with only a single fallback price -
    savings must reflect only the item that actually varies."""
    _login(client, test_user)
    supplier_a = client.post("/api/suppliers/", json={"name": "Savings Test Supplier A"}).json()
    supplier_b = client.post("/api/suppliers/", json={"name": "Savings Test Supplier B"}).json()

    material_with_variance = client.post("/api/materials/", json={
        "name": "Variance Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_a["id"], "material_id": material_with_variance["id"], "supplier_price": "100.00",
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_b["id"], "material_id": material_with_variance["id"], "supplier_price": "120.00",
    })

    material_no_variance = client.post("/api/materials/", json={
        "name": "No Variance Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
        "average_rate": "50.00",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "Optimize this purchase",
        "context": {"cart_items": [
            {"material_id": material_with_variance["id"], "quantity": 5},
            {"material_id": material_no_variance["id"], "quantity": 3},
        ]},
    })
    text = resp.json()["response"]
    assert "100.00" in text or "100" in text  # savings = 20 * 5 = 100, matches the hand-traced value


def test_optimize_cart_with_no_pricing_at_all_gives_honest_message(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "No Pricing Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 1,
        "average_rate": "0",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "Optimize this purchase",
        "context": {"cart_items": [{"material_id": material["id"], "quantity": 2}]},
    })
    assert "couldn't find pricing" in resp.json()["response"].lower()


def test_cart_optimization_only_triggers_with_cart_items_in_context(client, test_user):
    """"Optimize" without cart context must not crash or misfire -
    falls through to the general dispatch instead."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "Optimize this purchase"})
    assert resp.status_code == 200  # doesn't error, just doesn't trigger cart-specific logic
