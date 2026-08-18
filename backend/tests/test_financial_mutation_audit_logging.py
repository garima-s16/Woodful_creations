"""Tests for audit logging on financial mutations - payments, orders,
and project expenses. Continues the coverage started with deletes and
salary slips; verifies the shared serializable_fields() helper works
correctly across these different models (a regression guard for the
Decimal/JSON bug already caught once in salary_slips.py)."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_update_payment_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Audit Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "40000", "advance": "0",
    }).json()
    payment = client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-21T00:00:00", "amount": "5000",
        "payment_type": "Advance", "payment_mode": "Cash",
    }).json()

    resp = client.put(f"/api/payments/{payment['id']}", json={"amount": "6000"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "update_payment" and l["record_id"] == payment["id"]), None)
    assert match is not None
    assert match["old_value"]["amount"] == 5000.0
    assert match["new_value"]["amount"] == 6000.0


def test_create_order_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Audit Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "25000", "advance": "0",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "create_order" and l["record_id"] == order["id"]), None)
    assert match is not None
    assert match["new_value"]["order_value"] == 25000.0


def test_update_order_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Update Audit Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "25000", "advance": "0",
    }).json()

    resp = client.put(f"/api/orders/{order['id']}", json={"project_type": "Kitchen"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "update_order" and l["record_id"] == order["id"]), None)
    assert match is not None
    assert match["new_value"]["project_type"] == "Kitchen"


def test_create_and_update_project_expense_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Expense Audit Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "30000", "advance": "0",
    }).json()
    expense = client.post("/api/project-expenses/", json={
        "order_id": order["id"], "date": "2026-08-21T00:00:00", "category": "Material", "amount": "5000",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    create_match = next((l for l in logs if l["action"] == "create_project_expense" and l["record_id"] == expense["id"]), None)
    assert create_match is not None
    assert create_match["new_value"]["category"] == "Material"

    resp = client.put(f"/api/project-expenses/{expense['id']}", json={"amount": "5500"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    update_match = next((l for l in logs if l["action"] == "update_project_expense" and l["record_id"] == expense["id"]), None)
    assert update_match is not None
    assert update_match["old_value"]["amount"] == 5000.0
    assert update_match["new_value"]["amount"] == 5500.0
