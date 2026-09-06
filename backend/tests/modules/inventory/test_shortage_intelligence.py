"""Order Material Requirement + Shortage Intelligence
(StockService.calculate_order_material_requirements, GET
/api/orders/{id}/material-requirements). Proves the exact formula from
the spec (section 9.3): Shortage = max(0, Required - Available -
Relevant Pending Supply) - the pending purchase is netted directly
into the shortage figure, not applied as a separate later step."""
from tests.helpers import _login


def _make_client(client, suffix):
    return client.post("/api/clients/", json={
        "name": f"Shortage Intel Client {suffix}", "phone": f"90000103{suffix}",
    }).json()["id"]


def test_shortage_matches_worked_example_5_required_2_available_1_pending(client, test_user):
    """5 sheets required, 2 available, a pending purchase of 1 already
    placed -> shortage 2 (required - available - pending), not 3 -
    exactly the spec's own formula and worked example."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Shortage Intel HDHMR Sheet", "unit": "Sheets", "opening_stock": "2", "minimum_stock": "1",
    }).json()
    supplier = client.post("/api/suppliers/", json={"name": "Shortage Intel Supplier"}).json()
    # A purchase already placed but not yet received - "pending".
    client.post("/api/purchases/", json={
        "date": "2026-08-01T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "1", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "receipt_status": "Ordered",
    })
    product = client.post("/api/products/", json={
        "name": "Shortage Intel Wardrobe", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = _make_client(client, "1")
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Wardrobe", "quantity": "1", "unit": "Piece", "rate": "40000", "product_id": product["id"]}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/material-requirements")
    assert resp.status_code == 200
    materials = resp.json()["materials"]
    assert len(materials) == 1
    row = materials[0]
    assert row["material_id"] == material["id"]
    assert float(row["required"]) == 5.0
    assert float(row["available"]) == 2.0
    assert float(row["gap_before_pending_supply"]) == 3.0
    assert float(row["pending_purchase_quantity"]) == 1.0
    assert float(row["shortage"]) == 2.0
    assert float(row["recommended_purchase_quantity"]) == 2.0


def test_shortage_multiplies_bom_quantity_by_order_quantity(client, test_user):
    """2 wardrobes ordered, each needs 5 sheets -> 10 required, not 5 -
    the BOM quantity must scale with how many units were actually
    ordered, not just the per-unit recipe."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Shortage Intel Ply Sheet", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Shortage Intel Cabinet", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = _make_client(client, "2")
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Cabinet", "quantity": "2", "unit": "Piece", "rate": "20000", "product_id": product["id"]}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/material-requirements")
    row = resp.json()["materials"][0]
    assert float(row["required"]) == 10.0
    assert float(row["recommended_purchase_quantity"]) == 10.0


