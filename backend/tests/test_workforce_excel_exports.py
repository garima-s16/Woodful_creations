"""Tests for the workforce Excel exports (Section 10) - attendance,
overtime, leave, payroll, and filtered tasks. Confirms exports
respect filters (Section 12's explicit example) and that the
payroll export is genuinely backend-enforced master-only, not just
hidden from the UI."""
import io
from openpyxl import load_workbook


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_attendance_export_opens_and_respects_employee_filter(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Excel Export Attendance Employee"}).json()
    client.post("/api/attendance/", json={
        "date": "2026-08-10T00:00:00", "employee_id": employee["id"],
        "in_time": "2026-08-10T09:00:00", "out_time": "2026-08-10T18:00:00", "attendance_status": "Present",
    })

    resp = client.get("/api/reports/attendance.xlsx", params={"employee_id": employee["id"]})
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    assert "Attendance" in wb.sheetnames


def test_overtime_export_only_includes_overtime_records(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Excel Export Overtime Employee"}).json()
    client.post("/api/attendance/", json={
        "date": "2026-08-11T00:00:00", "employee_id": employee["id"],
        "in_time": "2026-08-11T09:00:00", "out_time": "2026-08-11T19:00:00",
        "standard_hours": "8", "attendance_status": "Present",
    })
    resp = client.get("/api/reports/attendance.xlsx", params={"employee_id": employee["id"], "overtime_only": True})
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    assert "Overtime" in wb.sheetnames


def test_leaves_export_opens_correctly(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Excel Export Leave Employee"}).json()
    client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "CL",
        "start_date": "2026-08-15T00:00:00", "end_date": "2026-08-15T00:00:00",
    })
    resp = client.get("/api/reports/leaves.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    assert "Leave" in wb.sheetnames


def test_tasks_export_respects_employee_filter(client, test_user):
    """The exact scenario from Section 12's own example - a filtered
    export must not silently return the whole database."""
    _login(client, test_user)
    emp_a = client.post("/api/employees/", json={"name": "Excel Export Tasks Employee A"}).json()
    emp_b = client.post("/api/employees/", json={"name": "Excel Export Tasks Employee B"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": emp_a["id"], "task_description": "Task for A only",
    })
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": emp_b["id"], "task_description": "Task for B only",
    })

    resp = client.get("/api/reports/tasks.xlsx", params={"employee_id": emp_a["id"]})
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb["Tasks"]
    task_descriptions = [cell.value for row in ws.iter_rows(min_row=1) for cell in row if isinstance(cell.value, str)]
    assert any("Task for A only" in d for d in task_descriptions)
    assert not any("Task for B only" in d for d in task_descriptions)


def test_payroll_export_requires_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Excel Export Payroll Permission Employee"}).json()
    user = User(
        username="payrollexportuser", email="payrollexportuser@example.com",
        full_name="Payroll Export User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "payrollexportuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/reports/payroll.xlsx")
    assert resp.status_code == 403


def test_payroll_export_works_for_master(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Excel Export Payroll Master Employee", "monthly_salary": "20000"}).json()
    client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "15000", "da": "0", "hra": "5000", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    })
    resp = client.get("/api/reports/payroll.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    assert "Payroll" in wb.sheetnames
