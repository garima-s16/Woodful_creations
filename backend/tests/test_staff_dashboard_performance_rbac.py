"""Test for the explicitly-named bug - employee_performance exposed
every employee's task/hours/overtime data to any authenticated role,
with zero permission check."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_master_sees_all_employee_performance(client, test_user):
    _login(client, test_user)
    client.post("/api/employees/", json={"name": "Perf RBAC Employee One"})
    client.post("/api/employees/", json={"name": "Perf RBAC Employee Two"})

    resp = client.get("/api/dashboard/staff").json()
    names = [p["employee"] for p in resp["employee_performance"]]
    assert "Perf RBAC Employee One" in names
    assert "Perf RBAC Employee Two" in names


def test_employee_sees_only_own_performance(client, test_user, db_session):
    _login(client, test_user)
    other = client.post("/api/employees/", json={"name": "Perf RBAC Other Employee"}).json()
    own = client.post("/api/employees/", json={"name": "Perf RBAC Own Employee"}).json()
    user = User(
        username="perfrbacuser", email="perfrbacuser@example.com", full_name="Perf RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=own["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "perfrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/dashboard/staff").json()
    names = [p["employee"] for p in resp["employee_performance"]]
    assert "Perf RBAC Own Employee" in names
    assert "Perf RBAC Other Employee" not in names
