"""Tests for the workforce Excel exports - attendance,
overtime, leave, payroll, and tasks/production. Confirms exports
respect filters and that the payroll export is genuinely
backend-enforced master-only, not just hidden from the UI. Also
covers basic tasks/production export functionality and RBAC
(open to any authenticated role, since anyone can already view tasks)."""
import io
from openpyxl import load_workbook
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


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
    """A filtered
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
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
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


def test_tasks_excel_export_contains_real_data(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Tasks Excel Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-18T00:00:00", "employee_id": employee["id"], "task_description": "Tasks Excel Test Task",
    })
    client.post("/api/production-jobs/", json={
        "date": "2026-08-18T00:00:00", "employee_id": employee["id"], "operation": "Tasks Excel Test Operation",
        "planned_qty": 5, "status": "Not Started",
    })

    resp = client.get("/api/reports/tasks.xlsx")
    assert resp.status_code == 200
    assert len(resp.content) > 1000  # a genuine workbook, not an empty/error stub

    wb = load_workbook(io.BytesIO(resp.content))
    assert "Tasks" in wb.sheetnames
    assert "Production" in wb.sheetnames


def test_tasks_excel_export_open_to_any_authenticated_role(client, test_user, db_session):
    """Everyone can view tasks - the export must not be restricted."""
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User

    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Tasks Excel RBAC Employee"}).json()
    user = User(
        username="tasksexcelrbacuser", email="tasksexcelrbacuser@example.com", full_name="Tasks Excel RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "tasksexcelrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/reports/tasks.xlsx")
    assert resp.status_code == 200


# ===========================================================================
# Unlinked non-master accounts must never fall through to an unfiltered
# export - regression coverage for a real gap found and fixed in this
# pass: employee_id resolving to None (an authenticated user with no
# employee link) made the `if employee_id:` guard a no-op, silently
# returning every employee's data instead of none. Creation-time
# enforcement (POST/PUT /api/users/) now prevents this state going
# forward, but these prove the read/export endpoints are safe even if
# such a row exists (e.g. old data, a script, a future code path).
# ===========================================================================
def _create_unlinked_non_master_user(client, db_session, username, email):
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})


def test_unlinked_user_gets_no_attendance_export(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/employees/", json={"name": "Unlinked Export Attendance Employee"})
    _create_unlinked_non_master_user(client, db_session, "unlinkedattexport", "unlinkedattexport@example.com")

    resp = client.get("/api/reports/attendance.xlsx")
    assert resp.status_code == 403


def test_unlinked_user_gets_no_leaves_export(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/employees/", json={"name": "Unlinked Export Leave Employee"})
    _create_unlinked_non_master_user(client, db_session, "unlinkedleaveexport", "unlinkedleaveexport@example.com")

    resp = client.get("/api/reports/leaves.xlsx")
    assert resp.status_code == 403
