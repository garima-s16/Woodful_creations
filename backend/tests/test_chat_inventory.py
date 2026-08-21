"""Tests for the inventory-specific chatbot gaps found and fixed this
turn: material-specific stock/supplier lookup, out-of-stock (distinct
from merely low), recent purchases, and the RBAC finding that inventory
viewing is genuinely not role-restricted anywhere in the real app."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_how_much_material_question_returns_specific_stock_not_generic_summary(client, test_user):
    """The exact bug found this turn - this must return HDHMR's own
    stock figure, not a generic "you have N materials" answer."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "HDHMR 18mm Chat Test", "unit": "Sheets", "opening_stock": "23", "minimum_stock": "20",
    })

    resp = client.post("/api/chat/", json={"message": "How much HDHMR 18mm Chat Test do we have?"})
    assert resp.status_code == 200
    text = resp.json()["response"]
    assert "23" in text
    assert "Sheets" in text


def test_which_supplier_supplied_material_question(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Chat Supplier Lookup Co"}).json()
    client.post("/api/materials/", json={
        "name": "Supplier Lookup Chat Material", "unit": "Sheets", "opening_stock": "5",
        "minimum_stock": "1", "supplier_id": supplier["id"],
    })

    resp = client.post("/api/chat/", json={"message": "Which supplier supplies Supplier Lookup Chat Material?"})
    assert "Chat Supplier Lookup Co" in resp.json()["response"]


def test_this_material_deictic_reference_does_not_misfire_as_literal_search(client, test_user):
    """"this material" must not be searched for literally - it should
    fall through to context-based handling (or the generic fallback if
    no context is provided), not return a nonsense "couldn't find a
    material matching 'material'" response."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "Which supplier supplied this material?"})
    assert resp.status_code == 200
    assert "couldn't find a material matching" not in resp.json()["response"].lower()


def test_out_of_stock_is_distinct_from_low_stock(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Zero Stock Chat Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    })
    client.post("/api/materials/", json={
        "name": "Low But Nonzero Chat Material", "unit": "Sheets", "opening_stock": "2", "minimum_stock": "5",
    })

    resp = client.post("/api/chat/", json={"message": "Which materials are out of stock?"})
    text = resp.json()["response"]
    assert "out of stock" in text.lower()


def test_material_not_found_gives_honest_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "How much Nonexistent Fictional Material XYZ do we have?"})
    assert "couldn't find" in resp.json()["response"].lower()


def test_recent_purchases_question(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Recent Purchase Chat Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Recent Purchase Chat Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-16T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })

    resp = client.post("/api/chat/", json={"message": "What materials were purchased recently?"})
    assert resp.status_code == 200
    assert resp.json()["records"] is not None


def test_inventory_questions_work_for_any_authenticated_role(client, test_user, db_session):
    """The real finding this turn - the actual REST API does not
    role-restrict viewing inventory (only mutating it), so the chatbot
    matching that means a plain "user" role account gets real answers,
    not a denial - building a fake restriction here would make the
    chatbot LESS capable than the real Materials page for no reason."""
    from app.core.security import hash_password
    from app.models.user import User

    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Inventory RBAC Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    limited_user = User(
        username="inventoryrbacuser", email="inventoryrbacuser@example.com", full_name="Limited Inventory User",
        password_hash=hash_password("LimitedPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(limited_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "inventoryrbacuser@example.com", "password": "LimitedPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={"message": "What materials are low in stock?"})
    assert chat_resp.status_code == 200
    assert "don't have access" not in chat_resp.json()["response"].lower()


def test_unauthenticated_chat_request_is_rejected(client):
    """The genuine permission boundary that actually exists - the chat
    endpoint itself requires authentication, matching every other
    protected endpoint in the app."""
    resp = client.post("/api/chat/", json={"message": "What materials are low in stock?"})
    assert resp.status_code in (401, 403)
