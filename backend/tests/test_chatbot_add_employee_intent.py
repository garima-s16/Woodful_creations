"""Tests for the P0 intent-collision bug named explicitly in the
product brief: "add new employee arpit" was being silently swallowed
by the material-add parser (any "add ..." message matched it
unconditionally), creating a fake material literally named "new
employee arpit" instead of proposing to create an employee."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_add_new_employee_is_not_misread_as_material(client, test_user):
    """The exact regression from the brief - this must never produce
    a proposed material creation."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "add new employee arpit"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["proposed_action"] is not None
    assert data["proposed_action"]["action_type"] == "create_employee"
    assert data["proposed_action"]["payload"]["name"] == "Arpit"


def test_add_employee_named_phrasing_extracts_clean_name(client, test_user):
    """Regression guard for a bug caught during implementation - the
    word "named" was leaking into the extracted name."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "add a new employee named devendra"})
    assert resp.json()["proposed_action"]["payload"]["name"] == "Devendra"


def test_material_add_command_still_works_normally(client, test_user):
    """The fix must not break the legitimate material-add path this
    collision sat in front of."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "HDHMR", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "5",
    })
    resp = client.post("/api/chat/", json={"message": "add 4 sheets of hdhmr to my cart"})
    assert resp.status_code == 200
    # Whatever it resolves to, it must NOT be an employee creation proposal
    proposed = resp.json().get("proposed_action")
    if proposed:
        assert proposed["action_type"] != "create_employee"


def test_add_employee_requires_master_role(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Add Employee Intent Test Employee"}).json()
    user = User(
        username="addemployeeintentuser", email="addemployeeintentuser@example.com",
        full_name="Add Employee Intent User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "addemployeeintentuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": "add new employee ravi"})
    assert resp.json()["proposed_action"] is None
    assert "master account" in resp.json()["response"].lower()


def test_add_employee_detects_existing_name(client, test_user):
    _login(client, test_user)
    client.post("/api/employees/", json={"name": "Chhoutu"})

    resp = client.post("/api/chat/", json={"message": "add new employee chhoutu"})
    assert resp.json()["proposed_action"] is None
    assert "already" in resp.json()["response"].lower()
