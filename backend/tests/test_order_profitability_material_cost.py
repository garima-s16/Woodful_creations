"""Tests for Section 4.6's explicit requirement - actual profitability
must not be represented as just Order Value - Project Expenses when
real material issue cost data exists. Labour cost is deliberately
excluded (no genuine time-tracking-to-wage data exists), not
fabricated."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_profitability_includes_real_material_issue_cost(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Material Cost Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Profitability Material", "unit": "Sheets", "opening_stock": "50",
        "minimum_stock": "1", "average_rate": "2000.00",
    }).json()

    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "10", "unit": "Sheets",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    assert resp.status_code == 200
    body = resp.json()
    assert body["material_cost"] == 20000.0  # 10 sheets * 2000/sheet
    assert body["actual_direct_costs"] == 20000.0  # no project expenses in this test
    assert body["estimated_gross_profit"] == 80000.0  # 100000 - 20000


def test_profitability_combines_material_cost_and_project_expenses(client, test_user):
    """The core fix - previously this order's gross profit would have
    only subtracted the 15000 expense, silently ignoring the 20000 of
    real material cost."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Combined Cost Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Combined Cost Material", "unit": "Sheets", "opening_stock": "50",
        "minimum_stock": "1", "average_rate": "2000.00",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "10", "unit": "Sheets",
    })
    client.post("/api/project-expenses/", json={
        "order_id": order["id"], "date": "2026-08-15T00:00:00", "expense_type": "Transport", "amount": "15000.00",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    body = resp.json()
    assert body["project_expenses"] == 15000.0
    assert body["material_cost"] == 20000.0
    assert body["actual_direct_costs"] == 35000.0
    assert body["estimated_gross_profit"] == 65000.0  # 100000 - 35000, not just 100000 - 15000


def test_order_with_no_material_issued_has_zero_material_cost(client, test_user):
    """An order with only expenses and no material issued must not
    show a fabricated material cost - genuinely zero, honestly."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "No Material Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "50000.00", "advance": "0",
    }).json()
    client.post("/api/project-expenses/", json={
        "order_id": order["id"], "date": "2026-08-15T00:00:00", "expense_type": "Labour", "amount": "5000.00",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability")
    body = resp.json()
    assert body["material_cost"] == 0.0
    assert body["estimated_gross_profit"] == 45000.0


def test_material_issued_to_a_different_order_does_not_affect_this_order(client, test_user):
    """Material cost must be correctly scoped per order, not leak
    across orders that happen to use the same material."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Isolation Cost Client"}).json()["id"]
    order_a = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Shared Cost Material", "unit": "Sheets", "opening_stock": "50",
        "minimum_stock": "1", "average_rate": "1000.00",
    }).json()

    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order_a["id"], "material_id": material["id"],
        "quantity_issued": "5", "unit": "Sheets",
    })

    order_a_profit = client.get(f"/api/orders/{order_a['id']}/profitability").json()
    order_b_profit = client.get(f"/api/orders/{order_b['id']}/profitability").json()
    assert order_a_profit["material_cost"] == 5000.0
    assert order_b_profit["material_cost"] == 0.0


def test_material_cost_supports_decimal_quantities(client, test_user):
    """Consistent with the decimal-quantity fix - material cost must
    correctly reflect a fractional quantity issued (e.g. 2.5 kg)."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Decimal Cost Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Decimal Cost Adhesive", "unit": "Kg", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "400.00",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "2.5", "unit": "Kg",
    })

    resp = client.get(f"/api/orders/{order['id']}/profitability").json()
    assert resp["material_cost"] == 1000.0  # 2.5 kg * 400/kg


def test_dashboard_excel_and_chatbot_all_reflect_the_same_material_cost(client, test_user):
    """Single source of truth check across all three consumers named in
    the brief - dashboard, Excel export, and chatbot must not disagree."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Consistency Check Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": "20000.00", "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": "Consistency Check Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "500.00",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "4", "unit": "Sheets",
    })

    dashboard_row = next(
        r for r in client.get("/api/dashboard/orders").json()["order_profitability"]
        if r["order_id"] == order["order_code"]
    )
    order_detail = client.get(f"/api/orders/{order['id']}/profitability").json()

    assert dashboard_row["material_cost"] == order_detail["material_cost"] == 2000.0
