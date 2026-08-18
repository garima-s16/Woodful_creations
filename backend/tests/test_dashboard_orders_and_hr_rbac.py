"""Tests for this turn's corrections: /api/dashboard/orders financial
redaction (a real, previously-untouched gap), Leaves/Salary Slips
own-records-only enforcement, and the matching chatbot fix."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee(client, db_session, employee_name, username, email):
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


def test_master_sees_orders_dashboard_financials(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/orders").json()
    assert resp["total_order_value"] is not None
    assert resp["total_received"] is not None
    assert resp["pending_payment"] is not None


def test_employee_orders_dashboard_financials_are_null(client, test_user, db_session):
    """The real, previously-untouched gap found this turn."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Orders Dash RBAC Client"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "50000.00", "advance": "0",
    })

    _create_employee(client, db_session, "Orders Dash RBAC Employee", "ordersdashrbacuser", "ordersdashrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    assert resp["total_order_value"] is None
    assert resp["total_received"] is None
    assert resp["pending_payment"] is None
    # Non-financial fields remain real.
    assert resp["active_orders"] is not None
    assert resp["order_pipeline"] is not None


def test_employee_top_orders_money_fields_are_null_but_status_visible(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Top Orders RBAC Client"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "70000.00", "advance": "0",
    })

    _create_employee(client, db_session, "Top Orders RBAC Employee", "toporderrbacuser", "toporderrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    match = next(o for o in resp["top_orders"] if o["client"] == "Top Orders RBAC Client")
    assert match["order_value"] is None
    assert match["received"] is None
    assert match["pending"] is None
    assert match["status"] is not None


def test_employee_order_profitability_is_empty_not_leaked(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "Profit Dash RBAC Employee", "profitdashrbacuser", "profitdashrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    assert resp["order_profitability"] == []


def test_employee_cannot_view_another_employees_leaves(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Leave RBAC Other Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/leaves/", json={
        "employee_id": other_employee["id"], "leave_type": "Sick", "start_date": "2026-08-01T00:00:00", "end_date": "2026-08-02T00:00:00",
    })

    _create_employee(client, db_session, "Leave RBAC Self Employee", "leaverbacuser", "leaverbacuser@example.com")
    resp = client.get("/api/leaves/", params={"employee_id": other_employee["id"]})
    assert resp.status_code == 403


def test_employee_can_view_own_leaves(client, test_user, db_session):
    _login(client, test_user)
    employee = _create_employee(client, db_session, "Leave RBAC Own Employee", "leaveownrbacuser", "leaveownrbacuser@example.com")
    _login(client, test_user)
    client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "Casual", "start_date": "2026-08-05T00:00:00", "end_date": "2026-08-05T00:00:00",
    })

    client.post("/api/auth/login", json={"identifier": "leaveownrbacuser@example.com", "password": "EmpPass1!"})
    resp = client.get("/api/leaves/")
    assert resp.status_code == 200
    assert all(l["employee_id"] == employee["id"] for l in resp.json())


def test_employee_cannot_request_leave_for_someone_else(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Leave RBAC Impersonation Target", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    _create_employee(client, db_session, "Leave RBAC Impersonator", "leaveimpersonateuser", "leaveimpersonateuser@example.com")

    resp = client.post("/api/leaves/", json={
        "employee_id": other_employee["id"], "leave_type": "Sick", "start_date": "2026-08-10T00:00:00", "end_date": "2026-08-10T00:00:00",
    })
    assert resp.status_code == 403


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

    _create_employee(client, db_session, "Salary RBAC Requester", "salaryotherrbacuser", "salaryotherrbacuser@example.com")
    resp = client.get(f"/api/salary-slips/{slip['id']}")
    assert resp.status_code == 403


def test_employee_cannot_create_salary_slip(client, test_user, db_session):
    """Creation stays master-only - viewing opened up, editing did not."""
    _login(client, test_user)
    employee = _create_employee(client, db_session, "Salary RBAC Create Employee", "salarycreaterbacuser", "salarycreaterbacuser@example.com")
    resp = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "9", "year": "2026", "working_days": "26", "paid_days": "26",
        "basic": "15000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    })
    assert resp.status_code == 403


def test_chatbot_employee_cannot_view_another_employees_leaves(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "ChatLeaveRbacTarget", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/leaves/", json={
        "employee_id": other_employee["id"], "leave_type": "Sick", "start_date": "2026-08-01T00:00:00", "end_date": "2026-08-02T00:00:00",
    })

    _create_employee(client, db_session, "Chat Leave RBAC Requester", "chatleaverbacuser", "chatleaverbacuser@example.com")
    resp = client.post("/api/chat/", json={"message": "Show ChatLeaveRbacTarget's leaves"})
    assert "own leave records" in resp.json()["response"].lower()


def test_chatbot_master_can_view_named_employees_leaves(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "ChatLeaveRbacMasterTarget", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "Casual", "start_date": "2026-08-03T00:00:00", "end_date": "2026-08-03T00:00:00",
    })

    resp = client.post("/api/chat/", json={"message": "Show ChatLeaveRbacMasterTarget's leaves"})
    assert "own leave records" not in resp.json()["response"].lower()


def test_chatbot_employee_can_view_own_leaves(client, test_user, db_session):
    _login(client, test_user)
    employee = _create_employee(client, db_session, "Chat Leave RBAC Self", "chatleaveselfrbacuser", "chatleaveselfrbacuser@example.com")
    _login(client, test_user)
    client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "Casual", "start_date": "2026-08-04T00:00:00", "end_date": "2026-08-04T00:00:00",
    })

    client.post("/api/auth/login", json={"identifier": "chatleaveselfrbacuser@example.com", "password": "EmpPass1!"})
    resp = client.post("/api/chat/", json={"message": "Show my leaves"})
    assert resp.status_code == 200
    assert "own leave records" not in resp.json()["response"].lower()
