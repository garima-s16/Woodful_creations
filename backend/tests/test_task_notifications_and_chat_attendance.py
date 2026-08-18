"""Tests for two gaps closed this turn: task assignment/status-change
notifications (none existed before), and the chatbot's "my attendance"
query (previously fell through to a generic company-wide summary
instead of the employee's own record)."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee_user(client, db_session, employee_id, username, email):
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee_id, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200


def test_employee_notified_when_task_assigned(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Task Notif Employee"}).json()
    _create_employee_user(client, db_session, employee["id"], "tasknotifuser", "tasknotifuser@example.com")

    _login(client, test_user)
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-18T00:00:00", "employee_id": employee["id"], "task_description": "Sand the wardrobe panels",
    })

    client.post("/api/auth/login", json={"identifier": "tasknotifuser@example.com", "password": "EmpPass1!"})
    notifications = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "TASK_ASSIGNED" for n in notifications)


def test_employee_notified_on_task_status_change(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Task Status Notif Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-18T00:00:00", "employee_id": employee["id"], "task_description": "Cut panels",
    }).json()
    _create_employee_user(client, db_session, employee["id"], "taskstatusnotifuser", "taskstatusnotifuser@example.com")
    client.post("/api/auth/login", json={"identifier": "taskstatusnotifuser@example.com", "password": "EmpPass1!"})

    client.put(f"/api/daily-tasks/{task['id']}", json={"status": "In Progress"})

    notifications = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "TASK_STATUS_CHANGED" for n in notifications)


def test_chatbot_my_attendance_returns_own_records(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Chat Attendance Employee"}).json()
    client.post("/api/attendance/", json={
        "date": "2026-08-18T00:00:00", "employee_id": employee["id"], "attendance_status": "Present",
    })
    _create_employee_user(client, db_session, employee["id"], "chatattendanceuser", "chatattendanceuser@example.com")

    resp = client.post("/api/chat/", json={"message": "Show my attendance"})
    assert resp.status_code == 200
    assert resp.json()["records"]


def test_chatbot_my_attendance_no_records_message(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Chat No Attendance Employee"}).json()
    _create_employee_user(client, db_session, employee["id"], "chatnoattendanceuser", "chatnoattendanceuser@example.com")

    resp = client.post("/api/chat/", json={"message": "Show my attendance"})
    assert "no attendance records" in resp.json()["response"].lower()
