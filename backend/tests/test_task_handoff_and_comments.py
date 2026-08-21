"""Tests for the task handoff system - Complete & Assign Next,
comments, subtasks, and the blocked-reason self-service fix."""
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


def test_complete_and_assign_next_creates_linked_task(client, test_user):
    _login(client, test_user)
    emp_a = client.post("/api/employees/", json={"name": "Handoff Employee A"}).json()
    emp_b = client.post("/api/employees/", json={"name": "Handoff Employee B"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": emp_a["id"], "task_description": "Measure wardrobe",
    }).json()

    resp = client.post(f"/api/daily-tasks/{task['id']}/complete-and-assign-next", json={
        "next_employee_id": emp_b["id"], "next_task_description": "Prepare cutting drawing",
        "next_due_date": "2026-08-20T00:00:00",
    })
    assert resp.status_code == 201
    next_task = resp.json()
    assert next_task["previous_task_id"] == task["id"]
    assert next_task["employee_id"] == emp_b["id"]

    original = client.get(f"/api/daily-tasks/{task['id']}").json()
    assert original["status"] == "Completed"
    assert original["completion_percent"] == 100


def test_original_task_not_overwritten_by_handoff(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Handoff No Overwrite Employee"}).json()
    next_employee = client.post("/api/employees/", json={"name": "Handoff No Overwrite Next"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Original description",
    }).json()

    client.post(f"/api/daily-tasks/{task['id']}/complete-and-assign-next", json={
        "next_employee_id": next_employee["id"], "next_task_description": "Different description",
        "next_due_date": "2026-08-20T00:00:00",
    })

    original = client.get(f"/api/daily-tasks/{task['id']}").json()
    assert original["task_description"] == "Original description"


def test_add_and_list_task_comments(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Comment Test Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Cut panels",
    }).json()

    resp = client.post(f"/api/daily-tasks/{task['id']}/comments", json={"text": "Ready for cutting."})
    assert resp.status_code == 201

    comments = client.get(f"/api/daily-tasks/{task['id']}/comments").json()
    assert len(comments) == 1
    assert comments[0]["text"] == "Ready for cutting."


def test_subtask_links_to_parent(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Subtask Test Employee"}).json()
    parent = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Wardrobe - full build",
    }).json()
    sub = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Assembly",
        "parent_task_id": parent["id"],
    }).json()
    assert sub["parent_task_id"] == parent["id"]


def test_employee_can_set_status_and_block_reason_together(client, test_user, db_session):
    """The explicit brief requirement - mark BLOCKED with a reason -
    previously impossible since only status was self-service."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Block Reason Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Apply laminate",
    }).json()
    _create_employee_user(client, db_session, employee["id"], "blockreasonuser", "blockreasonuser@example.com")

    resp = client.put(f"/api/daily-tasks/{task['id']}", json={
        "status": "On Hold", "delay_reason": "Waiting for laminate",
    })
    assert resp.status_code == 200
    assert resp.json()["delay_reason"] == "Waiting for laminate"


def test_employee_notified_when_task_blocked(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Block Notif Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Sand panels",
    }).json()
    _create_employee_user(client, db_session, employee["id"], "blocknotifuser", "blocknotifuser@example.com")

    client.put(f"/api/daily-tasks/{task['id']}", json={"status": "On Hold", "delay_reason": "Material unavailable"})

    notifications = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "TASK_BLOCKED" for n in notifications)


def test_created_by_set_on_task_creation(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Created By Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Install hardware",
    }).json()
    assert task["created_by"] == "test@example.com"


def test_employee_cannot_complete_unrelated_task(client, test_user, db_session):
    """The explicit brief requirement - an employee must not be able to
    use Complete & Assign Next on a task assigned to someone else."""
    _login(client, test_user)
    owner = client.post("/api/employees/", json={"name": "Handoff Owner Employee"}).json()
    other_employee = client.post("/api/employees/", json={"name": "Handoff Unrelated Employee"}).json()
    next_employee = client.post("/api/employees/", json={"name": "Handoff Unrelated Next"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": owner["id"], "task_description": "Owner's task",
    }).json()
    _create_employee_user(client, db_session, other_employee["id"], "handoffunrelateduser", "handoffunrelateduser@example.com")

    resp = client.post(f"/api/daily-tasks/{task['id']}/complete-and-assign-next", json={
        "next_employee_id": next_employee["id"], "next_task_description": "Should not be created",
        "next_due_date": "2026-08-20T00:00:00",
    })
    assert resp.status_code == 403

    unchanged = client.get(f"/api/daily-tasks/{task['id']}")
    assert unchanged.status_code == 200
    assert unchanged.json()["status"] != "DONE"


def test_employee_can_complete_and_assign_next_for_own_task(client, test_user, db_session):
    _login(client, test_user)
    owner = client.post("/api/employees/", json={"name": "Handoff Self Owner"}).json()
    next_employee = client.post("/api/employees/", json={"name": "Handoff Self Next"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": owner["id"], "task_description": "My own task",
    }).json()
    _create_employee_user(client, db_session, owner["id"], "handoffselfuser", "handoffselfuser@example.com")

    resp = client.post(f"/api/daily-tasks/{task['id']}/complete-and-assign-next", json={
        "next_employee_id": next_employee["id"], "next_task_description": "Handed off task",
        "next_due_date": "2026-08-20T00:00:00",
    })
    assert resp.status_code == 201
