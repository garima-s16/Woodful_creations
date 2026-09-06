"""Tests for GET /api/production-jobs/{id}/variance - planned vs actual
(P0.3 section 27/28). Never invents an actual value: duration variance
is computed only from operations that actually have actual_duration_minutes
recorded, and duration_complete distinguishes a partial variance from
the final one."""
from tests.helpers import _login


def test_quantity_variance_reflects_real_planned_vs_completed(client, test_user):
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Cutting", "planned_qty": 100, "completed_qty": 90,
    }).json()

    resp = client.get(f"/api/production-jobs/{job['id']}/variance")
    assert resp.status_code == 200
    body = resp.json()
    assert body["quantity_planned"] == 100
    assert body["quantity_completed"] == 90
    assert body["quantity_variance"] == -10
    assert body["quantity_variance_percent"] == -10.0


def test_duration_variance_none_when_no_actuals_recorded_yet(client, test_user):
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Cutting"}).json()
    client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Cut Sheets",
        "estimated_duration_minutes": 120,
    })

    resp = client.get(f"/api/production-jobs/{job['id']}/variance")
    body = resp.json()
    assert body["duration_planned_minutes"] == 120
    assert body["duration_actual_minutes"] is None
    assert body["duration_variance_minutes"] is None
    assert body["duration_complete"] is False


def test_duration_variance_computed_once_actual_is_recorded(client, test_user):
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Cutting"}).json()
    operation = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Cut Sheets",
        "estimated_duration_minutes": 120,
    }).json()
    client.put(f"/api/production-operations/{operation['id']}", json={"actual_duration_minutes": 150})

    resp = client.get(f"/api/production-jobs/{job['id']}/variance")
    body = resp.json()
    assert body["duration_planned_minutes"] == 120
    assert body["duration_actual_minutes"] == 150
    assert body["duration_variance_minutes"] == 30
    assert body["duration_complete"] is True
    assert body["operations_total"] == 1
    assert body["operations_with_actual_duration"] == 1


def test_duration_incomplete_when_only_some_operations_have_actuals(client, test_user):
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Cutting"}).json()
    op1 = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Cut Sheets",
        "estimated_duration_minutes": 60,
    }).json()
    client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 2, "operation_name": "Assemble",
        "estimated_duration_minutes": 90,
    })
    client.put(f"/api/production-operations/{op1['id']}", json={"actual_duration_minutes": 70})

    resp = client.get(f"/api/production-jobs/{job['id']}/variance")
    body = resp.json()
    assert body["operations_total"] == 2
    assert body["operations_with_actual_duration"] == 1
    assert body["duration_complete"] is False
    # Only the operation with a real actual counts toward the variance -
    # not the still-unrecorded second operation.
    assert body["duration_actual_minutes"] == 70
    assert body["duration_variance_minutes"] == 10


def test_variance_requires_auth(client):
    resp = client.get("/api/production-jobs/1/variance")
    assert resp.status_code == 401


def test_variance_unknown_job_returns_404(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/production-jobs/999999/variance")
    assert resp.status_code == 404
