"""Regression tests for the User <-> Employee <-> Task relationship - a
real backend authorization gap where any authenticated user could
previously update any task, and there was no way to resolve "my tasks"
without matching names."""
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


def test_employee_can_update_own_task(client, test_user, db_session):
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

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "In Progress", "completion_percent": 40})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "In Progress"
    assert update_resp.json()["completion_percent"] == 40


def test_employee_cannot_update_another_employees_task(client, test_user, db_session):
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
    assert update_resp.status_code == 403


def test_employee_cannot_reassign_task_via_self_service_fields(client, test_user, db_session):
    """Even on their own task, an employee can't change fields outside
    the explicit self-service allowlist (status, completion_percent,
    remarks, delay_reason) - e.g. reassigning it to someone else."""
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

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"checked_by": "Someone Else"})
    assert update_resp.status_code == 403


def test_employee_with_no_linked_record_gets_clear_rejection(client, test_user, db_session):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee D", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "D's task",
    }).json()
    # A user account that exists but was never linked to an employee.
    unlinked = User(
        username="taskauthunlinked", email="taskauthunlinked@example.com", full_name="Unlinked",
        password_hash=hash_password("EmployeePass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(unlinked)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "taskauthunlinked@example.com", "password": "EmployeePass1!"})
    assert resp.status_code == 200

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "In Progress"})
    assert update_resp.status_code == 403
    assert "not linked" in update_resp.json()["detail"].lower()


def test_completed_status_forces_completion_percent_to_100(client, test_user):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee E", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "E's task",
        "completion_percent": 30,
    }).json()

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "Completed"})
    assert update_resp.status_code == 200
    assert update_resp.json()["completion_percent"] == 100


def test_mine_query_returns_only_the_linked_employees_tasks(client, test_user, db_session):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee F", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    other_employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee G", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "F's own task",
    })
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": other_employee_id, "task_description": "G's task",
    })
    _create_employee_user(client, db_session, employee_id, "taskauthempf", "taskauthempf@example.com")

    resp = client.post("/api/auth/login", json={"identifier": "taskauthempf@example.com", "password": "EmployeePass1!"})
    assert resp.status_code == 200

    mine_resp = client.get("/api/daily-tasks/", params={"mine": True})
    assert mine_resp.status_code == 200
    descriptions = [t["task_description"] for t in mine_resp.json()]
    assert "F's own task" in descriptions
    assert "G's task" not in descriptions


def test_master_can_still_update_any_task_and_any_field(client, test_user):
    """Confirms the authorization change didn't accidentally restrict
    master/manager accounts, which must retain full access."""
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee H", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "H's task",
    }).json()

    resp = client.put(f"/api/daily-tasks/{task['id']}", json={"checked_by": "Manager Name", "status": "In Progress"})
    assert resp.status_code == 200
    assert resp.json()["checked_by"] == "Manager Name"
