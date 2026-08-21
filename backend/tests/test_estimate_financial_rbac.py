"""Tests for a major gap found this turn - Estimates were fully open
to any authenticated role for both viewing (financial fields
unredacted) and mutation (create/update/revise), despite being an
inherently financial document."""
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


def test_master_sees_estimate_financials(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Master Client", "phone": "9000010059"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "50000", "labor_cost": "20000",
    }).json()

    resp = client.get(f"/api/estimates/{estimate['id']}").json()
    assert resp["material_cost"] is not None
    assert resp["total_cost"] is not None


def test_employee_estimate_financials_are_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Employee Client", "phone": "9000010060"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "50000", "labor_cost": "20000",
    }).json()

    _create_employee(client, db_session, "Estimate RBAC Employee", "estimaterbacuser", "estimaterbacuser@example.com")
    resp = client.get(f"/api/estimates/{estimate['id']}").json()
    assert resp["material_cost"] is None
    assert resp["labor_cost"] is None
    assert resp["discount"] is None
    assert resp["subtotal"] is None
    assert resp["tax_amount"] is None
    assert resp["total_cost"] is None
    # Non-financial workflow state remains real.
    assert resp["status"] is not None
    assert resp["estimate_code"] == estimate["estimate_code"]


def test_employee_estimate_line_item_pricing_is_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Items Client", "phone": "9000010061"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Cabinet", "unit": "Nos"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Cabinet", "category": "Material", "quantity": "1", "unit": "Nos", "rate": "15000.00", "product_id": product_id}],
    }).json()

    _create_employee(client, db_session, "Estimate RBAC Items Employee", "estimateitemsrbacuser", "estimateitemsrbacuser@example.com")
    resp = client.get(f"/api/estimates/{estimate['id']}").json()
    assert resp["line_items"][0]["rate"] is None
    assert resp["line_items"][0]["amount"] is None
    assert resp["line_items"][0]["description"] == "Cabinet"


def test_employee_cannot_create_estimate(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Create Client", "phone": "9000010062"}).json()["id"]
    _create_employee(client, db_session, "Estimate RBAC Create Employee", "estimatecreaterbacuser", "estimatecreaterbacuser@example.com")

    resp = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    })
    assert resp.status_code == 403


def test_employee_cannot_update_estimate(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Update Client", "phone": "9000010063"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    _create_employee(client, db_session, "Estimate RBAC Update Employee", "estimateupdaterbacuser", "estimateupdaterbacuser@example.com")
    resp = client.put(f"/api/estimates/{estimate['id']}", json={"discount": "1000"})
    assert resp.status_code == 403


def test_employee_cannot_revise_estimate(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Revise Client", "phone": "9000010064"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    _create_employee(client, db_session, "Estimate RBAC Revise Employee", "estimaterevisebacuser", "estimaterevisebacuser@example.com")
    resp = client.post(f"/api/estimates/{estimate['id']}/revise")
    assert resp.status_code == 403


def test_master_can_still_create_update_and_revise_estimates(client, test_user):
    """Backward compatibility - master retains full functionality."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Master Full Client", "phone": "9000010065"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()
    assert client.put(f"/api/estimates/{estimate['id']}", json={"discount": "500"}).status_code == 200
    assert client.post(f"/api/estimates/{estimate['id']}/revise").status_code == 201
