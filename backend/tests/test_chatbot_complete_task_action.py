"""Tests for the chatbot's task-completion action - a real action
(direct execution, not just a query), reusing the same ownership rule
as the real endpoint, resolved from page context rather than a
separate chat-only permission system."""
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


def test_mark_this_done_completes_own_task_with_context(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Chat Complete Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Sand the panels",
    }).json()
    _create_employee_user(client, db_session, employee["id"], "chatcompleteuser", "chatcompleteuser@example.com")

    resp = client.post("/api/chat/", json={
        "message": "Mark this task as done",
        "context": {"record_type": "task", "record_id": task["id"]},
    })
    assert resp.status_code == 200
    assert "done" in resp.json()["response"].lower()

    updated = client.get(f"/api/daily-tasks/{task['id']}").json()
    assert updated["status"] == "DONE"
    assert updated["completion_percent"] == 100


def test_mark_this_done_deep_link_uses_correct_route(client, test_user):
    """Regression test for a real broken-link bug found this turn -
    the action_path/record path must point at the actual route
    (/daily-tasks/:id), not a nonexistent /tasks/:id."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Chat Link Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Check the link",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "mark this done",
        "context": {"record_type": "task", "record_id": task["id"]},
    })
    records = resp.json()["records"]
    assert records[0]["path"] == f"/daily-tasks/{task['id']}"


def test_employee_cannot_complete_unrelated_task_via_chat(client, test_user, db_session):
    _login(client, test_user)
    owner = client.post("/api/employees/", json={"name": "Chat Complete Owner"}).json()
    other = client.post("/api/employees/", json={"name": "Chat Complete Other"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": owner["id"], "task_description": "Owner's task",
    }).json()
    _create_employee_user(client, db_session, other["id"], "chatcompleteotheruser", "chatcompleteotheruser@example.com")

    resp = client.post("/api/chat/", json={
        "message": "mark this done",
        "context": {"record_type": "task", "record_id": task["id"]},
    })
    assert "only complete your own" in resp.json()["response"].lower()

    unchanged = client.get(f"/api/daily-tasks/{task['id']}").json()
    assert unchanged["status"] != "DONE"


def test_mark_this_done_without_context_asks_for_clarification(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "mark this done"})
    assert "not sure which task" in resp.json()["response"].lower()


def test_master_can_complete_any_task_via_chat(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Chat Complete Master Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"], "task_description": "Any task",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "this is done",
        "context": {"record_type": "task", "record_id": task["id"]},
    })
    updated = client.get(f"/api/daily-tasks/{task['id']}").json()
    assert updated["status"] == "DONE"
