"""Salary slip tests: creation/computation (net salary, working/paid
days validation, duplicate rejection), PDF generation across various
field-completeness scenarios, ownership-based RBAC (an employee sees
only their own slip, master sees all), and the unlinked-non-master
defense-in-depth regression guard."""
import re
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login

BUSINESS_ID_PATTERN = re.compile(r"^[A-Z0-9]{10}$")


def _create_logged_in_employee(client, db_session, employee_name, username, email):
    """Unlike _create_employee below (which only creates the employee
    record), this also creates and logs in as a real User account tied
    to that employee - needed for RBAC tests that check "own records"
    access by actually being logged in as the employee in question."""
    employee = client.post("/api/employees/", json={
        "name": employee_name, "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200
    return employee


def _create_employee(client, name="Salary Slip Test Employee"):
    resp = client.post("/api/employees/", json={
        "name": name, "designation": "Carpenter", "department": "Production", "monthly_salary": "26000.00",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


def test_create_salary_slip_end_to_end(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "20000.00", "da": "2000.00", "hra": "3000.00", "overtime_amount": "500.00",
        "pf_deduction": "1200.00", "tds_deduction": "0.00", "other_deductions": "0.00",
    })
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    # 20000 + 2000 + 3000 + 500 - 1200 = 24300
    assert float(body["net_salary"]) == 24300.0


def test_salary_slip_defaults_working_and_paid_days(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "September", "year": "2026", "basic": "20000.00",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert float(body["working_days"]) == 26.0
    assert float(body["paid_days"]) == 26.0


def test_salary_slip_rejects_paid_days_exceeding_working_days(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "October", "year": "2026",
        "working_days": "20", "paid_days": "25", "basic": "20000.00",
    })
    assert resp.status_code == 422


def test_salary_slip_rejects_zero_or_negative_days(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "November", "year": "2026",
        "working_days": "0", "paid_days": "0", "basic": "20000.00",
    })
    assert resp.status_code == 422


def test_duplicate_salary_slip_rejected(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)
    payload = {"employee_id": employee_id, "month": "December", "year": "2026", "basic": "20000.00"}

    first = client.post("/api/salary-slips/", json=payload)
    assert first.status_code == 201
    second = client.post("/api/salary-slips/", json=payload)
    assert second.status_code == 400


def test_salary_slip_update_rejects_paid_days_exceeding_working_days(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)
    create = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "January", "year": "2027",
        "working_days": "26", "paid_days": "26", "basic": "20000.00",
    })
    slip_id = create.json()["id"]

    resp = client.put(f"/api/salary-slips/{slip_id}", json={"working_days": "10"})
    assert resp.status_code == 400


def test_salary_slip_pdf_generates_successfully_with_minimal_fields(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)
    create = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "February", "year": "2027", "basic": "20000.00",
    })
    slip_id = create.json()["id"]

    resp = client.get(f"/api/reports/salary-slips/{slip_id}.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 0


def test_employee_can_view_own_salary_slip(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Salary RBAC Own Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "8", "year": "2026", "working_days": "26", "paid_days": "26",
        "basic": "15000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    }).json()

    user = User(
        username="salaryownrbacuser", email="salaryownrbacuser@example.com", full_name="Salary Own",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "salaryownrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/salary-slips/{slip['id']}")
    assert resp.status_code == 200


def test_employee_cannot_view_another_employees_salary_slip(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Salary RBAC Other Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": other_employee["id"], "month": "8", "year": "2026", "working_days": "26", "paid_days": "26",
        "basic": "15000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    }).json()

    _create_logged_in_employee(client, db_session, "Salary RBAC Requester", "salaryotherrbacuser", "salaryotherrbacuser@example.com")
    resp = client.get(f"/api/salary-slips/{slip['id']}")
    assert resp.status_code == 403


def test_employee_cannot_create_salary_slip(client, test_user, db_session):
    """Creation stays master-only - viewing opened up, editing did not."""
    _login(client, test_user)
    employee = _create_logged_in_employee(client, db_session, "Salary RBAC Create Employee", "salarycreaterbacuser", "salarycreaterbacuser@example.com")
    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "9", "year": "2026", "working_days": "26", "paid_days": "26",
        "basic": "15000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    })
    assert resp.status_code == 403

# ===========================================================================
# Salary slip PDF export (from test_salary_slip_pdf_generation.py)
# ===========================================================================

"""Tests that the salary slip PDF endpoint actually generates a valid
PDF response for real stored data, and that access to it is correctly
scoped: master can download any slip, an employee can download their
own, and cannot download another employee's - a real inconsistency
found during a full-backend systematic sweep, since get_salary_slip
(the API for the same underlying record) had already been widened to
let an employee view their own, but the PDF export was still
master-only."""


def test_salary_slip_pdf_generates_successfully(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "PDF Gen Test Employee", "monthly_salary": "20000",
        "designation": "Carpenter", "department": "Assembly",
        "pan": "ABCPT1234A", "uan": "100200300999",
        "bank_name": "State Bank of India", "bank_account_number": "998877661234",
        "tax_regime": "New",
    }).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "9500", "da": "500", "hra": "6000", "overtime_amount": "1500",
        "pf_deduction": "1140", "tds_deduction": "0", "other_deductions": "300",
    }).json()

    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000  # a genuine PDF, not an empty/error stub


def test_salary_slip_pdf_generates_with_no_leave_history(client, test_user):
    """An employee with zero leave records must not crash the PDF -
    the Leave Balance section should degrade gracefully."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "PDF Gen No Leave Employee", "monthly_salary": "18000",
    }).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "9000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    }).json()

    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
    assert resp.status_code == 200


def test_salary_slip_pdf_generates_with_missing_employee_payroll_fields(client, test_user):
    """PAN/UAN/bank details are all optional - a slip for an employee
    without them must still generate cleanly (shown as '-')."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "PDF Gen Minimal Employee", "monthly_salary": "14000",
    }).json()
    assert employee.get("pan") is None
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "7000", "da": "0", "hra": "3000", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "200",
    }).json()

    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
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

# ===========================================================================
# Employee salary field RBAC (from test_client_hr_and_export_features.py)
# ===========================================================================
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


def test_unlinked_non_master_user_sees_no_salary_slips(client, test_user, db_session):
    """Unlinked non-master users must get zero records, not every
    employee's salary slips - the most sensitive instance of this
    class of bug, since it's compensation data."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Unlinked Salary Other Employee"}).json()
    client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "20000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    })
    user = User(
        username="unlinkedsalaryuser", email="unlinkedsalaryuser@example.com", full_name="Unlinked Salary User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "unlinkedsalaryuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/salary-slips/")
    assert resp.status_code == 200
    assert resp.json() == []

# ===========================================================================
# Salary slip net computation (from test_admin_and_ai_gateway.py's
# former test_estimates_hr.py section)
# ===========================================================================
def test_salary_slip_computes_net(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={
        "employee_code": "EMP-SAL", "name": "Salary Test Employee", "monthly_salary": "20000.00",
    })
    employee_id = resp.json()["id"]

    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee_id, "month": "August", "year": "2026",
        "basic": "15000.00", "da": "2000.00", "hra": "3000.00",
        "pf_deduction": "1800.00", "tds_deduction": "0.00",
    })
    assert resp.status_code == 201
    assert float(resp.json()["net_salary"]) == 18200.0
