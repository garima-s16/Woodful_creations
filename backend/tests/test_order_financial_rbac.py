"""Tests for a major gap found this turn - the core Order object
itself (order_value, advance, other_received, total_received, balance,
items_subtotal, payment_status, plus each line item's rate/amount) was
exposed to any authenticated role via list_orders/get_order, not just
the dashboard's summary view."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _create_employee(client, db_session, name, username, email):
    employee = client.post("/api/employees/", json={
        "name": name, "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200


def test_master_sees_order_financials(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Master Client", "phone": "9000010132"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "90000.00", "advance": "0",
    }).json()

    resp = client.get(f"/api/orders/{order['id']}").json()
    assert resp["order_value"] is not None
    assert resp["balance"] is not None
    assert resp["payment_status"] is not None


def test_employee_get_order_financials_are_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Employee Client", "phone": "9000010133"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "90000.00", "advance": "0",
    }).json()

    _create_employee(client, db_session, "Order RBAC Employee", "orderrbacuser", "orderrbacuser@example.com")
    resp = client.get(f"/api/orders/{order['id']}").json()
    assert resp["order_value"] is None
    assert resp["advance"] is None
    assert resp["other_received"] is None
    assert resp["total_received"] is None
    assert resp["balance"] is None
    assert resp["items_subtotal"] is None
    assert resp["payment_status"] is None
    # Non-financial order status remains real.
    assert resp["project_status"] is not None
    assert resp["progress_percent"] is not None
    assert resp["order_code"] == order["order_code"]


def test_employee_list_orders_financials_are_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC List Client", "phone": "9000010134"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "45000.00", "advance": "0",
    })

    _create_employee(client, db_session, "Order RBAC List Employee", "orderlistrbacuser", "orderlistrbacuser@example.com")
    orders = client.get("/api/orders/").json()
    match = next(o for o in orders if o["client_id"])
    assert match["order_value"] is None


def test_employee_cannot_derive_order_total_from_line_items(client, test_user, db_session):
    """The deeper part of this fix - redacting only the top-level
    order_value while leaving item.rate/item.amount visible would let
    anyone just sum the line items back to the real total."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Items Client", "phone": "9000010135"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Wardrobe", "unit": "Nos"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "0", "advance": "0",
        "items": [{"description": "Wardrobe", "quantity": "1", "unit": "Nos", "rate": "50000.00", "product_id": product_id}],
    }).json()

    _create_employee(client, db_session, "Order RBAC Items Employee", "orderitemsrbacuser", "orderitemsrbacuser@example.com")
    resp = client.get(f"/api/orders/{order['id']}").json()
    assert len(resp["items"]) == 1
    assert resp["items"][0]["rate"] is None
    assert resp["items"][0]["amount"] is None
    # Non-financial item fields remain visible - still shows what was ordered.
    assert resp["items"][0]["description"] == "Wardrobe"
    assert resp["items"][0]["quantity"] is not None


def test_master_sees_order_line_item_pricing(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Items Master Client", "phone": "9000010136"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Kitchen", "unit": "Nos"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "0", "advance": "0",
        "items": [{"description": "Kitchen", "quantity": "1", "unit": "Nos", "rate": "30000.00", "product_id": product_id}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}").json()
    assert resp["items"][0]["rate"] is not None
    assert resp["items"][0]["amount"] is not None
