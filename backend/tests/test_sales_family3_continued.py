"""Tests for Family 3 continued work: order.balance consolidated to
the single authoritative recompute_totals() method (was duplicated
inline in update_order, a real "fake duplicate totals" risk even
though both produced the same result today), the new sales-history
chatbot summary, and export rate limiting."""
import io
from openpyxl import load_workbook


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_order_balance_recomputes_correctly_when_items_change(client, test_user):
    """Confirms the consolidated recompute_totals() call still produces
    the correct balance after an item-driven order_value change,
    verifying the refactor didn't change behavior."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Recompute Totals Test Client", "phone": "9000010176"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Custom wardrobe", "unit": "Nos"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "2000",
    }).json()
    assert float(order["balance"]) == 8000.0

    updated = client.put(f"/api/orders/{order['id']}", json={
        "items": [{"description": "Custom wardrobe", "quantity": "1", "rate": "25000", "amount": "25000", "product_id": product_id}],
    }).json()
    assert float(updated["order_value"]) == 25000.0
    assert float(updated["balance"]) == 23000.0  # 25000 - 2000 advance, matching recompute_totals()'s formula


def test_order_balance_stays_consistent_after_a_payment(client, test_user):
    """The same balance field, now updated via a completely different
    code path (payments.py) - both must agree on the same number."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Consistency Test Client", "phone": "9000010177"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "20000", "advance": "0",
    }).json()
    client.post("/api/payments/", json={"order_id": order["id"], "amount": "5000", "payment_date": "2026-08-19T00:00:00"})

    refreshed = client.get(f"/api/orders/{order['id']}").json()
    assert float(refreshed["balance"]) == 15000.0


def test_chatbot_sales_history_summary(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Shrangi", "phone": "9000010178"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "30000", "advance": "10000",
    })

    resp = client.post("/api/chat/", json={"message": "shrangi sales history"})
    assert resp.status_code == 200
    data = resp.json()
    assert "1 order" in data["response"]
    assert "Rs" in data["response"]  # master sees the financial figure


def test_chatbot_sales_history_hides_money_for_non_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Khushaal", "phone": "9000010179"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "40000", "advance": "0",
    })
    employee = client.post("/api/employees/", json={"name": "Sales History RBAC Employee"}).json()
    user = User(
        username="saleshistoryrbacuser", email="saleshistoryrbacuser@example.com",
        full_name="Sales History RBAC User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "saleshistoryrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": "khushaal sales history"})
    assert "Rs" not in resp.json()["response"]


def test_estimates_export_is_rate_limited(client, test_user):
    _login(client, test_user)
    from app.core.config import settings
    responses = [client.get("/api/reports/estimates.xlsx") for _ in range(settings.RATE_LIMIT_EXPORT_PER_MINUTE + 3)]
    assert any(r.status_code == 429 for r in responses)
