"""Tests for the audit-logging gap found in the P0/P1 hardening
review - deletion is the most irreversible, highest-stakes action in
the app, and only 3 of 8 delete endpoints previously recorded an
audit trail entry at all."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_material_deletion_is_audit_logged(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Audit Log Test Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()

    client.delete(f"/api/materials/{material['id']}")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "delete_material" and l["record_id"] == material["id"]), None)
    assert match is not None
    assert match["module_name"] == "materials"
    assert match["old_value"]["name"] == "Audit Log Test Material"


def test_supplier_deletion_is_audit_logged(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Audit Log Test Supplier"}).json()

    client.delete(f"/api/suppliers/{supplier['id']}")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "delete_supplier" and l["record_id"] == supplier["id"]), None)
    assert match is not None


def test_client_deletion_is_audit_logged(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Audit Log Test Client"}).json()

    client.delete(f"/api/clients/{created['id']}")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "delete_client" and l["record_id"] == created["id"]), None)
    assert match is not None


def test_employee_deletion_is_audit_logged(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Audit Log Test Employee"}).json()

    client.delete(f"/api/employees/{employee['id']}")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "delete_employee" and l["record_id"] == employee["id"]), None)
    assert match is not None
