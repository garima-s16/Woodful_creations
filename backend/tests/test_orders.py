import re
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


def test_payments_filtered_by_client_across_multiple_orders(client, test_user):
    _login(client, test_user)
    client_resp = client.post("/api/clients/", json={"name": "Multi-Order Client"})
    client_id = client_resp.json()["id"]

    order1 = client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "Wardrobe",
        "order_date": "2026-08-01T00:00:00", "order_value": "40000.00", "advance": "0",
    }).json()
    order2 = client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "Bed",
        "order_date": "2026-08-02T00:00:00", "order_value": "60000.00", "advance": "0",
    }).json()

    client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order1["id"],
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "10000.00",
    })
    client.post("/api/payments/", json={
        "date": "2026-08-06T00:00:00", "order_id": order2["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "15000.00",
    })

    # A single client_id call should return both payments, across both orders,
    # without the caller needing to fetch per-order.
    resp = client.get("/api/payments/", params={"client_id": client_id})
    assert resp.status_code == 200
    amounts = sorted(float(p["amount"]) for p in resp.json())
    assert amounts == [10000.0, 15000.0]


def test_payments_client_filter_excludes_other_clients(client, test_user):
    _login(client, test_user)
    client_a = client.post("/api/clients/", json={"name": "Client A"}).json()["id"]
    client_b = client.post("/api/clients/", json={"name": "Client B"}).json()["id"]

    order_a = client.post("/api/orders/", json={
        "client_id": client_a, "order_date": "2026-08-01T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_b, "order_date": "2026-08-01T00:00:00", "order_value": "20000.00", "advance": "0",
    }).json()

    client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order_a["id"],
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "5000.00",
    })
    client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order_b["id"],
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "7000.00",
    })

    resp = client.get("/api/payments/", params={"client_id": client_a})
    payments = resp.json()
    assert len(payments) == 1
    assert float(payments[0]["amount"]) == 5000.0


def test_advance_is_not_lost_when_a_payment_is_recorded_afterward(client, test_user):
    """Regression test for a real bug found during integration testing:
    recompute_totals() summed only Payment rows, but the advance amount
    is stored directly on the Order at creation (never as its own
    Payment record) - so total_received would silently drop to just the
    newest payment the instant any payment was recorded afterward,
    making the original advance vanish from the running total."""
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200

    client_id = client.post("/api/clients/", json={"name": "Advance Regression Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00",
        "order_value": "100000.00", "advance": "30000.00",
    }).json()
    assert order["total_received"] == "30000.00"

    client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order["id"],
        "payment_type": "Progress Payment", "payment_mode": "UPI", "amount": "20000.00",
    })

    order_after = client.get(f"/api/orders/{order['id']}").json()
    # The advance (30000) must still be reflected, not just the new payment (20000).
    assert order_after["total_received"] == "50000.00"
    assert order_after["balance"] == "50000.00"


def test_cash_payment_gets_auto_generated_reference(client, test_user):
    """Cash payments have no external transaction to reference, so the
    user must not have to invent one - the backend generates it, per
    the specified CASH-YYYYMMDD-NNN format."""
    _login2(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Cash Reference Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()

    resp = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "5000.00",
    })
    assert resp.status_code == 201
    reference = resp.json()["reference_number"]
    assert reference == "CASH-20260812-001"

    # Receipt ID (business_id) must be the real 10-char ID, and distinct
    # from the cash reference - these are two different identifiers.
    assert re.match(r"^[A-Z0-9]{10}$", resp.json()["business_id"])
    assert resp.json()["business_id"] != reference


def test_cash_payment_reference_increments_per_day(client, test_user):
    _login2(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Cash Increment Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()

    refs = []
    for i in range(3):
        resp = client.post("/api/payments/", json={
            "date": "2026-08-12T00:00:00", "order_id": order["id"],
            "payment_type": "Advance", "payment_mode": "Cash", "amount": "1000.00",
        })
        refs.append(resp.json()["reference_number"])

    assert refs == ["CASH-20260812-001", "CASH-20260812-002", "CASH-20260812-003"]


def test_non_cash_payment_keeps_user_supplied_reference(client, test_user):
    """UPI/Bank/Card modes have a real external transaction reference the
    system cannot know on its own - the user-supplied value must be
    preserved exactly, not overwritten."""
    _login2(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "UPI Reference Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "10000.00", "advance": "0",
    }).json()

    resp = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "2000.00",
        "reference_number": "UPI-TXN-88213347",
    })
    assert resp.status_code == 201
    assert resp.json()["reference_number"] == "UPI-TXN-88213347"
