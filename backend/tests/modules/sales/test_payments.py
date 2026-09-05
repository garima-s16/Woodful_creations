import re
from tests.helpers import _login

CASH_REF_PATTERN = re.compile(r"^CASH-\d{8}-\d{3}$")


def _create_client(client, name="Payment Test Client"):
    resp = client.post("/api/clients/", json={"name": name, "phone": "9999999998"})
    assert resp.status_code == 201
    return resp.json()["id"]


def _create_order(client, client_id, order_value="100000.00"):
    resp = client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "Wardrobe",
        "order_date": "2026-08-01T00:00:00", "order_value": order_value, "advance": "0.00",
    })
    assert resp.status_code == 201
    return resp.json()


def test_cash_payment_gets_auto_generated_reference(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)

    resp = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "5000.00",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert CASH_REF_PATTERN.match(body["reference_number"]), f"got {body['reference_number']!r}"
    assert body["reference_number"].startswith("CASH-20260812-")


def test_cash_payment_ignores_client_supplied_reference(client, test_user):
    """The user should never have to (or be able to) type a cash reference -
    the backend always generates its own, even if the client sends one."""
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)

    resp = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "1000.00",
        "reference_number": "whatever-the-user-typed",
    })
    assert resp.status_code == 201
    assert resp.json()["reference_number"] != "whatever-the-user-typed"
    assert CASH_REF_PATTERN.match(resp.json()["reference_number"])


def test_cash_reference_numbers_are_sequential_and_unique_per_day(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)

    refs = set()
    for _ in range(3):
        resp = client.post("/api/payments/", json={
            "date": "2026-08-12T00:00:00", "order_id": order["id"],
            "payment_type": "Advance", "payment_mode": "Cash", "amount": "500.00",
        })
        assert resp.status_code == 201
        refs.add(resp.json()["reference_number"])
    assert len(refs) == 3


def test_non_cash_payment_keeps_user_supplied_reference(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)

    resp = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "2000.00",
        "reference_number": "402812345678",
    })
    assert resp.status_code == 201
    assert resp.json()["reference_number"] == "402812345678"


def test_payment_gets_rcpt_prefixed_receipt_code(client, test_user):
    """The business_id-format assertion this test used to also make is
    redundant with test_business_id.py's own systematic per-entity
    sweep (which already covers payments) - kept only the assertion
    genuinely unique to this test: the receipt_code prefix."""
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)

    resp = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Bank Transfer", "amount": "3000.00",
        "reference_number": "UTR123456",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert body["receipt_code"].startswith("RCPT-")


def test_payments_export_returns_xlsx(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)
    client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "1500.00",
    })

    resp = client.get("/api/reports/payments.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(resp.content) > 0


def test_payments_export_supports_filters(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)
    client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "1500.00",
    })

    resp = client.get(f"/api/reports/payments.xlsx?order_id={order['id']}&payment_mode=Cash")
    assert resp.status_code == 200


def test_payment_create_rejects_zero_amount(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)
    resp = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "0.00",
    })
    assert resp.status_code == 422


def test_payment_create_rejects_negative_amount(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)
    resp = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "-500.00",
    })
    assert resp.status_code == 422


def test_payment_create_allows_positive_amount_and_keeps_order_totals_correct(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)
    resp = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "2500.00",
    })
    assert resp.status_code == 201

    order_resp = client.get(f"/api/orders/{order['id']}")
    assert order_resp.status_code == 200
    assert order_resp.json()["total_received"] == "2500.00"


def test_payment_update_rejects_zero_and_negative_amount(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)
    order = _create_order(client, client_id)
    created = client.post("/api/payments/", json={
        "date": "2026-08-12T00:00:00", "order_id": order["id"],
        "payment_type": "Advance", "payment_mode": "Cash", "amount": "1000.00",
    }).json()

    resp = client.put(f"/api/payments/{created['id']}", json={"amount": "0.00"})
    assert resp.status_code == 422

    resp = client.put(f"/api/payments/{created['id']}", json={"amount": "-100.00"})
    assert resp.status_code == 422

    resp = client.put(f"/api/payments/{created['id']}", json={"amount": "1200.00"})
    assert resp.status_code == 200
