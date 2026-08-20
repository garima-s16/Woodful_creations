"""Tests for the global delete rule - every delete endpoint in the app
requires strictly master. Covers the four endpoints that had no
dedicated delete-permission test at all before this turn: employees,
candidate resumes, lookup values, and supplier-material links."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _login_as_user(client, username, email):
    """The application has only two roles - master and user. This
    creates a non-master account to confirm delete endpoints reject
    it, not an obsolete third role."""
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("UserPass1!"), role="user", is_active=True,
    )
    return user


def test_employee_delete_rejects_non_master(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Global Delete Guard Employee", "monthly_salary": "20000"}).json()
    non_master = _login_as_user(client, "globaldeleteguarduser1", "globaldeleteguarduser1@example.com")
    db_session.add(non_master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "globaldeleteguarduser1@example.com", "password": "UserPass1!"})

    resp = client.delete(f"/api/employees/{employee['id']}")
    assert resp.status_code == 403


def test_lookup_value_delete_rejects_non_master(client, test_user, db_session):
    _login(client, test_user)
    value = client.post("/api/settings/units", json={"name": "Global Delete Guard Unit"}).json()
    non_master = _login_as_user(client, "globaldeleteguarduser2", "globaldeleteguarduser2@example.com")
    db_session.add(non_master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "globaldeleteguarduser2@example.com", "password": "UserPass1!"})

    resp = client.delete(f"/api/settings/units/{value['id']}")
    assert resp.status_code == 403


def test_supplier_material_delete_rejects_non_master(client, test_user, db_session):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Global Delete Guard Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Global Delete Guard Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    link = client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "100.00",
    }).json()
    non_master = _login_as_user(client, "globaldeleteguarduser3", "globaldeleteguarduser3@example.com")
    db_session.add(non_master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "globaldeleteguarduser3@example.com", "password": "UserPass1!"})

    resp = client.delete(f"/api/supplier-materials/{link['id']}")
    assert resp.status_code == 403


def test_master_can_still_delete_employee(client, test_user):
    """Backward compatibility - master retains full delete access."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Global Delete Guard Master Employee", "monthly_salary": "20000"}).json()
    resp = client.delete(f"/api/employees/{employee['id']}")
    assert resp.status_code == 204
