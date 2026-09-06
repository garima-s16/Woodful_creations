"""Tests for ProductionOperation (P0.3.3/3.4) - a single manufacturing
step within a ProductionJob, with a deliberately simple, single-
predecessor dependency (not a general workflow engine). Focused on the
real business rule: a dependent operation cannot be started/completed
while its declared predecessor is still incomplete."""
from tests.helpers import _login


def _make_job(client):
    return client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "General"}).json()


def test_operation_with_incomplete_dependency_cannot_be_started(client, test_user):
    _login(client, test_user)
    job = _make_job(client)
    cutting = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Cutting",
    }).json()
    cnc = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 2, "operation_name": "CNC",
        "depends_on_operation_id": cutting["id"],
    }).json()

    resp = client.put(f"/api/production-operations/{cnc['id']}", json={"status": "In Progress"})
    assert resp.status_code == 409
    assert "Cutting" in resp.json()["detail"]


def test_operation_becomes_unblocked_once_dependency_completes(client, test_user):
    _login(client, test_user)
    job = _make_job(client)
    cutting = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Cutting",
    }).json()
    cnc = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 2, "operation_name": "CNC",
        "depends_on_operation_id": cutting["id"],
    }).json()

    client.put(f"/api/production-operations/{cutting['id']}", json={"status": "Completed"})

    resp = client.put(f"/api/production-operations/{cnc['id']}", json={"status": "In Progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "In Progress"


def test_operation_list_reports_blocked_flag_without_starting_it(client, test_user):
    _login(client, test_user)
    job = _make_job(client)
    cutting = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Cutting",
    }).json()
    client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 2, "operation_name": "CNC",
        "depends_on_operation_id": cutting["id"],
    })

    resp = client.get("/api/production-operations/", params={"production_job_id": job["id"]})
    assert resp.status_code == 200
    rows = {r["operation_name"]: r for r in resp.json()}
    assert rows["Cutting"]["is_blocked_by_dependency"] is False
    assert rows["CNC"]["is_blocked_by_dependency"] is True


def test_operation_without_dependency_is_never_blocked(client, test_user):
    _login(client, test_user)
    job = _make_job(client)
    op = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Finishing",
    }).json()

    resp = client.put(f"/api/production-operations/{op['id']}", json={"status": "Completed"})
    assert resp.status_code == 200


def test_dependency_must_belong_to_the_same_production_job(client, test_user):
    _login(client, test_user)
    job_a = _make_job(client)
    job_b = _make_job(client)
    op_a = client.post("/api/production-operations/", json={
        "production_job_id": job_a["id"], "sequence": 1, "operation_name": "Cutting A",
    }).json()

    resp = client.post("/api/production-operations/", json={
        "production_job_id": job_b["id"], "sequence": 1, "operation_name": "CNC B",
        "depends_on_operation_id": op_a["id"],
    })
    assert resp.status_code == 400


def test_production_operations_require_auth(client):
    resp = client.get("/api/production-operations/")
    assert resp.status_code == 401


def test_employee_cannot_create_operation(client, test_user, db_session):
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    _login(client, test_user)
    job = _make_job(client)
    employee = User(
        username="prodopempuser", email="prodopempuser@example.com", full_name="Prod Op Employee",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "prodopempuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/production-operations/", json={
        "production_job_id": job["id"], "sequence": 1, "operation_name": "Unauthorized Op",
    })
    assert resp.status_code == 403
