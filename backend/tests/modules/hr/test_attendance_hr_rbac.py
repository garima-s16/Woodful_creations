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
