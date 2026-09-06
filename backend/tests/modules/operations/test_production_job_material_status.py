"""Production job material-status (GET
/api/production-jobs/{id}/material-status) - Phase D dependency-aware
planning: is this job blocked by a real material shortage? Reuses
StockService.calculate_order_material_requirements for the job's own
order; no separate shortage calculation exists here."""
from tests.helpers import _login


def test_job_material_status_reports_real_shortage(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Job Shortage Test Sheet", "unit": "Sheets", "opening_stock": "2", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Job Shortage Test Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": "Job Shortage Client", "phone": "9000010199"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Cutting",
        "order_id": order["id"], "material_id": material["id"],
    }).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/material-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_shortage_data"] is True
    assert body["is_blocked_by_shortage"] is True
    assert float(body["shortage"]) == 3.0  # 5 required - 2 available


def test_job_material_status_no_shortage_when_stock_covers_it(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Job No Shortage Test Sheet", "unit": "Sheets", "opening_stock": "20", "minimum_stock": "1",
    }).json()
    product = client.post("/api/products/", json={
        "name": "Job No Shortage Test Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": "Job No Shortage Client", "phone": "9000010198"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Cutting",
        "order_id": order["id"], "material_id": material["id"],
    }).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/material-status")
    body = resp.json()
    assert body["has_shortage_data"] is True
    assert body["is_blocked_by_shortage"] is False


def test_job_without_order_or_material_has_no_shortage_data(client, test_user):
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Assembly"}).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/material-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_shortage_data"] is False
    assert body["is_blocked_by_shortage"] is False


def test_job_material_status_requires_auth(client):
    resp = client.get("/api/production-jobs/1/material-status")
    assert resp.status_code == 401


def test_job_material_status_unknown_job_returns_404(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/production-jobs/999999/material-status")
    assert resp.status_code == 404


def test_job_material_status_includes_supplier_options_when_blocked(client, test_user):
    """Family 130 section 8: a blocked job's material-status must show
    which supplier can actually resolve the shortage, not just the raw
    numbers - preferred supplier first regardless of price."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Job Shortage Supplier Test Sheet", "unit": "Sheets", "opening_stock": "2", "minimum_stock": "1",
    }).json()
    cheap_supplier = client.post("/api/suppliers/", json={"name": "Cheap Sheet Supplier"}).json()
    preferred_supplier = client.post("/api/suppliers/", json={"name": "Preferred Sheet Supplier"}).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": cheap_supplier["id"], "material_id": material["id"],
        "supplier_price": "400.00", "lead_time_days": 5, "is_preferred": False,
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": preferred_supplier["id"], "material_id": material["id"],
        "supplier_price": "550.00", "lead_time_days": 2, "is_preferred": True,
    })
    product = client.post("/api/products/", json={
        "name": "Job Shortage Supplier Test Product", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": "Job Shortage Supplier Client", "phone": "9000010200"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Cutting",
        "order_id": order["id"], "material_id": material["id"],
    }).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/material-status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_blocked_by_shortage"] is True
    assert float(body["recommended_purchase_quantity"]) == 3.0
    options = body["supplier_options"]
    assert len(options) == 2
    # Preferred supplier ranks first even though it is not the cheapest.
    assert options[0]["supplier_id"] == preferred_supplier["id"]
    assert options[0]["is_preferred"] is True
    assert options[0]["lead_time_days"] == 2
    assert options[1]["supplier_id"] == cheap_supplier["id"]
    assert options[1]["price"] == 400.0
