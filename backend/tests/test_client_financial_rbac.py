"""Test for a gap found this turn - Client.total_sales (an aggregate
of order values) was returned to any authenticated role via
GET /api/clients/{id}, unredacted."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_master_sees_client_total_sales(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Client RBAC Master Test", "phone": "9000010049"}).json()
    resp = client.get(f"/api/clients/{created['id']}").json()
    assert resp["total_sales"] is not None


def test_employee_client_total_sales_is_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Client RBAC Employee Test", "phone": "9000010050"}).json()
    client.post("/api/orders/", json={
        "client_id": created["id"], "order_date": "2026-08-16T00:00:00", "order_value": "80000.00", "advance": "0",
    })

    employee = client.post("/api/employees/", json={
        "name": "Client RBAC Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username="clientrbacuser", email="clientrbacuser@example.com", full_name="Client RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/clients/{created['id']}").json()
    assert resp["total_sales"] is None
    # Non-financial fields remain real - total_orders is a count, not money.
    assert resp["total_orders"] == 1
    assert resp["name"] == "Client RBAC Employee Test"
