"""Tests for two more financial-leak gaps found this turn: the
personal cart's stored rate leaking a material's price to an employee
even though Materials itself redacts it, and the chatbot's cart
optimization (explicit supplier price comparison) having no permission
check at all."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee(client, db_session, username, email):
    employee = client.post("/api/employees/", json={
        "name": username, "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200
    return user


def test_master_sees_own_cart_item_rate(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC Master Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "400.00",
    }).json()

    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "2"})
    assert resp.json()["rate"] is not None


def test_employee_own_cart_item_rate_is_genuinely_null(client, test_user, db_session):
    """The real gap found this turn - an employee could previously see
    a material's price by adding it to their own cart, even though the
    Materials page itself hides it from them."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC Employee Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "400.00",
    }).json()

    _create_employee(client, db_session, "cartrbacuser", "cartrbacuser@example.com")
    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "2"})
    assert resp.status_code == 201
    assert resp.json()["rate"] is None
    # Non-financial fields remain visible - it's still a usable cart.
    assert resp.json()["material_name"] == "Cart RBAC Employee Material"
    assert float(resp.json()["quantity"]) == 2.0


def test_employee_cart_list_also_redacts_rate(client, test_user, db_session):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC List Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "250.00",
    }).json()

    _create_employee(client, db_session, "cartlistrbacuser", "cartlistrbacuser@example.com")
    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "1"})
    listed = client.get("/api/personal-cart/").json()
    assert listed[0]["rate"] is None


def test_employee_accumulating_existing_cart_item_still_redacts_rate(client, test_user, db_session):
    """The second add-to-cart code path (existing item, quantity
    accumulates) must also redact - not just the first-add path."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC Accumulate Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "300.00",
    }).json()

    _create_employee(client, db_session, "cartaccumrbacuser", "cartaccumrbacuser@example.com")
    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "1"})
    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "1"})
    assert resp.json()["rate"] is None
    assert float(resp.json()["quantity"]) == 2.0


def test_chatbot_employee_denied_cart_optimization(client, test_user, db_session):
    """The real gap found this turn - cart optimization explicitly
    compares supplier prices and had no permission check at all."""
    _login(client, test_user)
    supplier_a = client.post("/api/suppliers/", json={"name": "Cart Opt RBAC Supplier A"}).json()
    supplier_b = client.post("/api/suppliers/", json={"name": "Cart Opt RBAC Supplier B"}).json()
    material = client.post("/api/materials/", json={
        "name": "Cart Opt RBAC Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_a["id"], "material_id": material["id"], "supplier_price": "100.00",
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_b["id"], "material_id": material["id"], "supplier_price": "120.00",
    })

    _create_employee(client, db_session, "cartoptrbacuser", "cartoptrbacuser@example.com")
    resp = client.post("/api/chat/", json={
        "message": "Optimize this purchase",
        "context": {"cart_items": [{"material_id": material["id"], "quantity": 5}]},
    })
    text = resp.json()["response"]
    assert "master accounts only" in text.lower()
    assert "Cart Opt RBAC Supplier A" not in text
    assert "100" not in text


def test_chatbot_master_still_gets_real_cart_optimization(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Cart Opt RBAC Master Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Cart Opt RBAC Master Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "100.00",
    })

    resp = client.post("/api/chat/", json={
        "message": "Optimize this purchase",
        "context": {"cart_items": [{"material_id": material["id"], "quantity": 5}]},
    })
    text = resp.json()["response"]
    assert "master accounts only" not in text.lower()
    assert "Cart Opt RBAC Master Supplier" in text
