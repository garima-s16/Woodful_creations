"""HR-domain tests: attendance access control (structurally the same
gap as Leaves - an unrestricted employee_id filter - fixed the same
way), payroll attendance summary, working-calendar/weekday
configuration, and employee directory CRUD/search/export."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def test_employee_cannot_view_another_employees_attendance(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Attendance RBAC Other Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/attendance/", json={
        "date": "2026-08-16T00:00:00", "employee_id": other_employee["id"], "attendance_status": "Present",
    })

    employee = client.post("/api/employees/", json={
        "name": "Attendance RBAC Self Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username="attendancerbacuser", email="attendancerbacuser@example.com", full_name="Attendance RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "attendancerbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/attendance/", params={"employee_id": other_employee["id"]})
    assert resp.status_code == 403


def test_employee_can_view_own_attendance(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Attendance RBAC Own Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/attendance/", json={
        "date": "2026-08-16T00:00:00", "employee_id": employee["id"], "attendance_status": "Present",
    })
    user = User(
        username="attendanceownrbacuser", email="attendanceownrbacuser@example.com", full_name="Attendance Own RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "attendanceownrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/attendance/")
    assert resp.status_code == 200
    assert all(a["employee_id"] == employee["id"] for a in resp.json())


def test_employee_cannot_mark_attendance_for_someone_else(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Attendance RBAC Impersonation Target", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    employee = client.post("/api/employees/", json={
        "name": "Attendance RBAC Impersonator", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username="attendanceimpersonateuser", email="attendanceimpersonateuser@example.com", full_name="Impersonator",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "attendanceimpersonateuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/attendance/", json={
        "date": "2026-08-16T00:00:00", "employee_id": other_employee["id"], "attendance_status": "Present",
    })
    assert resp.status_code == 403


def test_employee_can_mark_own_attendance(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Attendance RBAC Self Mark Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username="attendanceselfmarkuser", email="attendanceselfmarkuser@example.com", full_name="Self Mark",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "attendanceselfmarkuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/attendance/", json={
        "date": "2026-08-16T00:00:00", "employee_id": employee["id"], "attendance_status": "Present",
    })
    assert resp.status_code == 201


def test_employee_cannot_correct_attendance_record(client, test_user, db_session):
    """Correction is a supervisory action, master-only."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Attendance RBAC Correction Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    record = client.post("/api/attendance/", json={
        "date": "2026-08-16T00:00:00", "employee_id": employee["id"], "attendance_status": "Present",
    }).json()
    user = User(
        username="attendancecorrectuser", email="attendancecorrectuser@example.com", full_name="Correction User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "attendancecorrectuser@example.com", "password": "EmpPass1!"})

    resp = client.put(f"/api/attendance/{record['id']}", json={"attendance_status": "Half Day"})
    assert resp.status_code == 403


def test_master_full_attendance_access_unaffected(client, test_user):
    """Backward compatibility - master retains full functionality."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Attendance RBAC Master Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    record = client.post("/api/attendance/", json={
        "date": "2026-08-16T00:00:00", "employee_id": employee["id"], "attendance_status": "Present",
    }).json()
    assert client.get("/api/attendance/").status_code == 200
    assert client.put(f"/api/attendance/{record['id']}", json={"attendance_status": "Half Day"}).status_code == 200

# ===========================================================================
# Payroll attendance summary (from test_auth_and_chatbot_misc.py)
# ===========================================================================
# ===========================================================================
def test_salary_days_matches_working_days_when_no_leave(client, test_user):
    """Family P0.43: Salary Days = actual configured working days in
    the month minus approved leave - with no leave, they're equal.
    February 2026 has 24 Monday-Saturday working days (28 calendar
    days, 4 Sundays) - deliberately not August's 26, to prove this is
    genuinely computed per-month, not a fixed assumption."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Salary Days No Leave Employee", "monthly_salary": "20800"}).json()

    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "February", "year": "2026",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["calendar_days"] == 28
    assert data["suggested_working_days"] == 24
    assert data["leave_days"] == 0
    assert data["salary_days"] == 24


