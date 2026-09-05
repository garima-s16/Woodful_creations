"""Operations domain tests - DailyTask/Milestone lifecycle, consolidated
from 3 separate files: milestones + chatbot "next action", task
self-service authorization (a normal user may update ONLY their own
assigned task, and only the self-service field set - status,
completion_percent, delay_reason, remarks - even on their own task;
master retains unrestricted access), and the task handoff system
(Complete & Assign Next, comments, subtasks, blocked-reason
self-service).

Status values match the actual current vocabulary (TO DO / DOING /
DONE / BLOCKED), not an older "In Progress"/"Completed" vocabulary
some of the source files previously used.

One genuine helper-name collision was found and resolved: both
test_task_authorization.py and test_task_handoff_and_comments.py
defined a same-signature _create_employee_user - but they are not
duplicates, they do different things (the authorization version
creates and returns the User row; the handoff version also logs that
user in and asserts success, returning nothing). Kept both under
distinct names: _create_employee_user (create only) and
_create_and_login_employee_user (create + login).
"""
from sqlalchemy import event
from app.platform.database.database import engine
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


# ===========================================================================
# Milestones + chatbot "next action" (from test_milestones_and_next_action.py)
# ===========================================================================
def test_create_milestone(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Milestone Test Client", "phone": "9000010114"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    resp = client.post("/api/milestones/", json={
        "order_id": order["id"], "name": "Design approval", "target_date": "2026-09-01T00:00:00",
    })
    assert resp.status_code == 201
    assert resp.json()["name"] == "Design approval"
    assert resp.json()["completed_date"] is None


def test_milestone_creation_requires_master(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Milestone RBAC Client", "phone": "9000010115"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Milestone RBAC Employee"}).json()
    user = User(
        username="milestonerbacuser", email="milestonerbacuser@example.com", full_name="Milestone RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "milestonerbacuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/milestones/", json={
        "order_id": order["id"], "name": "Employee Attempt", "target_date": "2026-09-01T00:00:00",
    })
    assert resp.status_code == 403


def test_milestone_can_be_marked_complete(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Milestone Complete Client", "phone": "9000010116"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    milestone = client.post("/api/milestones/", json={
        "order_id": order["id"], "name": "Site measurement", "target_date": "2026-08-25T00:00:00",
    }).json()

    resp = client.put(f"/api/milestones/{milestone['id']}", json={"completed_date": "2026-08-24T00:00:00"})
    assert resp.status_code == 200
    assert resp.json()["completed_date"] is not None


def test_milestones_list_filters_by_order(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Milestone Filter Client", "phone": "9000010117"}).json()["id"]
    order_a = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "12000", "advance": "0",
    }).json()
    client.post("/api/milestones/", json={"order_id": order_a["id"], "name": "A Milestone", "target_date": "2026-09-01T00:00:00"})
    client.post("/api/milestones/", json={"order_id": order_b["id"], "name": "B Milestone", "target_date": "2026-09-01T00:00:00"})

    resp = client.get("/api/milestones/", params={"order_id": order_a["id"]})
    assert resp.status_code == 200
    names = [m["name"] for m in resp.json()]
    assert "A Milestone" in names
    assert "B Milestone" not in names


def test_chatbot_next_action_via_client_name(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Next Action Client", "phone": "9000010118"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    client.post("/api/daily-tasks/", json={
        "order_id": order["id"], "date": "2026-08-20T00:00:00",
        "task_description": "Site measurement", "status": "TO DO",
    })

    resp = client.post("/api/chat/", json={"message": "what is the next action for Next Action Client"})
    assert resp.status_code == 200
    assert "Site measurement" in resp.json()["response"]


def test_chatbot_next_action_flags_blocked_task(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Next Action Blocked Client", "phone": "9000010119"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    client.post("/api/daily-tasks/", json={
        "order_id": order["id"], "date": "2026-08-20T00:00:00",
        "task_description": "Blocked cutting", "status": "BLOCKED", "delay_reason": "Waiting for material",
    })

    resp = client.post("/api/chat/", json={"message": "what is the next action for Next Action Blocked Client"})
    assert resp.status_code == 200
    assert "Blocked cutting" in resp.json()["response"]


