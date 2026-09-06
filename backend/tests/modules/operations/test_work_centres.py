"""Tests for WorkCentre (P0.3.5) and its capacity check (P0.3.6)."""
from tests.helpers import _login


def test_create_and_list_work_centre(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/work-centres/", json={"name": "Test CNC", "type": "CNC", "capacity_hours_per_day": "8"})
    assert resp.status_code == 201
    centre = resp.json()
    assert float(centre["capacity_hours_per_day"]) == 8.0

    resp = client.get("/api/work-centres/")
    assert resp.status_code == 200
    assert any(c["name"] == "Test CNC" for c in resp.json())


def test_duplicate_work_centre_name_rejected(client, test_user):
    _login(client, test_user)
    client.post("/api/work-centres/", json={"name": "Duplicate CNC"})
    resp = client.post("/api/work-centres/", json={"name": "Duplicate CNC"})
    assert resp.status_code == 409


def test_capacity_conflict_detected_when_scheduled_work_exceeds_capacity(client, test_user):
    _login(client, test_user)
    centre = client.post("/api/work-centres/", json={"name": "Capacity CNC", "capacity_hours_per_day": "8"}).json()
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Cutting"}).json()
    client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Big Cut",
        "work_centre_id": centre["id"], "estimated_duration_minutes": 600,
        "start_time": "2026-08-19T09:00:00",
    })

    resp = client.get(f"/api/work-centres/{centre['id']}/capacity", params={"date": "2026-08-19"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["has_capacity_data"] is True
    assert body["scheduled_minutes"] == 600
    # 8 hours capacity = 480 minutes; 600 scheduled minutes exceeds it.
    assert body["status"] == "CAPACITY_CONFLICT"
    assert body["remaining_minutes"] == -120


def test_capacity_is_ok_when_scheduled_work_fits(client, test_user):
    _login(client, test_user)
    centre = client.post("/api/work-centres/", json={"name": "Fits CNC", "capacity_hours_per_day": "8"}).json()
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Cutting"}).json()
    client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Small Cut",
        "work_centre_id": centre["id"], "estimated_duration_minutes": 240,
        "start_time": "2026-08-19T09:00:00",
    })

    resp = client.get(f"/api/work-centres/{centre['id']}/capacity", params={"date": "2026-08-19"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "OK"
    assert body["remaining_minutes"] == 240


def test_capacity_reports_no_data_when_unconfigured(client, test_user):
    _login(client, test_user)
    centre = client.post("/api/work-centres/", json={"name": "Unconfigured CNC"}).json()
    resp = client.get(f"/api/work-centres/{centre['id']}/capacity")
    assert resp.status_code == 200
    assert resp.json()["has_capacity_data"] is False


def test_work_centres_require_auth(client):
    resp = client.get("/api/work-centres/")
    assert resp.status_code == 401
