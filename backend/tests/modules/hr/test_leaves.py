from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def _create_employee(client):
    resp = client.post("/api/employees/", json={
        "employee_code": "EMP-LEAVE", "name": "Leave Test Employee", "monthly_salary": "18000.00",
    })
    return resp.json()["id"]


def _create_logged_in_employee(client, db_session, employee_name, username, email):
    """Unlike _create_employee above (which only creates the employee
    record), this also creates and logs in as a real User account tied
    to that employee - needed for RBAC tests that check "own records"
    access by actually being logged in as the employee in question."""
    employee = client.post("/api/employees/", json={
        "name": employee_name, "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200
    return employee


def test_leave_request_and_default_status(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/leaves/", json={
        "employee_id": employee_id, "leave_type": "CL",
        "start_date": "2026-08-20T00:00:00", "end_date": "2026-08-21T00:00:00",
        "reason": "Family function",
    })
    assert resp.status_code == 201
    assert resp.json()["status"] == "Pending"
    assert resp.json()["days"] == "2"


def test_leave_days_is_1_when_from_equals_to(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/leaves/", json={
        "employee_id": employee_id, "leave_type": "SL",
        "start_date": "2026-08-11T00:00:00", "end_date": "2026-08-11T00:00:00",
    })
    assert resp.status_code == 201
    assert resp.json()["days"] == "1"


def test_leave_days_inclusive_multi_day(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/leaves/", json={
        "employee_id": employee_id, "leave_type": "PL",
        "start_date": "2026-08-11T00:00:00", "end_date": "2026-08-13T00:00:00",
    })
    assert resp.status_code == 201
    assert resp.json()["days"] == "3"


def test_leave_days_from_client_is_ignored(client, test_user):
    """Even if a caller (or a stale frontend build) sends a garbage `days`
    value, the server must compute its own - never trust the client for a
    number that must never be 0/negative/NaN."""
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/leaves/", json={
        "employee_id": employee_id, "leave_type": "CL",
        "start_date": "2026-08-11T00:00:00", "end_date": "2026-08-11T00:00:00",
        "days": "-1",
    })
    assert resp.status_code == 201
    assert resp.json()["days"] == "1"


def test_leave_rejects_end_before_start(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    resp = client.post("/api/leaves/", json={
        "employee_id": employee_id, "leave_type": "SL",
        "start_date": "2026-08-20T00:00:00", "end_date": "2026-08-18T00:00:00",
    })
    assert resp.status_code == 400


def test_leave_approval_updates_status(client, test_user):
    _login(client, test_user)
    employee_id = _create_employee(client)

    create = client.post("/api/leaves/", json={
        "employee_id": employee_id, "leave_type": "PL",
        "start_date": "2026-09-01T00:00:00", "end_date": "2026-09-02T00:00:00",
    })
    leave_id = create.json()["id"]

    resp = client.put(f"/api/leaves/{leave_id}", json={"status": "Approved", "approved_by": "Nikhil"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "Approved"


def test_leaves_require_auth(client):
    resp = client.get("/api/leaves/")
    assert resp.status_code == 401


def test_employee_cannot_view_another_employees_leaves(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Leave RBAC Other Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/leaves/", json={
        "employee_id": other_employee["id"], "leave_type": "Sick", "start_date": "2026-08-01T00:00:00", "end_date": "2026-08-02T00:00:00",
    })

    _create_logged_in_employee(client, db_session, "Leave RBAC Self Employee", "leaverbacuser", "leaverbacuser@example.com")
    resp = client.get("/api/leaves/", params={"employee_id": other_employee["id"]})
    assert resp.status_code == 403


def test_employee_can_view_own_leaves(client, test_user, db_session):
    _login(client, test_user)
    employee = _create_logged_in_employee(client, db_session, "Leave RBAC Own Employee", "leaveownrbacuser", "leaveownrbacuser@example.com")
    _login(client, test_user)
    client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "Casual", "start_date": "2026-08-05T00:00:00", "end_date": "2026-08-05T00:00:00",
    })

    client.post("/api/auth/login", json={"identifier": "leaveownrbacuser@example.com", "password": "EmpPass1!"})
    resp = client.get("/api/leaves/")
    assert resp.status_code == 200
    assert all(l["employee_id"] == employee["id"] for l in resp.json())


def test_employee_cannot_request_leave_for_someone_else(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Leave RBAC Impersonation Target", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    _create_logged_in_employee(client, db_session, "Leave RBAC Impersonator", "leaveimpersonateuser", "leaveimpersonateuser@example.com")

    resp = client.post("/api/leaves/", json={
        "employee_id": other_employee["id"], "leave_type": "Sick", "start_date": "2026-08-10T00:00:00", "end_date": "2026-08-10T00:00:00",
    })
    assert resp.status_code == 403


def test_chatbot_employee_cannot_view_another_employees_leaves(client, test_user, db_session):
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "ChatLeaveRbacTarget", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/leaves/", json={
        "employee_id": other_employee["id"], "leave_type": "Sick", "start_date": "2026-08-01T00:00:00", "end_date": "2026-08-02T00:00:00",
    })

    _create_logged_in_employee(client, db_session, "Chat Leave RBAC Requester", "chatleaverbacuser", "chatleaverbacuser@example.com")
    resp = client.post("/api/chat/", json={"message": "Show ChatLeaveRbacTarget's leaves"})
    assert "own leave records" in resp.json()["response"].lower()


def test_chatbot_master_can_view_named_employees_leaves(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "ChatLeaveRbacMasterTarget", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "Casual", "start_date": "2026-08-03T00:00:00", "end_date": "2026-08-03T00:00:00",
    })

    resp = client.post("/api/chat/", json={"message": "Show ChatLeaveRbacMasterTarget's leaves"})
    assert "own leave records" not in resp.json()["response"].lower()


def test_chatbot_employee_can_view_own_leaves(client, test_user, db_session):
    _login(client, test_user)
    employee = _create_logged_in_employee(client, db_session, "Chat Leave RBAC Self", "chatleaveselfrbacuser", "chatleaveselfrbacuser@example.com")
    _login(client, test_user)
    client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "Casual", "start_date": "2026-08-04T00:00:00", "end_date": "2026-08-04T00:00:00",
    })

    client.post("/api/auth/login", json={"identifier": "chatleaveselfrbacuser@example.com", "password": "EmpPass1!"})
    resp = client.post("/api/chat/", json={"message": "Show my leaves"})
    assert resp.status_code == 200
    assert "own leave records" not in resp.json()["response"].lower()


def test_unlinked_non_master_user_sees_no_leaves(client, test_user, db_session):
    """Unlinked non-master users must get zero records, not an
    unfiltered query result across every employee's leave history."""
    _login(client, test_user)
    other_id = _create_employee(client)
    client.post("/api/leaves/", json={
        "employee_id": other_id, "leave_type": "Casual",
        "start_date": "2026-08-10T00:00:00", "end_date": "2026-08-10T00:00:00",
    })
    user = User(
        username="unlinkedleaveuser", email="unlinkedleaveuser@example.com", full_name="Unlinked Leave User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "unlinkedleaveuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/leaves/")
    assert resp.status_code == 200
    assert resp.json() == []
