"""Regression tests for Priority 10 - the chatbot must resolve a real
employee name to their actual tasks via a live database query, never
hard-coded, and must resolve "my tasks" through the real
User.employee_id link, never by name matching."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_chatbot_finds_tasks_by_employee_name(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Pankaj Verma", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee["id"], "task_description": "Assemble cabinet frame",
    }).json()

    resp = client.post("/api/chat/", json={"message": "Show tasks for Pankaj."})
    assert resp.status_code == 200
    body = resp.json()
    match = next((r for r in body["records"] if r["path"] == f"/daily-tasks/{task['id']}"), None)
    assert match is not None
    assert match["label"] == "Assemble cabinet frame"


def test_chatbot_resolves_possessive_and_working_on_phrasing(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Sunita Rao", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee["id"], "task_description": "Polish tabletop",
    })

    for phrasing in ["What is Sunita working on?", "Show Sunita's tasks", "What tasks are assigned to Sunita?"]:
        resp = client.post("/api/chat/", json={"message": phrasing})
        assert resp.status_code == 200
        labels = [r["label"] for r in resp.json()["records"]]
        assert "Polish tabletop" in labels, f"failed for phrasing: {phrasing!r}"


def test_chatbot_overdue_tasks_for_named_employee(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Ramesh", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    overdue_task = client.post("/api/daily-tasks/", json={
        "date": "2026-01-01T00:00:00", "employee_id": employee["id"], "task_description": "Old overdue task",
    }).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-12-31T00:00:00", "employee_id": employee["id"], "task_description": "Future task",
    })

    resp = client.post("/api/chat/", json={"message": "Which of Ramesh's tasks are overdue?"})
    assert resp.status_code == 200
    paths = [r["path"] for r in resp.json()["records"]]
    assert f"/daily-tasks/{overdue_task['id']}" in paths
    assert len(resp.json()["records"]) == 1  # future task must not be included


def test_chatbot_my_tasks_uses_real_employee_link_not_name(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Totally Different Name", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee["id"], "task_description": "My linked task",
    }).json()
    linked_user = User(
        username="chattasksuser", email="chattasksuser@example.com", full_name="A Name That Does Not Match",
        password_hash=hash_password("ChatTasksPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(linked_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "chattasksuser@example.com", "password": "ChatTasksPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={"message": "Show my tasks."})
    assert chat_resp.status_code == 200
    paths = [r["path"] for r in chat_resp.json()["records"]]
    assert f"/daily-tasks/{task['id']}" in paths


def test_chatbot_unlinked_account_gets_clear_message_not_empty_silence(client, test_user, db_session):
    _login(client, test_user)
    unlinked_user = User(
        username="chatunlinkeduser", email="chatunlinkeduser@example.com", full_name="Unlinked",
        password_hash=hash_password("ChatTasksPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(unlinked_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "chatunlinkeduser@example.com", "password": "ChatTasksPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={"message": "What do I need to complete today?"})
    assert chat_resp.status_code == 200
    assert "not linked" in chat_resp.json()["response"].lower()


def test_chatbot_blocked_tasks_query(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Blocked Task Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee["id"], "task_description": "Waiting on materials",
    }).json()
    client.put(f"/api/daily-tasks/{task['id']}", json={"status": "Blocked"})

    resp = client.post("/api/chat/", json={"message": "Which tasks are blocked?"})
    assert resp.status_code == 200
    paths = [r["path"] for r in resp.json()["records"]]
    assert f"/daily-tasks/{task['id']}" in paths


def test_chatbot_no_match_for_unknown_name_gives_clear_answer(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "Show tasks for NobodyWithThisNameExists."})
    assert resp.status_code == 200
    assert resp.json()["records"] == []
    assert "couldn't find" in resp.json()["response"].lower()
