"""System administration tests - user account management (/api/users/)
and audit log access (/api/audit-logs/). This is a genuinely distinct
domain from HR (Employee records): a User is a login/authentication
account, not an employee. Extracted from the former
test_admin_and_ai_gateway.py, which mixed this together with 11 other
unrelated historical test files under one misleading name."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def test_list_users_requires_master(client):
    resp = client.get("/api/users/")
    assert resp.status_code == 401


def test_master_can_create_and_list_users(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "New Staff Employee"}).json()
    resp = client.post("/api/users/", json={
        "username": "newstaff", "email": "staff@example.com", "password": "StaffPass1!",
        "full_name": "New Staff", "role": "user", "employee_id": employee["id"],
    })
    assert resp.status_code == 201
    new_id = resp.json()["id"]

    resp = client.get("/api/users/")
    assert resp.status_code == 200
    assert any(u["id"] == new_id for u in resp.json())


def test_non_master_user_requires_an_employee_link(client, test_user):
    """The invariant every 'own records only' RBAC check across the app
    depends on: a non-master account with no employee_id would make
    those filters no-op (returning every employee's records instead of
    none), so creation must refuse it outright."""
    _login(client, test_user)
    resp = client.post("/api/users/", json={
        "username": "unlinkedstaff", "email": "unlinked@example.com", "password": "StaffPass1!",
        "full_name": "Unlinked Staff", "role": "user",
    })
    assert resp.status_code == 400


def test_non_master_user_employee_id_must_reference_a_real_employee(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/users/", json={
        "username": "ghoststaff", "email": "ghost@example.com", "password": "StaffPass1!",
        "full_name": "Ghost Staff", "role": "user", "employee_id": 999999,
    })
    assert resp.status_code == 400


def test_cannot_deactivate_protected_account(client, test_user, db_session):
    _login(client, test_user)
    test_user.cannot_be_deleted = True
    db_session.add(test_user)
    db_session.commit()

    resp = client.put(f"/api/users/{test_user.id}", json={"is_active": False})
    assert resp.status_code == 403


def test_cannot_delete_own_account(client, test_user):
    _login(client, test_user)
    resp = client.delete(f"/api/users/{test_user.id}")
    assert resp.status_code == 400


def test_cannot_delete_protected_account(client, test_user, db_session):
    _login(client, test_user)
    resp = client.post("/api/users/", json={
        "username": "protectedstaff", "email": "protected@example.com", "password": "StaffPass1!",
        "full_name": "Protected Staff", "role": "master",
    })
    protected_id = resp.json()["id"]

    protected_user = db_session.query(User).filter(User.id == protected_id).first()
    protected_user.cannot_be_deleted = True
    db_session.add(protected_user)
    db_session.commit()

    resp = client.delete(f"/api/users/{protected_id}")
    assert resp.status_code == 403


def test_audit_logs_requires_master(client):
    resp = client.get("/api/audit-logs/")
    assert resp.status_code == 401


def test_audit_logs_capture_login(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/audit-logs/", params={"action": "login"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1