def test_salary_days_subtracts_approved_leave_on_working_dates(client, test_user):
    """2026-02-05 and 2026-02-06 are a Thursday and Friday (real
    working dates) - both must be subtracted."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Salary Days Leave Employee", "monthly_salary": "20800"}).json()
    leave = client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "CL",
        "start_date": "2026-02-05T00:00:00", "end_date": "2026-02-06T00:00:00",
    }).json()
    client.put(f"/api/leaves/{leave['id']}", json={"status": "Approved"})

    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "February", "year": "2026",
    })
    data = resp.json()
    assert data["leave_days"] == 2
    assert data["salary_days"] == 22  # 24 - 2


def test_salary_days_ignores_pending_leave(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Salary Days Pending Leave Employee", "monthly_salary": "20800"}).json()
    client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "CL",
        "start_date": "2026-02-05T00:00:00", "end_date": "2026-02-06T00:00:00",
    })
    # Left as "Pending" - never approved.

    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "February", "year": "2026",
    })
    data = resp.json()
    assert data["leave_days"] == 0
    assert data["salary_days"] == 24


def test_salary_days_does_not_double_subtract_leave_on_sunday(client, test_user):
    """2026-02-01 is a Sunday - already not a working day, so an
    approved leave covering it must not reduce salary_days further."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Salary Days Sunday Leave Employee", "monthly_salary": "20800"}).json()
    leave = client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "CL",
        "start_date": "2026-02-01T00:00:00", "end_date": "2026-02-01T00:00:00",
    }).json()
    client.put(f"/api/leaves/{leave['id']}", json={"status": "Approved"})

    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "February", "year": "2026",
    })
    data = resp.json()
    assert data["leave_days"] == 0  # Sunday was never a working day to begin with
    assert data["salary_days"] == 24


def test_add_overtime_creates_record_when_none_exists(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Add Overtime New Record Employee", "monthly_salary": "20800"}).json()

    resp = client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-10T00:00:00"], "hours": "2", "mode": "add",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert float(body[0]["overtime_hours"]) == 2.0


def test_add_overtime_is_additive_not_replace(client, test_user):
    """The spec's own core rule: existing 2 + add 1 = 3, never a
    silent replace to 1."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Add Overtime Additive Employee", "monthly_salary": "20800"}).json()
    client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-10T00:00:00"], "hours": "2", "mode": "add",
    })

    resp = client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-10T00:00:00"], "hours": "1", "mode": "add",
    })
    assert float(resp.json()[0]["overtime_hours"]) == 3.0


def test_set_overtime_replaces_existing_value(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Set Overtime Replace Employee", "monthly_salary": "20800"}).json()
    client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-10T00:00:00"], "hours": "3", "mode": "add",
    })

    resp = client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-10T00:00:00"], "hours": "1", "mode": "set",
    })
    assert float(resp.json()[0]["overtime_hours"]) == 1.0


def test_add_overtime_multiple_dates_matches_spec_worked_example(client, test_user):
    """Spec's own example: A=1, B=2, C=0, D=3. Select A, B, D. Add 2.
    Result: A=3, B=4, C=0 (untouched), D=5."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Add Overtime Multi Date Employee", "monthly_salary": "20800"}).json()
    client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-10T00:00:00"], "hours": "1", "mode": "set",  # A
    })
    client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-11T00:00:00"], "hours": "2", "mode": "set",  # B
    })
    client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-13T00:00:00"], "hours": "3", "mode": "set",  # D
    })
    # C (2026-08-12) is deliberately never touched here.

    client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"],
        "dates": ["2026-08-10T00:00:00", "2026-08-11T00:00:00", "2026-08-13T00:00:00"],
        "hours": "2", "mode": "add",
    })

    resp = client.get("/api/attendance/", params={"employee_id": employee["id"]})
    by_date = {r["date"][:10]: float(r["overtime_hours"]) for r in resp.json()}
    assert by_date["2026-08-10"] == 3.0  # A: 1 + 2
    assert by_date["2026-08-11"] == 4.0  # B: 2 + 2
    assert "2026-08-12" not in by_date  # C: never created, untouched
    assert by_date["2026-08-13"] == 5.0  # D: 3 + 2