def test_no_shortage_when_stock_covers_requirement(client, test_user):
    """Enough stock on hand -> zero shortage, zero recommendation, not
    a negative or nonsensical number."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Shortage Intel Surplus Sheet", "unit": "Sheets", "opening_stock": "20", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Shortage Intel Shelf", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "3"}],
    }).json()
    client_id = _make_client(client, "3")
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Shelf", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/material-requirements")
    row = resp.json()["materials"][0]
    assert float(row["shortage"]) == 0.0
    assert float(row["recommended_purchase_quantity"]) == 0.0


def test_order_item_without_product_has_no_material_requirement(client, test_user):
    """A freeform order line (no product_id, e.g. "Installation") has
    no BOM to trace, so it contributes nothing - not an error."""
    _login(client, test_user)
    client_id = _make_client(client, "4")
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Installation", "quantity": "1", "unit": "Nos", "rate": "2000"}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/material-requirements")
    assert resp.status_code == 200
    assert resp.json()["materials"] == []


def test_reserved_stock_from_other_open_order_reduces_available(client, test_user):
    """Two open orders competing for the same material: Order A's own
    unfulfilled BOM demand (nothing issued against it yet) must reduce
    what Order B sees as "available", per Available = Current Stock -
    Reserved Qty. Neither order's own demand should reserve against
    itself (checked separately below)."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Shortage Intel Contested Sheet", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Shortage Intel Contested Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "6"}],
    }).json()
    client_a = _make_client(client, "5a")
    client_b = _make_client(client, "5b")
    order_a = client.post("/api/orders/", json={
        "client_id": client_a, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_b, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    # Order A's own check: nothing else is open yet except Order B,
    # which also needs 6 - Order A must see Order B's demand reserved
    # against it, not its own.
    resp_a = client.get(f"/api/orders/{order_a['id']}/material-requirements")
    row_a = resp_a.json()["materials"][0]
    assert float(row_a["reserved_by_other_orders"]) == 6.0
    assert float(row_a["available"]) == 4.0  # 10 stock - 6 reserved by order B
    assert float(row_a["shortage"]) == 2.0   # 6 required - 4 available

    resp_b = client.get(f"/api/orders/{order_b['id']}/material-requirements")
    row_b = resp_b.json()["materials"][0]
    assert float(row_b["reserved_by_other_orders"]) == 6.0  # order A's own unfulfilled demand
    assert float(row_b["available"]) == 4.0
    assert float(row_b["shortage"]) == 2.0


def test_issuing_material_releases_the_reservation(client, test_user):
    """Once a material is actually issued against an order, that
    portion of its demand is fulfilled - it must stop counting as
    reserved against other orders."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Shortage Intel Issued Sheet", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Shortage Intel Issued Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "6"}],
    }).json()
    client_a = _make_client(client, "6a")
    client_b = _make_client(client, "6b")
    order_a = client.post("/api/orders/", json={
        "client_id": client_a, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_b, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    # Order A's full 6-sheet requirement is issued - fully fulfilled,
    # nothing left of its demand to reserve.
    client.post("/api/issues/", json={
        "date": "2026-08-19T00:00:00", "order_id": order_a["id"], "material_id": material["id"],
        "quantity_issued": "6", "unit": "Sheets",
    })

    resp_b = client.get(f"/api/orders/{order_b['id']}/material-requirements")
    row_b = resp_b.json()["materials"][0]
    assert float(row_b["reserved_by_other_orders"]) == 0.0
    assert float(row_b["available"]) == 10.0


def test_cancelled_order_does_not_reserve_stock(client, test_user):
    """A cancelled order's demand must not reserve stock against
    other orders - it will never actually consume that material."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Shortage Intel Cancelled Sheet", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Shortage Intel Cancelled Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "6"}],
    }).json()
    client_a = _make_client(client, "7a")
    client_b = _make_client(client, "7b")
    order_a = client.post("/api/orders/", json={
        "client_id": client_a, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    client.put(f"/api/orders/{order_a['id']}", json={"project_status": "Cancelled"})
    order_b = client.post("/api/orders/", json={
        "client_id": client_b, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    resp_b = client.get(f"/api/orders/{order_b['id']}/material-requirements")
    row_b = resp_b.json()["materials"][0]
    assert float(row_b["reserved_by_other_orders"]) == 0.0
    assert float(row_b["available"]) == 10.0


def test_hardware_requirement_uses_the_same_bom_path_unchanged(client, test_user):
    """Phase C's own worked example: product quantity x hardware-per-
    product = required hinges/handles. A hardware-category Material
    linked via the same ProductMaterial BOM must flow through the
    identical shortage calculation as any raw material - no separate
    "hardware requirement" code path exists or is needed, since a
    hinge is just another Material to this service."""
    _login(client, test_user)
    hinge = client.post("/api/materials/", json={
        "name": "Shortage Intel Soft-Close Hinge", "category": "Hardware", "unit": "Nos",
        "opening_stock": "10", "minimum_stock": "4",
    }).json()
    assert hinge["category"] == "Hardware"
    # 2 doors per wardrobe, 2 hinges per door = 4 hinges per wardrobe.
    product = client.post("/api/products/", json={
        "name": "Shortage Intel Hinged Wardrobe", "unit": "Piece",
        "materials_used": [{"material_id": hinge["id"], "quantity_required": "4"}],
    }).json()
    client_id = _make_client(client, "8")
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Wardrobe", "quantity": "3", "unit": "Piece", "rate": "35000", "product_id": product["id"]}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}/material-requirements")
    assert resp.status_code == 200
    row = resp.json()["materials"][0]
    assert row["material_id"] == hinge["id"]
    assert float(row["required"]) == 12.0  # 3 wardrobes x 4 hinges
    assert float(row["available"]) == 10.0
    assert float(row["shortage"]) == 2.0  # 12 required - 10 available


def test_material_requirements_requires_auth(client):
    resp = client.get("/api/orders/1/material-requirements")
    assert resp.status_code == 401


def test_material_requirements_unknown_order_returns_404(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/orders/999999/material-requirements")
    assert resp.status_code == 404


def test_at_risk_orders_matches_per_order_calculation(client, test_user):
    """The bulk dashboard calculation (calculate_at_risk_orders) must
    produce exactly the same shortage figures as calling the per-order
    endpoint for each order individually - proves the business-wide
    derivation (reserved-by-others from a total already in memory,
    not a second per-order query) is mathematically equivalent, not a
    second, independently-drifting way to compute a shortage. Reuses
    the exact two-competing-orders scenario from
    test_reserved_stock_from_other_open_order_reduces_available above."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "At Risk Dashboard Contested Sheet", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "At Risk Dashboard Contested Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "6"}],
    }).json()
    client_a = _make_client(client, "9a")
    client_b = _make_client(client, "9b")
    order_a = client.post("/api/orders/", json={
        "client_id": client_a, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_b, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    per_order_a = client.get(f"/api/orders/{order_a['id']}/material-requirements").json()["materials"][0]
    per_order_b = client.get(f"/api/orders/{order_b['id']}/material-requirements").json()["materials"][0]

    resp = client.get("/api/dashboard/at-risk-orders")
    assert resp.status_code == 200
    body = resp.json()
    by_order_id = {row["order_id"]: row for row in body["orders"]}
    assert order_a["id"] in by_order_id
    assert order_b["id"] in by_order_id

    bulk_a = by_order_id[order_a["id"]]["materials"][0]
    bulk_b = by_order_id[order_b["id"]]["materials"][0]
    assert float(bulk_a["shortage"]) == float(per_order_a["shortage"]) == 2.0
    assert float(bulk_a["available"]) == float(per_order_a["available"]) == 4.0
    assert float(bulk_b["shortage"]) == float(per_order_b["shortage"]) == 2.0
    assert float(bulk_b["available"]) == float(per_order_b["available"]) == 4.0


def test_at_risk_orders_excludes_order_with_sufficient_stock(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "At Risk Dashboard Ample Sheet", "unit": "Sheets", "opening_stock": "100", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "At Risk Dashboard Ample Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "2"}],
    }).json()
    client_id = _make_client(client, "9c")
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    resp = client.get("/api/dashboard/at-risk-orders")
    assert resp.status_code == 200
    order_ids = [row["order_id"] for row in resp.json()["orders"]]
    assert order["id"] not in order_ids


def test_at_risk_orders_requires_auth(client):
    resp = client.get("/api/dashboard/at-risk-orders")
    assert resp.status_code == 401


def test_material_requirement_recalculates_when_order_quantity_changes(client, test_user):
    """P0.1 section 8 (Configuration Change Impact) - changing an
    order's item quantity must immediately change its material
    requirement, with no manual recalculation step and no stale
    value, since this is computed fresh from current order_items/BOM/
    stock on every call rather than stored anywhere."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Config Change Impact Sheet", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Config Change Impact Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "1"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": "Config Change Impact Client", "phone": "9000010800"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()

    before = client.get(f"/api/orders/{order['id']}/material-requirements").json()["materials"][0]
    assert float(before["required"]) == 1.0
    assert float(before["shortage"]) == 0.0

    update_resp = client.put(f"/api/orders/{order['id']}", json={
        "items": [{"description": "Item", "quantity": "10", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    })
    assert update_resp.status_code == 200

    after = client.get(f"/api/orders/{order['id']}/material-requirements").json()["materials"][0]
    assert float(after["required"]) == 10.0
    assert float(after["shortage"]) == 5.0
