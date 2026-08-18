"""Tests for Attendance access control - structurally the same gap as
Leaves (an unrestricted employee_id filter), fixed the same way."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


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
