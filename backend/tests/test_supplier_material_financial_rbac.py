"""Tests for SupplierMaterial pricing redaction - a real gap found
after the initial Materials/Purchases/Dashboard/Excel/Chatbot RBAC
pass. supplier_price/last_purchase_price are financial data; which
suppliers can provide a material, MOQ, and lead time are not."""
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


def test_master_sees_supplier_material_pricing(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "SM RBAC Master Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "SM RBAC Master Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "1500.00",
    })

    resp = client.get(f"/api/supplier-materials/by-material/{material['id']}").json()
    assert resp[0]["supplier_price"] is not None


def test_employee_supplier_material_pricing_is_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "SM RBAC Employee Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "SM RBAC Employee Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "1500.00", "moq": 10, "lead_time_days": 3,
    })

    _create_employee(client, db_session, "smrbacuser", "smrbacuser@example.com")
    resp = client.get(f"/api/supplier-materials/by-material/{material['id']}").json()
    assert resp[0]["supplier_price"] is None
    assert resp[0]["last_purchase_price"] is None
    # Operational (non-financial) fields remain visible.
    assert resp[0]["moq"] == 10
    assert resp[0]["lead_time_days"] == 3
    assert resp[0]["supplier_name"] == "SM RBAC Employee Supplier"


def test_employee_by_supplier_pricing_is_also_null(client, test_user, db_session):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "SM RBAC By Supplier Co"}).json()
    material = client.post("/api/materials/", json={
        "name": "SM RBAC By Supplier Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "800.00",
    })

    _create_employee(client, db_session, "smsuppbacuser", "smsuppbacuser@example.com")
    resp = client.get(f"/api/supplier-materials/by-supplier/{supplier['id']}").json()
    assert resp[0]["supplier_price"] is None


def test_employee_supplier_list_order_does_not_leak_relative_price(client, test_user, db_session):
    """The subtler fix - sorting by price.asc() even with the price
    number hidden still leaks which supplier is cheaper via list order.
    An employee's list must be ordered by something price-blind
    (preferred, then alphabetical) instead."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "SM RBAC Order Test Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    expensive_supplier = client.post("/api/suppliers/", json={"name": "Zebra Expensive Supplier"}).json()
    cheap_supplier = client.post("/api/suppliers/", json={"name": "Alpha Cheap Supplier"}).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": expensive_supplier["id"], "material_id": material["id"], "supplier_price": "5000.00",
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": cheap_supplier["id"], "material_id": material["id"], "supplier_price": "100.00",
    })

    _create_employee(client, db_session, "smorderrbacuser", "smorderrbacuser@example.com")
    resp = client.get(f"/api/supplier-materials/by-material/{material['id']}").json()
    names_in_order = [r["supplier_name"] for r in resp]
    # Alphabetical (price-blind), NOT price-ascending (which would put
    # the 100.00 supplier first, indirectly revealing it's cheaper).
    assert names_in_order == sorted(names_in_order)


def test_only_master_manager_can_create_supplier_material_link(client, test_user, db_session):
    """Already-correct behavior, confirmed unaffected by this change."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "SM RBAC Create Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "SM RBAC Create Test Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()

    _create_employee(client, db_session, "smcreaterbacuser", "smcreaterbacuser@example.com")
    resp = client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "100.00",
    })
    assert resp.status_code == 403
