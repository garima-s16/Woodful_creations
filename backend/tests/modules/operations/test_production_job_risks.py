"""Tests for GET /api/production-jobs/{id}/risks - Production Risk
(P0.3 section 29). Always a list of individually-explained findings,
never a single opaque score; an empty list is a real "nothing found
from checkable data", not a claim of guaranteed safety."""
from datetime import datetime, timedelta
from tests.helpers import _login


def test_no_risks_when_everything_is_fine(client, test_user):
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Assembly"}).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/risks")
    assert resp.status_code == 200
    assert resp.json()["risks"] == []


def test_completed_job_has_no_risks_regardless_of_material(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={"name": "Risk Test Sheet A", "unit": "Sheets", "opening_stock": "0"}).json()
    product = client.post("/api/products/", json={
        "name": "Risk Test Product A", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": "Risk Test Client A", "phone": "9000010801"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Cutting", "order_id": order["id"], "material_id": material["id"],
    }).json()
    client.put(f"/api/production-jobs/{job['id']}", json={"status": "Completed"})

    resp = client.get(f"/api/production-jobs/{job['id']}/risks")
    assert resp.json()["risks"] == []


def test_material_shortage_produces_a_high_severity_risk(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={"name": "Risk Test Sheet B", "unit": "Sheets", "opening_stock": "0"}).json()
    product = client.post("/api/products/", json={
        "name": "Risk Test Product B", "unit": "Piece",
        "materials_used": [{"material_id": material["id"], "quantity_required": "5"}],
    }).json()
    client_id = client.post("/api/clients/", json={"name": "Risk Test Client B", "phone": "9000010802"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00",
        "items": [{"description": "Item", "quantity": "1", "unit": "Piece", "rate": "5000", "product_id": product["id"]}],
    }).json()
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Cutting", "order_id": order["id"], "material_id": material["id"],
    }).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/risks")
    risks = resp.json()["risks"]
    shortage_risks = [r for r in risks if r["type"] == "material_shortage"]
    assert len(shortage_risks) == 1
    assert shortage_risks[0]["severity"] == "high"
    assert "Risk Test Sheet B" in shortage_risks[0]["why"]


def test_dependency_blockage_produces_a_risk_per_blocked_operation(client, test_user):
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Assembly"}).json()
    cutting = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Risk Test Cutting",
    }).json()
    client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 2, "operation_name": "Risk Test CNC",
        "depends_on_operation_id": cutting["id"],
    })

    resp = client.get(f"/api/production-jobs/{job['id']}/risks")
    risks = resp.json()["risks"]
    dep_risks = [r for r in risks if r["type"] == "dependency_blockage"]
    assert len(dep_risks) == 1
    assert "Risk Test CNC" in dep_risks[0]["what"]
    assert "Risk Test Cutting" in dep_risks[0]["why"]


def test_capacity_overload_produces_a_risk(client, test_user):
    _login(client, test_user)
    centre = client.post("/api/work-centres/", json={"name": "Risk Test CNC Centre", "capacity_hours_per_day": "8"}).json()
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Cutting"}).json()
    client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Risk Test Overload Op",
        "work_centre_id": centre["id"], "estimated_duration_minutes": 600, "start_time": "2026-08-19T09:00:00",
    })

    resp = client.get(f"/api/production-jobs/{job['id']}/risks")
    risks = resp.json()["risks"]
    capacity_risks = [r for r in risks if r["type"] == "capacity_overload"]
    assert len(capacity_risks) == 1
    assert "Risk Test CNC Centre" in capacity_risks[0]["what"]
    assert capacity_risks[0]["when"] == "2026-08-19"


def test_schedule_risk_when_delivery_date_already_passed(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Risk Test Client C", "phone": "9000010803"}).json()["id"]
    past_date = (datetime.utcnow() - timedelta(days=5)).isoformat()
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "delivery_date": past_date,
    }).json()
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Assembly", "order_id": order["id"],
    }).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/risks")
    risks = resp.json()["risks"]
    schedule_risks = [r for r in risks if r["type"] == "schedule_risk"]
    assert len(schedule_risks) == 1
    assert schedule_risks[0]["severity"] == "high"
    assert "already passed" in schedule_risks[0]["what"]


def test_schedule_risk_when_delivery_date_imminent(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Risk Test Client D", "phone": "9000010804"}).json()["id"]
    soon_date = (datetime.utcnow() + timedelta(days=2)).isoformat()
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "delivery_date": soon_date,
    }).json()
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Assembly", "order_id": order["id"],
    }).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/risks")
    risks = resp.json()["risks"]
    schedule_risks = [r for r in risks if r["type"] == "schedule_risk"]
    assert len(schedule_risks) == 1
    assert schedule_risks[0]["severity"] == "medium"
    assert "imminent" in schedule_risks[0]["what"]


def test_risks_requires_auth(client):
    resp = client.get("/api/production-jobs/1/risks")
    assert resp.status_code == 401


def test_risks_unknown_job_returns_404(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/production-jobs/999999/risks")
    assert resp.status_code == 404
