"""Tests for audit logging on estimates (create/update/revise) and
purchases (create/update/receive) - continuing the coverage started
with deletes, salary slips, and other financial mutations."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_create_estimate_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Audit Client"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "create_estimate" and l["record_id"] == estimate["id"]), None)
    assert match is not None
    assert match["new_value"]["client_id"] == client_id


def test_update_estimate_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Update Audit Client"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    resp = client.put(f"/api/estimates/{estimate['id']}", json={"material_cost": "12000"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "update_estimate" and l["record_id"] == estimate["id"]), None)
    assert match is not None
    assert match["old_value"]["material_cost"] == 10000.0
    assert match["new_value"]["material_cost"] == 12000.0


def test_revise_estimate_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Revise Audit Client"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    revision = client.post(f"/api/estimates/{estimate['id']}/revise").json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "revise_estimate" and l["record_id"] == revision["id"]), None)
    assert match is not None
    assert match["old_value"]["source_estimate_id"] == estimate["id"]


def test_create_purchase_is_audit_logged(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Purchase Audit Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Purchase Audit Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()

    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-22T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "create_purchase" and l["record_id"] == purchase["id"]), None)
    assert match is not None
    assert match["new_value"]["material_id"] == material["id"]


def test_receive_purchase_is_audit_logged(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Purchase Receive Audit Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Purchase Receive Audit Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-22T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18",
        "payment_status": "Paid", "receipt_status": "Ordered",
    }).json()

    client.post(f"/api/purchases/{purchase['id']}/receive")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "receive_purchase" and l["record_id"] == purchase["id"]), None)
    assert match is not None
    assert match["new_value"]["receipt_status"] == "Received"