def test_add_overtime_requires_master(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Add Overtime RBAC Employee", "monthly_salary": "20800"}).json()
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    user = User(
        username="addovertimerbacuser", email="addovertimerbacuser@example.com", full_name="Add Overtime RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "addovertimerbacuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-10T00:00:00"], "hours": "2", "mode": "add",
    })
    assert resp.status_code == 403


def test_add_overtime_rejects_negative_hours(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Add Overtime Negative Employee", "monthly_salary": "20800"}).json()

    resp = client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-10T00:00:00"], "hours": "-1", "mode": "add",
    })
    assert resp.status_code == 422


def test_add_overtime_rejects_empty_dates_list(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Add Overtime Empty Dates Employee", "monthly_salary": "20800"}).json()

    resp = client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": [], "hours": "2", "mode": "add",
    })
    assert resp.status_code == 422


def test_add_overtime_rejects_unknown_employee(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/attendance/overtime", json={
        "employee_id": 999999, "dates": ["2026-08-10T00:00:00"], "hours": "2", "mode": "add",
    })
    assert resp.status_code == 404


def test_add_overtime_on_sunday_still_requires_explicit_value(client, test_user):
    """2026-08-02 is a Sunday - overtime still only comes from the
    explicit hours given, never implied by the day itself."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Add Overtime Sunday Employee", "monthly_salary": "20800"}).json()

    resp = client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-08-02T00:00:00"], "hours": "4", "mode": "add",
    })
    assert float(resp.json()[0]["overtime_hours"]) == 4.0


def test_payroll_summary_reflects_real_slip_and_advance_data(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Payroll Summary Real Data Employee", "monthly_salary": "20800"}).json()
    client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "September", "year": "2026", "basic": "20000",
    })

    resp = client.get("/api/salary-slips/payroll-summary", params={"month": "September", "year": "2026"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["month"] == "September"
    assert body["employees_with_slip"] == 1
    assert body["status_counts"]["draft"] == 1
    assert "salary_advances" in body


def test_payroll_summary_requires_master(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Payroll Summary RBAC Employee", "monthly_salary": "20800"}).json()
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    user = User(
        username="payrollsummaryrbacuser", email="payrollsummaryrbacuser@example.com", full_name="Payroll Summary RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "payrollsummaryrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/salary-slips/payroll-summary", params={"month": "September", "year": "2026"})
    assert resp.status_code == 403


def test_attendance_summary_computes_paid_days_and_overtime(client, test_user):
    """Family P0.43: overtime is a fact the Master explicitly records,
    not derived from in_time/out_time - the first record below has a
    10-hour clock span but overtime_hours is only counted because it
    is explicitly set to 2, not because it was computed from the
    clock times."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Payroll Summary Test Employee", "monthly_salary": "20800"}).json()

    client.post("/api/attendance/", json={
        "date": "2026-08-03T00:00:00", "employee_id": employee["id"],
        "in_time": "2026-08-03T09:00:00", "out_time": "2026-08-03T19:00:00",
        "standard_hours": "8", "attendance_status": "Present", "overtime_hours": "2",
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
    assert data["total_overtime_hours"] == 2.0  # explicitly recorded on the first day, not derived from clock times
    assert data["suggested_overtime_amount"] > 0


def test_overtime_is_zero_by_default_even_with_long_clock_span(client, test_user):
    """The core P0.43 correction: a long in/out span alone must never
    imply overtime - only an explicit value does."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "No Auto Overtime Employee", "monthly_salary": "20800"}).json()

    resp = client.post("/api/attendance/", json={
        "date": "2026-08-05T00:00:00", "employee_id": employee["id"],
        "in_time": "2026-08-05T08:00:00", "out_time": "2026-08-05T22:00:00",
        "standard_hours": "8", "attendance_status": "Present",
    })
    assert resp.status_code == 201
    assert float(resp.json()["overtime_hours"]) == 0.0


def test_sunday_work_does_not_imply_overtime_without_explicit_value(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Sunday No Auto Overtime Employee", "monthly_salary": "20800"}).json()

    # 2026-08-02 is a Sunday.
    resp = client.post("/api/attendance/", json={
        "date": "2026-08-02T00:00:00", "employee_id": employee["id"],
        "in_time": "2026-08-02T09:00:00", "out_time": "2026-08-02T17:00:00",
        "standard_hours": "8", "attendance_status": "Present",
    })
    assert resp.status_code == 201
    assert float(resp.json()["overtime_hours"]) == 0.0


def test_employee_cannot_set_overtime_hours_on_own_attendance(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Overtime RBAC Employee", "monthly_salary": "20800"}).json()
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    user = User(
        username="overtimerbacuser", email="overtimerbacuser@example.com", full_name="Overtime RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "overtimerbacuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/attendance/", json={
        "date": "2026-08-06T00:00:00", "employee_id": employee["id"],
        "attendance_status": "Present", "overtime_hours": "3",
    })
    assert resp.status_code == 403


def test_employee_can_mark_own_attendance_with_zero_overtime(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Overtime RBAC Zero Employee", "monthly_salary": "20800"}).json()
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    user = User(
        username="overtimerbaczerouser", email="overtimerbaczerouser@example.com", full_name="Overtime RBAC Zero User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "overtimerbaczerouser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/attendance/", json={
        "date": "2026-08-06T00:00:00", "employee_id": employee["id"], "attendance_status": "Present",
    })
    assert resp.status_code == 201


def test_master_can_set_overtime_hours(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Master Overtime Employee", "monthly_salary": "20800"}).json()

    resp = client.post("/api/attendance/", json={
        "date": "2026-08-06T00:00:00", "employee_id": employee["id"],
        "attendance_status": "Present", "overtime_hours": "3",
    })
    assert resp.status_code == 201
    assert float(resp.json()["overtime_hours"]) == 3.0


def test_negative_overtime_hours_rejected(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Negative Overtime Employee", "monthly_salary": "20800"}).json()

    resp = client.post("/api/attendance/", json={
        "date": "2026-08-06T00:00:00", "employee_id": employee["id"],
        "attendance_status": "Present", "overtime_hours": "-1",
    })
    assert resp.status_code == 422


def test_attendance_summary_requires_master(client, test_user, db_session):
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
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

# ===========================================================================
# Working calendar / weekday config (from test_client_hr_and_export_features.py)
# ===========================================================================
def test_default_weekday_config_is_mon_to_sat_working(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/working-calendar/weekdays")
    assert resp.status_code == 200
    weekdays = {w["weekday"]: w["is_working"] for w in resp.json()}
    assert weekdays["Monday"] is True
    assert weekdays["Saturday"] is True
    assert weekdays["Sunday"] is False


def test_working_days_differ_across_months(client, test_user):
    """The core requirement - February and August must not produce the
    same working-day count just because both used to default to 26."""
    _login(client, test_user)
    feb = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 2}).json()
    aug = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 8}).json()
    assert feb["working_days"] == 24  # 2026 is not a leap year: 28 days, 4 Sundays off
    assert aug["working_days"] == 26  # 31 days, 5 Sundays off
    assert feb["working_days"] != aug["working_days"]


def test_declared_holiday_reduces_working_days(client, test_user):
    _login(client, test_user)
    before = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 10}).json()["working_days"]

    client.post("/api/working-calendar/holidays", json={
        "date": "2026-10-02", "name": "Gandhi Jayanti", "is_working": False,
    })
    after = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 10}).json()["working_days"]
    assert after == before - 1


def test_special_working_day_increases_working_days(client, test_user):
    _login(client, test_user)
    # Find a Sunday in November 2026 to declare as a special working day
    before = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 11}).json()["working_days"]
    client.post("/api/working-calendar/holidays", json={
        "date": "2026-11-01", "name": "Special working Sunday", "is_working": True,
    })
    after = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 11}).json()["working_days"]
    assert after == before + 1


def test_weekday_config_requires_master_to_edit(client, test_user, db_session):
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    _login(client, test_user)
    weekday_id = client.get("/api/working-calendar/weekdays").json()[0]["id"]

    employee = client.post("/api/employees/", json={"name": "Calendar Permission Test Employee"}).json()
    user = User(
        username="calendarpermuser", email="calendarpermuser@example.com",
        full_name="Calendar Perm User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "calendarpermuser@example.com", "password": "EmpPass1!"})

    resp = client.put(f"/api/working-calendar/weekdays/{weekday_id}", json={"is_working": False})
    assert resp.status_code == 403


def test_attendance_summary_uses_actual_month_working_days(client, test_user):
    """Confirms the payroll suggestion endpoint genuinely uses the
    calendar-computed value, not a leftover fixed constant."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Payroll Calendar Integration Employee", "monthly_salary": "26000"}).json()

    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "February", "year": "2026",
    })
    assert resp.json()["suggested_working_days"] == 24

