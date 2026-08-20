"""Explicit regression suite for Family 3's exact demand: advance +
payment + edited payment + multiple payments must all correctly
recompute Order.total_received/balance, and the stored advance must
never disappear during recomputation - a real bug documented in
Order.recompute_totals()'s own docstring.

"Deleted payment" is NOT covered here - checked directly and
confirmed no delete endpoint exists for payments at all (a
deliberate design choice: payments are a record of money that
actually changed hands, and deletability would risk hiding real
transactions or silently breaking balance consistency). There is
nothing to regression-test for a feature that does not exist."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_advance_alone_is_reflected_in_total_received(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Advance Only Test Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "50000", "advance": "10000",
    }).json()
    assert float(order["total_received"]) == 10000.0
    assert float(order["balance"]) == 40000.0


def test_advance_does_not_disappear_after_a_payment_is_recorded(client, test_user):
    """The exact bug documented in recompute_totals()'s own docstring -
    the advance must still be counted after a payment is added, not
    silently dropped."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Advance Persistence Test Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "50000", "advance": "10000",
    }).json()
    client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-19T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "UPI", "amount": "15000",
    })

    refreshed = client.get(f"/api/orders/{order['id']}").json()
    assert float(refreshed["total_received"]) == 25000.0  # 10000 advance + 15000 payment, advance still present
    assert float(refreshed["balance"]) == 25000.0


def test_multiple_payments_accumulate_correctly_with_advance(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Multiple Payments Test Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "50000", "advance": "10000",
    }).json()
    client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-19T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "UPI", "amount": "15000",
    })
    client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-20T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "Cash", "amount": "10000",
    })

    refreshed = client.get(f"/api/orders/{order['id']}").json()
    assert float(refreshed["total_received"]) == 35000.0  # 10000 + 15000 + 10000
    assert float(refreshed["balance"]) == 15000.0


def test_editing_a_payment_amount_recomputes_correctly(client, test_user):
    """The exact scenario Family 3 names explicitly - an edited
    payment must correctly recompute the order's totals, not just a
    newly-created one."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Edited Payment Test Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "50000", "advance": "10000",
    }).json()
    payment = client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-19T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "UPI", "amount": "15000",
    }).json()
    client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-20T00:00:00", "payment_type": "Progress Payment",
        "payment_mode": "Cash", "amount": "10000",
    })

    client.put(f"/api/payments/{payment['id']}", json={"amount": "20000"})

    refreshed = client.get(f"/api/orders/{order['id']}").json()
    assert float(refreshed["total_received"]) == 40000.0  # 10000 advance + 20000 edited + 10000 second payment
    assert float(refreshed["balance"]) == 10000.0


def test_no_delete_endpoint_exists_for_payments(client, test_user):
    """Documents the deliberate design choice this suite's scope
    depends on, rather than silently assume it - if a delete
    endpoint is ever added, this test will fail and signal that the
    "deleted payment" regression scenario now needs real coverage."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "No Delete Test Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    payment = client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-19T00:00:00", "payment_type": "Advance",
        "payment_mode": "Cash", "amount": "5000",
    }).json()

    resp = client.delete(f"/api/payments/{payment['id']}")
    assert resp.status_code in (404, 405)
