"""Tests for the Production Readiness Engine
(GET /api/production-jobs/{id}/readiness) - P0.3 section 2.
READY/PARTIALLY_READY/BLOCKED, reusing
StockService.calculate_order_material_requirements exactly (the same
calculation the material-status endpoint, dashboard, daily-tasks list
and AI chatbot all already use) - no separate, independently-drifting
shortage logic here."""
from tests.helpers import _login


def _make_job_against_order(client, material_id, product_qty_required, opening_stock, suffix, pending_qty=None, supplier_name=None):
    material_kwargs = {
        "name": f"Readiness Sheet {suffix}", "unit": "Sheets", "opening_stock": str(opening_stock), "minimum_stock": "1",
    }
    if material_id is None:
        material = client.post("/api/materials/", json=material_kwargs).json()
        material_id = material["id"]
    if pending_qty is not None:
        supplier = client.post("/api/suppliers/", json={"name": supplier_name or f"Readiness Supplier {suffix}"}).json()
        client.post("/api/purchases/", json={
            "date": "2026-08-01T00:00:00", "supplier_id": supplier["id"], "material_id": material_id,
            "quantity": str(pending_qty), "unit": "Sheets", "rate": "500.00", "gst_percent": "18",
            "receipt_status": "Ordered",
        })
    product = client.post("/api/products/", json={
        "name": f"Readiness Product {suffix}", "unit": "Piece",
        "materials_used": [{"material_id": material_id, "quantity_required": str(product_qty_required)}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": f"Readiness Client {suffix}", "phone": f"900001070{suffix}"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Cutting", "order_id": order["id"], "material_id": material_id,
    }).json()
    return job, material_id


def test_readiness_is_ready_when_material_is_fully_available(client, test_user):
    _login(client, test_user)
    job, _ = _make_job_against_order(client, None, product_qty_required=2, opening_stock=100, suffix="1")

    resp = client.get(f"/api/production-jobs/{job['id']}/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["readiness"] == "READY"
    assert "fully available" in body["reason"]


def test_readiness_is_blocked_when_shortage_has_no_pending_coverage(client, test_user):
    _login(client, test_user)
    job, _ = _make_job_against_order(client, None, product_qty_required=5, opening_stock=2, suffix="2")

    resp = client.get(f"/api/production-jobs/{job['id']}/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["readiness"] == "BLOCKED"
    assert "Readiness Sheet 2" in body["reason"]


def test_readiness_is_partially_ready_when_pending_purchase_covers_the_gap(client, test_user):
    """The key distinction this engine must get right: shortage is
    computationally 0 once a covering purchase is on order, but the
    material is not physically in stock yet - the job cannot actually
    start, so this must be PARTIALLY_READY, not READY."""
    _login(client, test_user)
    job, _ = _make_job_against_order(
        client, None, product_qty_required=5, opening_stock=2, suffix="3",
        pending_qty=3, supplier_name="Readiness Covering Supplier",
    )

    resp = client.get(f"/api/production-jobs/{job['id']}/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["readiness"] == "PARTIALLY_READY"
    assert "already on order" in body["reason"]


def test_readiness_blocked_by_employee_reported_blocker_overrides_material_check(client, test_user):
    """A job the employee has explicitly flagged as blocked must report
    that reason even if the material itself is fully available - the
    blocker is real, reported information, and must not be silently
    overridden by an unrelated material check."""
    _login(client, test_user)
    job, _ = _make_job_against_order(client, None, product_qty_required=2, opening_stock=100, suffix="4")
    client.put(f"/api/production-jobs/{job['id']}", json={"blocker_reason": "CNC machine is down for maintenance"})

    resp = client.get(f"/api/production-jobs/{job['id']}/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["readiness"] == "BLOCKED"
    assert body["reason"] == "CNC machine is down for maintenance"


def test_readiness_is_ready_for_a_completed_job_regardless_of_material(client, test_user):
    _login(client, test_user)
    job, _ = _make_job_against_order(client, None, product_qty_required=5, opening_stock=0, suffix="5")
    client.put(f"/api/production-jobs/{job['id']}", json={"status": "Completed"})

    resp = client.get(f"/api/production-jobs/{job['id']}/readiness")
    assert resp.status_code == 200
    assert resp.json()["readiness"] == "READY"


def test_readiness_is_ready_when_job_has_no_order_or_material_link(client, test_user):
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Assembly"}).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["readiness"] == "READY"
    assert "no linked order/material" in body["reason"]


def test_readiness_requires_auth(client):
    resp = client.get("/api/production-jobs/1/readiness")
    assert resp.status_code == 401


def test_readiness_unknown_job_returns_404(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/production-jobs/999999/readiness")
    assert resp.status_code == 404
