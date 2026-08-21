"""Family 4 - the chatbot's "budget" context answer for an order.

Woodful's data model has no genuine planned/project-budget field
(Order only has order_value, which is the order's price, not a
declared cost ceiling). These tests lock in that the chatbot never
claims a project is "over budget" - only that costs exceed the order
value, or what the estimated profit/margin is - and that the
master-only restriction on this financial data is unchanged.
"""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_limited_user(db_session, employee_id, username, email):
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("LimitedPass1!"), role="user", employee_id=employee_id, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _make_order(client, order_value, advance="0"):
    client_id = client.post("/api/clients/", json={"name": f"Budget Wording Client {order_value}", "phone": "9000010022"}).json()["id"]
    return client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00",
        "order_value": order_value, "advance": advance,
    }).json()


def test_costs_over_order_value_never_phrased_as_over_budget(client, test_user):
    """Case B (no real budget field): when actual costs exceed the
    order value, the reply must state that fact plainly and must never
    claim the project is "over budget" - Woodful has no budget concept
    for that word to accurately describe."""
    _login(client, test_user)
    order = _make_order(client, order_value="700000.00")
    client.post("/api/project-expenses/", json={
        "order_id": order["id"], "date": "2026-08-13T00:00:00", "expense_type": "Material", "amount": "800000.00",
    })

    resp = client.post("/api/chat/", json={
        "message": "What's the budget on this project?",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    text = resp.json()["response"]
    assert "over budget" not in text.lower()
    assert "exceed the order value" in text.lower()
    assert "100,000.00" in text  # the actual overage figure is still surfaced


def test_profitable_project_gets_neutral_profitability_wording(client, test_user):
    """A profitable project (costs below order value) must get the
    neutral profitability phrasing, never a budget claim - this is
    also the case a real planned-budget could diverge from (profitable
    but still over some hypothetical budget), which Woodful's model
    cannot evaluate, so profitability is the only thing stated."""
    _login(client, test_user)
    order = _make_order(client, order_value="1000000.00")
    client.post("/api/project-expenses/", json={
        "order_id": order["id"], "date": "2026-08-13T00:00:00", "expense_type": "Material", "amount": "800000.00",
    })

    resp = client.post("/api/chat/", json={
        "message": "How is this project's budget tracking?",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    text = resp.json()["response"]
    assert "over budget" not in text.lower()
    assert "gross profit" in text.lower()
    assert "margin" in text.lower()


def test_no_expense_data_does_not_falsely_claim_over_budget(client, test_user):
    """No project expenses/issues recorded yet - insufficient data for
    any cost claim beyond "zero so far". Must not falsely infer an
    over-budget state merely from the absence of data."""
    _login(client, test_user)
    order = _make_order(client, order_value="500000.00")

    resp = client.post("/api/chat/", json={
        "message": "budget check for this project",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    text = resp.json()["response"]
    assert "over budget" not in text.lower()


def test_non_master_user_gets_no_financial_figures_for_budget_question(client, test_user, db_session):
    """The budget/profitability answer stays behind the same
    master-only restriction as the profitability endpoint - unchanged
    by this wording fix."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Budget Wording Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    _create_limited_user(db_session, employee["id"], "budgetwordinguser", "budgetwordinguser@example.com")

    order = _make_order(client, order_value="500000.00")

    resp = client.post("/api/auth/login", json={"identifier": "budgetwordinguser@example.com", "password": "LimitedPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={
        "message": "What's the budget on this project?",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert chat_resp.status_code == 200
    text = chat_resp.json()["response"]
    assert "Rs" not in text
    assert "master accounts only" not in text.lower()  # this denial path uses its own account-role wording
    assert "account role" in text.lower()


def test_chatbot_order_context_still_works_for_non_budget_questions(client, test_user):
    """Regression check - the unrelated order-summary path through the
    same context resolver must be untouched by this change."""
    _login(client, test_user)
    order = _make_order(client, order_value="250000.00")

    resp = client.post("/api/chat/", json={
        "message": "Summarize this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    assert order["order_code"] in resp.json()["response"]
