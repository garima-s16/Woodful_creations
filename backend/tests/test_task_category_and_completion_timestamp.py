"""Tests for task_category and actual_completed_at (workforce brief
Item 5 - task category, actual completion) - genuine gaps found
against DailyTask's field list, added via migration 0029."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_task_category_can_be_set_on_create(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Task Category Test Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"],
        "task_description": "Cut plywood panels", "task_category": "Cutting",
    }).json()
    assert task["task_category"] == "Cutting"


def test_actual_completed_at_is_set_on_transition_to_done(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Completion Timestamp Test Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"],
        "task_description": "Assemble wardrobe frame",
    }).json()
    assert task["actual_completed_at"] is None

    resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DONE"})
    assert resp.status_code == 200
    assert resp.json()["actual_completed_at"] is not None


def test_actual_completed_at_does_not_change_on_resave(client, test_user):
    """Re-saving an already-done task must not bump the completion
    timestamp - it should reflect when the task was FIRST completed."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Completion Timestamp Resave Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"],
        "task_description": "Install hinges",
    }).json()
    client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DONE"})
    first = client.get(f"/api/daily-tasks/{task['id']}").json()

    resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DONE", "remarks": "double-checked"})
    second = resp.json()
    assert second["actual_completed_at"] == first["actual_completed_at"]
