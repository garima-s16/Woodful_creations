"""Tests for Section 1's critical bug fix - the chatbot must understand
basic material add/cart commands. Matches the brief's own Section 49
test list exactly."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_add_material_with_no_existing_match_proposes_creation(client, test_user):
    """"Add one HDHMR sheet of 6mm" with no existing 6mm HDHMR - AI must
    propose creation, never silently create it."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "Add one HDHMR sheet of 6mm in list"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposed_action"] is not None
    assert body["proposed_action"]["action_type"] == "create_material"
    assert "6mm" in body["proposed_action"]["payload"]["thickness_size"]
    assert "hdhmr" in body["proposed_action"]["payload"]["name"].lower()


def test_confirming_create_material_actually_creates_it(client, test_user):
    """The proposal alone isn't enough - confirming it must actually
    create a real, verifiable database row (Section 3's explicit
    "verify the database after execution")."""
    _login(client, test_user)
    proposal = client.post("/api/chat/", json={
        "message": "Add one HDHMR sheet of 6mm in list",
    }).json()["proposed_action"]

    create_resp = client.post("/api/materials/", json=proposal["payload"])
    assert create_resp.status_code == 201

    materials = client.get("/api/materials/", params={"search": "HDHMR"}).json()
    assert any("6mm" in (m.get("thickness_size") or "") for m in materials)


def test_add_material_that_already_exists_does_not_propose_duplicate_creation(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "HDHMR Board", "thickness_size": "6mm", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 2,
    })

    resp = client.post("/api/chat/", json={"message": "Add one HDHMR sheet of 6mm in list"})
    body = resp.json()
    assert body["proposed_action"] is None
    assert "already exists" in body["response"].lower()
    assert body["records"][0]["type"] == "Material"


def test_add_to_purchase_cart_when_material_exists(client, test_user):
    """"Add 5 HDHMR 18mm sheets to my purchase cart" - must propose
    add_to_cart, not create_material, when the material already exists."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "HDHMR Board", "thickness_size": "18mm", "unit": "Sheets", "opening_stock": 20, "minimum_stock": 5,
    }).json()

    resp = client.post("/api/chat/", json={"message": "Add 5 HDHMR 18mm sheets to my purchase cart."})
    body = resp.json()
    assert body["proposed_action"]["action_type"] == "add_to_cart"
    assert body["proposed_action"]["payload"]["materialId"] == material["id"]
    assert body["proposed_action"]["payload"]["quantity"] == 5.0


def test_add_to_cart_when_material_does_not_exist_asks_instead_of_guessing(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "Add 5 nonexistent material xyz to my purchase cart."})
    body = resp.json()
    assert body["proposed_action"] is None
    assert "couldn't find" in body["response"].lower()


def test_word_number_quantity_correctly_stripped_from_description(client, test_user):
    """"one" must be recognized and consumed as the quantity, not left
    stuck in the guessed material name (e.g. "One Hdhmr 6mm")."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "Add one HDHMR sheet of 6mm in list"})
    guessed_name = resp.json()["proposed_action"]["payload"]["name"]
    assert "one" not in guessed_name.lower().split()


def test_project_issue_phrasing_gives_honest_not_yet_supported_message(client, test_user):
    """"Add 4 sheets to Ishu's project" must not silently create garbage
    material named "sheets to ishu's project" - this is a genuinely
    different action (issue to project) not yet implemented via chat."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "Add 4 sheets to Ishu's project."})
    body = resp.json()
    assert body["proposed_action"] is None
    assert "issues page" in body["response"].lower() or "issue" in body["response"].lower()
    assert "ishu" in body["response"].lower()


def test_create_material_requires_master_or_manager_role(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Chat Material Perm Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    limited_user = User(
        username="chatmaterialpermuser", email="chatmaterialpermuser@example.com", full_name="Limited User",
        password_hash=hash_password("LimitedPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(limited_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "chatmaterialpermuser@example.com", "password": "LimitedPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={"message": "Add one HDHMR sheet of 6mm in list"})
    assert chat_resp.json()["proposed_action"] is None
    assert "master account" in chat_resp.json()["response"].lower()


def test_receive_stock_via_chat_gives_honest_not_yet_supported_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "Add 5 HDHMR sheets to stock."})
    body = resp.json()
    assert body["proposed_action"] is None
    assert "purchase" in body["response"].lower()