# ===========================================================================


# ===========================================================================
# Employee directory CRUD/search/export (from test_client_hr_and_export_features.py)
# ===========================================================================
def _create_employee(client, name="Directory Test Employee", **overrides):
    payload = {"name": name, "department": "Production", "monthly_salary": "30000.00"}
    payload.update(overrides)
    resp = client.post("/api/employees/", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_employee_directory_fields_persist(client, test_user):
    _login(client, test_user)
    emp = _create_employee(
        client, name="Pankaj Sharma", designation="Site Supervisor",
        email="pankaj@example.com", manager="Garima",
    )
    assert emp["designation"] == "Site Supervisor"
    assert emp["email"] == "pankaj@example.com"
    assert emp["manager"] == "Garima"


def test_employee_email_is_validated(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={
        "name": "Bad Email Employee", "email": "not-an-email", "monthly_salary": "20000.00",
    })
    assert resp.status_code == 422


def test_employee_search_by_name(client, test_user):
    _login(client, test_user)
    _create_employee(client, name="Pankaj Kumar")
    _create_employee(client, name="Nikhil Verma")

    resp = client.get("/api/employees/?search=Pankaj")
    assert resp.status_code == 200
    names = [e["name"] for e in resp.json()]
    assert "Pankaj Kumar" in names
    assert "Nikhil Verma" not in names


def test_employee_directory_export_returns_xlsx(client, test_user):
    _login(client, test_user)
    _create_employee(client, name="Export Test Employee")

    resp = client.get("/api/reports/employees.xlsx")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(resp.content) > 0


# ===========================================================================
# Unlinked non-master users must get zero records, not an unfiltered
# query result (see test_workforce_excel_exports.py's version of this
# regression note for the full explanation)
# ===========================================================================
def test_unlinked_non_master_user_sees_no_attendance(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={"name": "Unlinked Attendance Other Employee"}).json()
    client.post("/api/attendance/", json={
        "date": "2026-08-16T00:00:00", "employee_id": other_employee["id"], "attendance_status": "Present",
    })
    user = User(
        username="unlinkedattenduser", email="unlinkedattenduser@example.com", full_name="Unlinked Attendance User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "unlinkedattenduser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/attendance/")
    assert resp.status_code == 200
    assert resp.json() == []
