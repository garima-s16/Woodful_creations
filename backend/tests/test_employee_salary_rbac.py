"""Tests for the most severe gap found in this whole thread -
Employee.monthly_salary/daily_wage were exposed to any authenticated
role via list_employees/get_employee, completely bypassing the Salary
Slips restriction fixed earlier."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_master_sees_all_employee_salaries(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Salary RBAC Master Employee", "monthly_salary": "25000",
    }).json()
    resp = client.get(f"/api/employees/{employee['id']}").json()
    assert resp["monthly_salary"] is not None
    assert resp["daily_wage"] is not None


def test_employee_cannot_see_another_employees_salary(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Salary RBAC Other Employee", "monthly_salary": "30000",
    }).json()
    employee = client.post("/api/employees/", json={
        "name": "Salary RBAC Self Employee", "monthly_salary": "20000",
    }).json()
    user = User(
        username="empsalaryrbacuser", email="empsalaryrbacuser@example.com", full_name="Emp Salary RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "empsalaryrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/employees/{other_employee['id']}").json()
    assert resp["monthly_salary"] is None
    assert resp["daily_wage"] is None
    # Non-financial directory info remains visible.
    assert resp["name"] == "Salary RBAC Other Employee"
    assert "designation" in resp


def test_employee_can_see_own_salary(client, test_user, db_session):
    """The specific nuance of this fix - own record stays visible,
    matching "employee can access only their OWN confidential HR data",
    not a blanket denial of all salary info."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Salary RBAC Own Employee", "monthly_salary": "22000",
    }).json()
    user = User(
        username="empsalaryownrbacuser", email="empsalaryownrbacuser@example.com", full_name="Emp Salary Own RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "empsalaryownrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/employees/{employee['id']}").json()
    assert resp["monthly_salary"] is not None
    assert float(resp["monthly_salary"]) == 22000.0
    assert resp["daily_wage"] is not None


def test_employee_list_view_redacts_others_but_shows_own_salary(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Salary RBAC List Other Employee", "monthly_salary": "35000",
    }).json()
    employee = client.post("/api/employees/", json={
        "name": "Salary RBAC List Self Employee", "monthly_salary": "18000",
    }).json()
    user = User(
        username="empsalarylistrbacuser", email="empsalarylistrbacuser@example.com", full_name="Emp Salary List RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "empsalarylistrbacuser@example.com", "password": "EmpPass1!"})

    employees = client.get("/api/employees/").json()
    other_row = next(e for e in employees if e["id"] == other_employee["id"])
    own_row = next(e for e in employees if e["id"] == employee["id"])
    assert other_row["monthly_salary"] is None
    assert own_row["monthly_salary"] is not None
