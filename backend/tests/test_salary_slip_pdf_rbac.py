"""Test for an inconsistency found during a full-backend systematic
sweep - the salary slip PDF export was still master-only even
though get_salary_slip (the API for the same underlying record) had
already been widened to let an employee view their own."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_employee_can_download_own_salary_slip_pdf(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Salary PDF RBAC Own Employee", "monthly_salary": "20000",
    }).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "8", "year": "2026", "working_days": "26", "paid_days": "26",
        "basic": "15000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    }).json()
    user = User(
        username="salarypdfownrbacuser", email="salarypdfownrbacuser@example.com", full_name="Salary PDF Own RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "salarypdfownrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
    assert resp.status_code == 200


def test_employee_cannot_download_another_employees_salary_slip_pdf(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Salary PDF RBAC Other Employee", "monthly_salary": "25000",
    }).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": other_employee["id"], "month": "8", "year": "2026", "working_days": "26", "paid_days": "26",
        "basic": "18000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    }).json()
    employee = client.post("/api/employees/", json={
        "name": "Salary PDF RBAC Requester", "monthly_salary": "18000",
    }).json()
    user = User(
        username="salarypdfotherrbacuser", email="salarypdfotherrbacuser@example.com", full_name="Salary PDF Other RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "salarypdfotherrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
    assert resp.status_code == 403


def test_master_can_download_any_salary_slip_pdf(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Salary PDF RBAC Master Employee", "monthly_salary": "20000",
    }).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "8", "year": "2026", "working_days": "26", "paid_days": "26",
        "basic": "15000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    }).json()

    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
    assert resp.status_code == 200
