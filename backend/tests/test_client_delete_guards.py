"""Tests for the Client delete chain closed this turn - the endpoint
existed but was never called from any frontend page, and had no guard
against deleting a client with real orders/estimates history."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_master_can_delete_unreferenced_client(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Unreferenced Client", "phone": "9000010043"}).json()
    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 204


def test_cannot_delete_client_with_orders(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Order Client", "phone": "9000010044"}).json()
    client.post("/api/orders/", json={
        "client_id": created["id"], "order_date": "2026-08-17T00:00:00", "order_value": "10000", "advance": "0",
    })
    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 400
    assert "orders" in resp.json()["detail"].lower()


def test_cannot_delete_client_with_estimates(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Estimate Client", "phone": "9000010045"}).json()
    client.post("/api/estimates/", json={
        "client_id": created["id"], "material_cost": "5000", "labor_cost": "2000",
    })
    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 400
    assert "estimates" in resp.json()["detail"].lower()


def test_client_with_only_activities_deletes_cleanly(client, test_user):
    """Activities are historical notes, not financial records - they
    should not block deletion, and must be cleaned up rather than
    cause an unhandled foreign-key error."""
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Activity Client", "phone": "9000010046"}).json()
    client.post("/api/client-activities/", json={
        "client_id": created["id"], "activity_type": "Call", "date": "2026-08-17T00:00:00", "summary": "Discussed requirements",
    })
    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 204


def test_client_delete_rejects_plain_employee(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Employee Test Client", "phone": "9000010047"}).json()
    employee = client.post("/api/employees/", json={"name": "Delete Guard Employee", "monthly_salary": "20000"}).json()
    user = User(
        username="clientdeleteguarduser", email="clientdeleteguarduser@example.com", full_name="Client Delete Guard User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientdeleteguarduser@example.com", "password": "EmpPass1!"})

    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 403


def test_client_delete_is_strictly_master_only(client, test_user, db_session):
    """Global delete rule - only master, not any other role, can
    delete anything anywhere in the app."""
    from app.core.security import hash_password
    from app.models.user import User

    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Delete Guard Non-Master Test Client", "phone": "9000010048"}).json()
    non_master = User(
        username="clientdeleteguarduser", email="clientdeleteguarduser@example.com", full_name="Client Delete Guard User",
        password_hash=hash_password("UserPass1!"), role="user", is_active=True,
    )
    db_session.add(non_master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientdeleteguarduser@example.com", "password": "UserPass1!"})

    resp = client.delete(f"/api/clients/{created['id']}")
    assert resp.status_code == 403
