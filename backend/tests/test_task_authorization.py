"""Tests for task authorization, corrected per the explicit access-
control brief: any employee (any non-master role) can edit
ANY task's status - not restricted to tasks assigned to them - and
status is the only field an employee may touch; every other field
remains master-only. Master retains unrestricted access
to every field."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee_user(client, db_session, employee_id, username, email):
    """Creates a real 'user'-role account linked to a specific employee,
    the same way a master would via the Users admin page."""
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmployeePass1!"), role="user", employee_id=employee_id, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def test_employee_can_update_own_task_status(client, test_user, db_session):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee One", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "Sand panels",
    }).json()
    _create_employee_user(client, db_session, employee_id, "taskauthemp1", "taskauthemp1@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "taskauthemp1@example.com", "password": "EmployeePass1!"})
    assert resp.status_code == 200

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "In Progress"})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "In Progress"


def test_employee_can_update_another_employees_task_status(client, test_user, db_session):
    """The explicit correction - tasks are visible and status-editable
    by everyone, not restricted to the assignee."""
    _login(client, test_user)
    employee_a = client.post("/api/employees/", json={
        "name": "Task Auth Employee A", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    employee_b = client.post("/api/employees/", json={
        "name": "Task Auth Employee B", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task_for_b = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_b, "task_description": "B's task",
    }).json()
    _create_employee_user(client, db_session, employee_a, "taskauthempa", "taskauthempa@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "taskauthempa@example.com", "password": "EmployeePass1!"})
    assert resp.status_code == 200

    update_resp = client.put(f"/api/daily-tasks/{task_for_b['id']}", json={"status": "Completed"})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "Completed"


def test_employee_cannot_update_completion_percent(client, test_user, db_session):
    """Narrowed per the brief - "any employee can edit task STATUS"
    means status only, not completion_percent/remarks/delay_reason,
    which were previously also allowed."""
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee C", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "C's task",
    }).json()
    _create_employee_user(client, db_session, employee_id, "taskauthempc", "taskauthempc@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "taskauthempc@example.com", "password": "EmployeePass1!"})
    assert resp.status_code == 200

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"completion_percent": 40})
    assert update_resp.status_code == 403


def test_employee_cannot_reassign_task_via_self_service_fields(client, test_user, db_session):
    """Even for status-permitted access, an employee still can't change
    fields outside the allowlist - e.g. reassigning a task."""
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee D", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "D's task",
    }).json()
    _create_employee_user(client, db_session, employee_id, "taskauthempd", "taskauthempd@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "taskauthempd@example.com", "password": "EmployeePass1!"})
    assert resp.status_code == 200

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"checked_by": "Someone Else"})
    assert update_resp.status_code == 403


def test_employee_with_no_linked_employee_record_can_still_update_status(client, test_user, db_session):
    """A deliberate consequence of the correction - status editing no
    longer depends on employee identity at all, so a 'user'-role
    account not linked to any Employee record can still update status,
    matching "any employee can edit task STATUS" taken literally."""
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee E", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "E's task",
    }).json()
    unlinked = User(
        username="taskauthunlinked", email="taskauthunlinked@example.com", full_name="Unlinked",
        password_hash=hash_password("EmployeePass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(unlinked)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "taskauthunlinked@example.com", "password": "EmployeePass1!"})
    assert resp.status_code == 200

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "In Progress"})
    assert update_resp.status_code == 200


def test_master_can_edit_all_task_fields(client, test_user):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Master Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "Master editable task",
    }).json()

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={
        "status": "In Progress", "completion_percent": 40, "checked_by": "Garima",
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["completion_percent"] == 40
    assert update_resp.json()["checked_by"] == "Garima"


def test_completed_status_forces_completion_percent_to_100(client, test_user):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee F", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "F's task",
        "completion_percent": 30,
    }).json()

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "Completed"})
    assert update_resp.status_code == 200
    assert update_resp.json()["completion_percent"] == 100


def test_any_authenticated_role_can_view_all_tasks(client, test_user, db_session):
    """Everyone can view all tasks - matching the explicit rule."""
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth View Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    other_employee_id = client.post("/api/employees/", json={
        "name": "Task Auth View Other Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": other_employee_id, "task_description": "Someone else's task",
    })
    _create_employee_user(client, db_session, employee_id, "taskauthviewer", "taskauthviewer@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "taskauthviewer@example.com", "password": "EmployeePass1!"})
    assert resp.status_code == 200

    tasks = client.get("/api/daily-tasks/").json()
    assert any(t["task_description"] == "Someone else's task" for t in tasks)


def test_mine_query_still_filters_to_the_linked_employees_own_tasks(client, test_user, db_session):
    """Unaffected by this turn's fix - "mine" is a convenience filter
    for an employee's own task list, a separate concern from whether
    they're allowed to edit another employee's task status."""
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Mine Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    other_employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Mine Other Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "My own task",
    })
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": other_employee_id, "task_description": "Not my task",
    })
    _create_employee_user(client, db_session, employee_id, "taskauthmine", "taskauthmine@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "taskauthmine@example.com", "password": "EmployeePass1!"})
    assert resp.status_code == 200

    mine_tasks = client.get("/api/daily-tasks/", params={"mine": True}).json()
    descriptions = [t["task_description"] for t in mine_tasks]
    assert "My own task" in descriptions
    assert "Not my task" not in descriptions
