"""Tests for the attendance-to-payroll suggestion endpoint (workforce
brief, Item 7 - "connect attendance + overtime + salary to the
existing payroll architecture" without rebuilding it). GET only,
never persists anything - the master reviews before saving an
actual salary slip."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_attendance_summary_computes_paid_days_and_overtime(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Payroll Summary Test Employee", "monthly_salary": "20800"}).json()

    client.post("/api/attendance/", json={
        "date": "2026-08-03T00:00:00", "employee_id": employee["id"],
        "in_time": "2026-08-03T09:00:00", "out_time": "2026-08-03T19:00:00",
        "standard_hours": "8", "attendance_status": "Present",
    })
    client.post("/api/attendance/", json={
        "date": "2026-08-04T00:00:00", "employee_id": employee["id"],
        "in_time": "2026-08-04T09:00:00", "out_time": "2026-08-04T13:00:00",
        "standard_hours": "8", "attendance_status": "Half Day",
    })

    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "August", "year": "2026",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["records_found"] == 2
    assert data["suggested_paid_days"] == 1.5  # 1 (Present) + 0.5 (Half Day)
    assert data["total_overtime_hours"] == 2.0  # 10 worked - 8 standard on the first day
    assert data["suggested_overtime_amount"] > 0


def test_attendance_summary_requires_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Payroll Summary Permission Employee"}).json()
    user = User(
        username="payrollsummaryuser", email="payrollsummaryuser@example.com",
        full_name="Payroll Summary User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "payrollsummaryuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "August", "year": "2026",
    })
    assert resp.status_code == 403


def test_attendance_summary_rejects_invalid_month(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Payroll Summary Invalid Month Employee"}).json()
    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "Augsut", "year": "2026",
    })
    assert resp.status_code == 400


def test_attendance_summary_returns_zero_for_no_records(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Payroll Summary No Records Employee"}).json()
    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "January", "year": "2026",
    })
    assert resp.status_code == 200
    assert resp.json()["records_found"] == 0
    assert resp.json()["suggested_paid_days"] == 0
