"""Test for a direct, explicit gap from the access-control brief itself
- Section 4 says "Employee must not perform stock-changing operations",
but create_issue (which decreases current_stock) was open to any
authenticated role. Viewing stays open - Issues carry no financial
fields, matching "Employee can view stock"."""
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


def test_employee_cannot_create_stock_issue(client, test_user, db_session):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Issue RBAC Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()

    _create_employee(client, db_session, "Issue RBAC Employee", "issuerbacuser", "issuerbacuser@example.com")
    resp = client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })
    assert resp.status_code == 403

    # Confirm stock is genuinely untouched by the rejected attempt.
    unchanged = client.get(f"/api/materials/{material['id']}").json()
    assert float(unchanged["current_stock"]) == 10.0


def test_master_can_still_create_stock_issue(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Issue RBAC Master Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()

    resp = client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })
    assert resp.status_code == 201


def test_employee_can_still_view_issues(client, test_user, db_session):
    """Viewing stays open - Issues carry no financial fields, matching
    "Employee can view stock"."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Issue RBAC View Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })

    _create_employee(client, db_session, "Issue RBAC View Employee", "issueviewrbacuser", "issueviewrbacuser@example.com")
    resp = client.get("/api/issues/")
    assert resp.status_code == 200
