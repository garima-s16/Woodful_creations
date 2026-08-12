import re

BUSINESS_ID_PATTERN = re.compile(r"^[A-Z0-9]{10}$")
CASH_REF_PATTERN = re.compile(r"^CASH-\d{8}-\d{3}$")


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


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


def test_payment_gets_10_char_business_id(client, test_user):
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
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
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
