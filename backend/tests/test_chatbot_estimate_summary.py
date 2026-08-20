"""Tests for "summarize estimate EST-XXX" and deictic "summarize this
estimate" - the last explicitly-named AI capability from Family 3
not yet built ("AI may summarize estimates")."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_summarize_estimate_by_explicit_code(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Summary Test Client"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "18mm Plywood Panel", "category": "Material", "quantity": "2", "rate": "2500", "amount": "5000"}],
    }).json()

    resp = client.post("/api/chat/", json={"message": f"summarize estimate {estimate['estimate_code']}"})
    assert resp.status_code == 200
    data = resp.json()
    assert estimate["estimate_code"] in data["response"]
    assert "1 line item" in data["response"]
    assert "Rs" in data["response"]  # master sees the total


def test_summarize_estimate_hides_money_for_non_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Summary RBAC Client"}).json()["id"]
    estimate = client.post("/api/estimates/", json={"client_id": client_id, "material_cost": "5000"}).json()

    employee = client.post("/api/employees/", json={"name": "Estimate Summary RBAC Employee"}).json()
    user = User(
        username="estimatesummaryrbacuser", email="estimatesummaryrbacuser@example.com",
        full_name="Estimate Summary RBAC User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "estimatesummaryrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": f"summarize estimate {estimate['estimate_code']}"})
    assert "Rs" not in resp.json()["response"]


def test_summarize_this_estimate_via_deictic_context(client, test_user):
    """"summarize this estimate" while the estimate's page is open -
    resolved via record_type/record_id context, no code needed."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Summary Deictic Client"}).json()["id"]
    estimate = client.post("/api/estimates/", json={"client_id": client_id, "material_cost": "7000"}).json()

    resp = client.post("/api/chat/", json={
        "message": "summarize this estimate",
        "context": {"record_type": "estimate", "record_id": estimate["id"]},
    })
    assert resp.status_code == 200
    assert estimate["estimate_code"] in resp.json()["response"]


def test_summarize_unknown_estimate_code_falls_through(client, test_user):
    """An unmatched code must not error - just fall through to the
    generic fallback response."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "summarize estimate EST-99999"})
    assert resp.status_code == 200
