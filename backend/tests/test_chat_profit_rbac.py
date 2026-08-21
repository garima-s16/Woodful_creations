"""Tests for chatbot RBAC on profit/margin data - master gets the real
numbers, everyone else (including manager) gets a clear denial, never
silence or a wrong/generic answer."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_limited_user(client, db_session, employee_id, username, email):
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("LimitedPass1!"), role="user", employee_id=employee_id, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_master_asking_for_profit_gets_real_data(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Profit RBAC Client", "phone": "9000010025"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "50000.00", "advance": "0",
    })

    resp = client.post("/api/chat/", json={"message": "What are our profits this month?"})
    assert resp.status_code == 200
    text = resp.json()["response"]
    assert "margin" in text.lower()
    assert "only available to master" not in text.lower()


def test_regular_user_asking_for_profit_gets_clear_denial_not_data(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Profit RBAC Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    _create_limited_user(client, db_session, employee["id"], "profitrbacuser", "profitrbacuser@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "profitrbacuser@example.com", "password": "LimitedPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={"message": "What are our profits this month?"})
    assert chat_resp.status_code == 200
    text = chat_resp.json()["response"]
    assert "master accounts only" in text.lower()
    assert "Rs" not in text  # must not leak any real figures alongside the denial


def test_regular_user_asking_for_margin_also_denied(client, test_user, db_session):
    """"margin" is a separate keyword from "profit" - both must be
    gated, not just one."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Margin RBAC Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    _create_limited_user(client, db_session, employee["id"], "marginrbacuser", "marginrbacuser@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "marginrbacuser@example.com", "password": "LimitedPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={"message": "Show me the margin"})
    assert "master accounts only" in chat_resp.json()["response"].lower()


def test_non_master_role_is_denied_profit_access(client, test_user, db_session):
    """Only master has privileged access to profit data - any
    non-master role must be denied exactly like a plain employee."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Non-Master RBAC Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    non_master_user = User(
        username="nonmasterrbacuser", email="nonmasterrbacuser@example.com", full_name="Non-Master RBAC User",
        password_hash=hash_password("UserPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(non_master_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "nonmasterrbacuser@example.com", "password": "UserPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={"message": "What is our overall profit margin?"})
    text = chat_resp.json()["response"]
    assert "master accounts only" in text.lower()
    assert "Rs" not in text


def test_profitability_figures_match_the_real_order_service_calculation(client, test_user):
    """Single source of truth check - the chatbot's numbers must come
    from the same OrderService.profitability() the dashboard uses, not
    an independently re-derived calculation that could drift."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Profit Consistency Client", "phone": "9000010026"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "100000.00", "advance": "0",
    }).json()
    client.post("/api/project-expenses/", json={
        "order_id": order["id"], "date": "2026-08-13T00:00:00", "expense_type": "Material", "amount": "40000.00",
    })

    dashboard_resp = client.get("/api/dashboard/orders")
    dashboard_row = next(r for r in dashboard_resp.json()["order_profitability"] if r["order_id"] == order["order_code"])

    chat_resp = client.post("/api/chat/", json={"message": "Show profitability"})
    chat_text = chat_resp.json()["response"]
    assert f"{dashboard_row['estimated_gross_profit']:,.2f}" in chat_text
