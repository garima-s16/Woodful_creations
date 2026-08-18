"""Tests for the global delete rule applied this turn - every delete
endpoint in the app requires strictly master, not master-or-manager.
Covers the four endpoints that had no dedicated delete-permission test
at all before this turn: employees, candidate resumes, lookup values,
and supplier-material links."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _login_as_manager(client, username, email):
    manager = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("ManagerPass1!"), role="manager", is_active=True,
    )
    return manager


def test_employee_delete_rejects_manager(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Global Delete Guard Employee", "monthly_salary": "20000"}).json()
    manager = _login_as_manager(client, "globaldeleteguardmgr1", "globaldeleteguardmgr1@example.com")
    db_session.add(manager)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "globaldeleteguardmgr1@example.com", "password": "ManagerPass1!"})

    resp = client.delete(f"/api/employees/{employee['id']}")
    assert resp.status_code == 403


def test_lookup_value_delete_rejects_manager(client, test_user, db_session):
    _login(client, test_user)
    value = client.post("/api/settings/units", json={"name": "Global Delete Guard Unit"}).json()
    manager = _login_as_manager(client, "globaldeleteguardmgr2", "globaldeleteguardmgr2@example.com")
    db_session.add(manager)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "globaldeleteguardmgr2@example.com", "password": "ManagerPass1!"})

    resp = client.delete(f"/api/settings/units/{value['id']}")
    assert resp.status_code == 403


def test_supplier_material_delete_rejects_manager(client, test_user, db_session):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Global Delete Guard Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Global Delete Guard Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    link = client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "100.00",
    }).json()
    manager = _login_as_manager(client, "globaldeleteguardmgr3", "globaldeleteguardmgr3@example.com")
    db_session.add(manager)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "globaldeleteguardmgr3@example.com", "password": "ManagerPass1!"})

    resp = client.delete(f"/api/supplier-materials/{link['id']}")
    assert resp.status_code == 403


def test_master_can_still_delete_employee(client, test_user):
    """Backward compatibility - master retains full delete access."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Global Delete Guard Master Employee", "monthly_salary": "20000"}).json()
    resp = client.delete(f"/api/employees/{employee['id']}")
    assert resp.status_code == 204
