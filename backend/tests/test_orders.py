def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_client(client):
    resp = client.post("/api/clients/", json={
        "client_code": "CL-TEST", "name": "Test Client", "phone": "9999999999",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_order(client, client_id):
    resp = client.post("/api/orders/", json={
        "order_code": "WC-TEST-001", "client_id": client_id, "project_type": "TV Unit",
        "order_date": "2026-08-01T00:00:00", "order_value": "100000.00", "advance": "20000.00",
    })
    assert resp.status_code == 201
    return resp.json()


def test_order_starts_with_advance_as_received(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)
    assert float(order["total_received"]) == 20000.0
    assert float(order["balance"]) == 80000.0


def test_payment_updates_order_totals(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)

    resp = client.post("/api/payments/", json={
        "receipt_code": "RCPT-TEST-001", "date": "2026-08-05T00:00:00", "order_id": order["id"],
        "payment_type": "Progress Payment", "payment_mode": "UPI", "amount": "30000.00",
    })
    assert resp.status_code == 201

    updated_order = client.get(f"/api/orders/{order['id']}").json()
    assert float(updated_order["total_received"]) == 50000.0
    assert float(updated_order["balance"]) == 50000.0


def test_order_profitability_reflects_expenses(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)

    client.post("/api/project-expenses/", json={
        "expense_code": "EXP-TEST-001", "date": "2026-08-02T00:00:00", "order_id": order["id"],
        "category": "Raw Material", "amount": "40000.00",
    })

    profitability = client.get(f"/api/orders/{order['id']}/profitability").json()
    assert profitability["project_expenses"] == 40000.0
    assert profitability["estimated_gross_profit"] == 60000.0


def test_client_endpoint_requires_auth(client):
    resp = client.get("/api/clients/")
    assert resp.status_code == 401
