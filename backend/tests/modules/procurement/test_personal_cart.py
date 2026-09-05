"""Tests for the database-backed personal cart - the core requirement
being that it's real server-side persistence, correctly isolated per
user, enforced at the API layer (not just hidden in the UI)."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def _create_and_login(client, db_session, username, email):
    employee = client.post("/api/employees/", json={
        "name": username, "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("CartPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "CartPass1!"})
    assert resp.status_code == 200
    return user


def test_add_and_list_cart_item(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart Test Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
    }).json()

    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "5"})
    assert resp.status_code == 201
    assert resp.json()["material_name"] == "Cart Test Material"

    listed = client.get("/api/personal-cart/").json()
    assert len(listed) == 1
    assert float(listed[0]["quantity"]) == 5.0


def test_adding_same_material_twice_accumulates_not_duplicates(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Accumulate Test Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
    }).json()

    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "3"})
    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "2"})

    listed = client.get("/api/personal-cart/").json()
    assert len(listed) == 1
    assert float(listed[0]["quantity"]) == 5.0


def test_update_quantity_to_zero_removes_item(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Zero Qty Test Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
    }).json()
    item = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "5"}).json()

    resp = client.put(f"/api/personal-cart/{item['id']}", json={"quantity": "0"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "REMOVED"

    listed = client.get("/api/personal-cart/").json()
    assert listed == []


def test_remove_and_clear_cart(client, test_user):
    _login(client, test_user)
    m1 = client.post("/api/materials/", json={"name": "Remove Test A", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1}).json()
    m2 = client.post("/api/materials/", json={"name": "Remove Test B", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1}).json()
    item1 = client.post("/api/personal-cart/", json={"material_id": m1["id"], "quantity": "1"}).json()
    client.post("/api/personal-cart/", json={"material_id": m2["id"], "quantity": "1"})

    client.delete(f"/api/personal-cart/{item1['id']}")
    assert len(client.get("/api/personal-cart/").json()) == 1

    client.delete("/api/personal-cart/")
    assert client.get("/api/personal-cart/").json() == []


def test_cart_persists_across_relogin_same_user(client, test_user, db_session):
    """Matches the brief's exact test: add items, log out (re-auth as
    the same user simulates this - the cart must be database-backed,
    not tied to the in-memory session), log back in, cart is unchanged."""
    user = _create_and_login(client, db_session, "cartpersistuser", "cartpersistuser@example.com")
    material = client.post("/api/materials/", json={
        "name": "Persist Test Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
    }).json()
    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "5"})

    # Re-authenticate as the same user (simulating logout + login again).
    relogin = client.post("/api/auth/login", json={"identifier": "cartpersistuser@example.com", "password": "CartPass1!"})
    assert relogin.status_code == 200

    listed = client.get("/api/personal-cart/").json()
    assert len(listed) == 1
    assert float(listed[0]["quantity"]) == 5.0


def test_cart_is_completely_isolated_between_different_users(client, test_user, db_session):
    """The critical security requirement - User A's cart must be
    invisible to User B, enforced by the API itself, not the UI."""
    material = client.post("/api/materials/", json={
        "name": "Isolation Test Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
    }).json()

    user_a = _create_and_login(client, db_session, "cartuserA", "cartuserA@example.com")
    item_a = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "5"}).json()

    user_b = _create_and_login(client, db_session, "cartuserB", "cartuserB@example.com")
    # User B's own cart is empty - A's item does not appear.
    assert client.get("/api/personal-cart/").json() == []

    # User B cannot access A's specific cart item by id either.
    get_resp = client.put(f"/api/personal-cart/{item_a['id']}", json={"quantity": "99"})
    assert get_resp.status_code == 404

    delete_resp = client.delete(f"/api/personal-cart/{item_a['id']}")
    assert delete_resp.status_code == 404

    # Confirm A's item is genuinely untouched by B's attempts.
    resp = client.post("/api/auth/login", json={"identifier": "cartuserA@example.com", "password": "CartPass1!"})
    assert resp.status_code == 200
    a_items = client.get("/api/personal-cart/").json()
    assert len(a_items) == 1
    assert float(a_items[0]["quantity"]) == 5.0


def test_adding_to_cart_does_not_change_material_stock(client, test_user):
    """The explicit rule - a personal cart is a request
    list, not a purchase; inventory must be completely untouched."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "No Stock Change Material", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 1,
    }).json()
    before = material["current_stock"]

    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "5"})

    after = client.get(f"/api/materials/{material['id']}").json()["current_stock"]
    assert after == before
