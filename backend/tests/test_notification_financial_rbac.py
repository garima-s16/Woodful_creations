"""Tests for a second gap found this turn: notification visibility was
an all-or-nothing broadcast/role split, which correctly hid financial
broadcasts from employees but incorrectly ALSO hid operational ones
(LOW_STOCK, OUT_OF_STOCK) they're explicitly supposed to see. Also
covers the dead-end deep link this same investigation surfaced."""
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


def test_employee_sees_broadcast_low_stock_notification(client, test_user, db_session):
    """The real bug found this turn - operational broadcasts must
    reach employees, not just master."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Notif RBAC Low Stock Material", "unit": "Sheets", "opening_stock": "1", "minimum_stock": "10",
    })

    _create_employee(client, db_session, "notiflowuser", "notiflowuser@example.com")
    notifications = client.get("/api/notifications/").json()
    assert any("Notif RBAC Low Stock Material" in n["title"] for n in notifications)


def test_employee_sees_broadcast_out_of_stock_notification(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Notif RBAC Out Of Stock Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    })

    _create_employee(client, db_session, "notifoosuser", "notifoosuser@example.com")
    notifications = client.get("/api/notifications/").json()
    assert any("Notif RBAC Out Of Stock Material" in n["title"] for n in notifications)


def test_employee_does_not_see_broadcast_payment_overdue_notification(client, test_user, db_session):
    """The genuinely financial broadcast must still stay hidden."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Notif RBAC Overdue Client"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "order_value": "50000.00", "advance": "0",
    })

    _create_employee(client, db_session, "notifoverdueuser", "notifoverdueuser@example.com")
    notifications = client.get("/api/notifications/").json()
    assert not any(n["notification_type"] == "PAYMENT_OVERDUE" for n in notifications)


def test_master_still_sees_payment_overdue_notification(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Notif RBAC Master Overdue Client"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "order_value": "60000.00", "advance": "0",
    })

    notifications = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "PAYMENT_OVERDUE" for n in notifications)


def test_purchase_received_notification_deep_link_is_accessible_to_everyone(client, test_user, db_session):
    """The dead-end link bug - PURCHASE_RECEIVED is visible to
    employees, so its action_path must not point at a page they can no
    longer access (/purchases is now master-only)."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Notif RBAC Purchase Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Notif RBAC Purchase Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-16T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })

    _create_employee(client, db_session, "notifpurchaseuser", "notifpurchaseuser@example.com")
    notifications = client.get("/api/notifications/").json()
    purchase_notif = next(n for n in notifications if n["notification_type"] == "PURCHASE_RECEIVED"
                           and "Notif RBAC Purchase Material" in n["title"])
    assert purchase_notif["action_path"] == f"/materials/{material['id']}"
    # And that page must genuinely be reachable by this employee.
    material_resp = client.get(f"/api/materials/{material['id']}")
    assert material_resp.status_code == 200