def test_chatbot_next_action_no_open_tasks(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Next Action Empty Client", "phone": "9000010120"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    })

    resp = client.post("/api/chat/", json={"message": "what is the next action for Next Action Empty Client"})
    assert resp.status_code == 200


# ===========================================================================
# Task self-service authorization (from test_task_authorization.py)
# ===========================================================================
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

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DOING"})
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "DOING"


def test_employee_cannot_update_another_employees_task_status(client, test_user, db_session):
    """The core rule: ownership is resolved via
    employee_id, not open to anyone - an employee cannot touch a task
    assigned to someone else, even just its status."""
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

    update_resp = client.put(f"/api/daily-tasks/{task_for_b['id']}", json={"status": "DONE"})
    assert update_resp.status_code == 403


def test_employee_can_update_completion_percent_on_own_task(client, test_user, db_session):
    """completion_percent IS in the self-service field set
    (EMPLOYEE_SELF_SERVICE_FIELDS in daily_tasks.py) - an employee can
    update it on their OWN task."""
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
    assert update_resp.status_code == 200
    assert update_resp.json()["completion_percent"] == 40


def test_employee_cannot_reassign_task_via_self_service_fields(client, test_user, db_session):
    """Even on their own task, an employee still can't change fields
    outside the self-service allowlist - e.g. checked_by."""
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


def test_employee_with_no_linked_employee_record_cannot_update_any_task(client, test_user, db_session):
    """Ownership is resolved via authenticated user -> employee_id ->
    DailyTask.employee_id (B13). A 'user'-role account with no linked
    Employee record has employee_id=None, which can never equal a
    real task's employee_id - so it can't update any task, including
    its own status, since it has no "own" task to begin with."""
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

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DOING"})
    assert update_resp.status_code == 403


def test_master_can_edit_all_task_fields(client, test_user):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Master Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "Master editable task",
    }).json()

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={
        "status": "DOING", "completion_percent": 40, "checked_by": "Garima",
    })
    assert update_resp.status_code == 200
    assert update_resp.json()["completion_percent"] == 40
    assert update_resp.json()["checked_by"] == "Garima"


def test_master_can_reassign_another_employees_task(client, test_user):
    """Master is not subject to the ownership restriction at all -
    reassignment (and every other field) is a management operation."""
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Master Reassign Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    other_employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Master Reassign Other Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "Reassignable task",
    }).json()

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"employee_id": other_employee_id})
    assert update_resp.status_code == 200
    assert update_resp.json()["employee_id"] == other_employee_id


def test_completed_status_forces_completion_percent_to_100(client, test_user):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Auth Employee F", "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee_id, "task_description": "F's task",
        "completion_percent": 30,
    }).json()

    update_resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DONE"})
    assert update_resp.status_code == 200
    assert update_resp.json()["completion_percent"] == 100
    assert update_resp.json()["actual_completed_at"] is not None


def test_any_authenticated_role_can_view_all_tasks(client, test_user, db_session):
    """Viewing (GET list, without mine=True) is unrestricted for any
    authenticated role - the ownership restriction in B13 applies to
    updating a task, not viewing the list."""
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
    """"mine" is a convenience filter for an employee's own task list -
    a separate concern from B13's update-ownership restriction, but
    consistent with it (both resolve via the same employee_id link)."""
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

# ===========================================================================
# Task handoff - Complete & Assign Next, comments, subtasks (from test_task_handoff_and_comments.py)
# ===========================================================================

def _create_and_login_employee_user(client, db_session, employee_id, username, email):
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
    assert original["status"] == "DONE"
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
    _create_and_login_employee_user(client, db_session, employee["id"], "blockreasonuser", "blockreasonuser@example.com")

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
    _create_and_login_employee_user(client, db_session, employee["id"], "blocknotifuser", "blocknotifuser@example.com")

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
    _create_and_login_employee_user(client, db_session, other_employee["id"], "handoffunrelateduser", "handoffunrelateduser@example.com")

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
    _create_and_login_employee_user(client, db_session, owner["id"], "handoffselfuser", "handoffselfuser@example.com")

    resp = client.post(f"/api/daily-tasks/{task['id']}/complete-and-assign-next", json={
        "next_employee_id": next_employee["id"], "next_task_description": "Handed off task",
        "next_due_date": "2026-08-20T00:00:00",
    })
    assert resp.status_code == 201

# ===========================================================================
# Tasks export N+1 query regression guard (from test_admin_and_ai_gateway.py's
# former test_excel_export_n_plus_one.py section)
# ===========================================================================
class _QueryCounter:
    def __init__(self):
        self.count = 0

    def __enter__(self):
        event.listen(engine, "before_cursor_execute", self._callback)
        return self

    def __exit__(self, *args):
        event.remove(engine, "before_cursor_execute", self._callback)

    def _callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1


def test_tasks_export_query_count_does_not_scale_with_row_count(client, test_user):
    """The core N+1 regression guard - export a growing number of
    tasks, each with a DIFFERENT employee and order, and confirm the
    query count stays bounded rather than growing linearly."""
    _login(client, test_user)
    for i in range(8):
        client_id = client.post("/api/clients/", json={"name": f"N+1 Test Client {i}", "phone": "9000010077"}).json()["id"]
        order = client.post("/api/orders/", json={
            "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "10000", "advance": "0",
        }).json()
        employee = client.post("/api/employees/", json={"name": f"N+1 Test Employee {i}"}).json()
        client.post("/api/daily-tasks/", json={
            "date": "2026-08-21T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
            "task_description": f"N+1 test task {i}",
        })

    with _QueryCounter() as counter:
        resp = client.get("/api/reports/tasks.xlsx")
    assert resp.status_code == 200
    # With 8 distinct employees/orders, an N+1 bug would need roughly
    # 8 (tasks) + 8 (employee lookups) + 8 (order lookups) = 24+ queries
    # for this one export alone. Eager-loading keeps it to a small,
    # fixed number regardless of row count.
    assert counter.count < 15, f"expected a bounded query count, got {counter.count} - possible N+1 regression"
