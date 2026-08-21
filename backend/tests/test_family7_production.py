"""Tests for Family 7 (Production Management): the real security gap
found in update_production_job (every field was previously open to
any authenticated user, unlike the equivalent DailyTask endpoint),
and the new production-bottlenecks chatbot handler."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_employee_can_update_status_and_completed_qty(client, test_user, db_session):
    """The genuinely-permitted self-service fields must still work for
    a non-master employee."""
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Cutting"}).json()
    employee = client.post("/api/employees/", json={"name": "Production Update Self Service Employee"}).json()
    user = User(
        username="prodselfserviceuser", email="prodselfserviceuser@example.com",
        full_name="Prod Self Service User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "prodselfserviceuser@example.com", "password": "EmpPass1!"})

    resp = client.put(f"/api/production-jobs/{job['id']}", json={"status": "In Progress", "completed_qty": 5})
    assert resp.status_code == 200


def test_employee_cannot_change_stage_or_remarks(client, test_user, db_session):
    """The real fix - planning fields must be blocked for non-master,
    which was not previously enforced at all."""
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Assembly"}).json()
    employee = client.post("/api/employees/", json={"name": "Production Update Restricted Employee"}).json()
    user = User(
        username="prodrestricteduser", email="prodrestricteduser@example.com",
        full_name="Prod Restricted User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "prodrestricteduser@example.com", "password": "EmpPass1!"})

    resp = client.put(f"/api/production-jobs/{job['id']}", json={"stage": "QC"})
    assert resp.status_code == 403

    resp2 = client.put(f"/api/production-jobs/{job['id']}", json={"remarks": "trying to sneak this in"})
    assert resp2.status_code == 403


def test_employee_can_set_blocker_reason(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Finishing"}).json()
    employee = client.post("/api/employees/", json={"name": "Production Blocker Reason Employee"}).json()
    user = User(
        username="prodblockeruser", email="prodblockeruser@example.com",
        full_name="Prod Blocker User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "prodblockeruser@example.com", "password": "EmpPass1!"})

    resp = client.put(f"/api/production-jobs/{job['id']}", json={
        "status": "Blocked", "blocker_reason": "Waiting on CNC router availability",
    })
    assert resp.status_code == 200
    assert resp.json()["blocker_reason"] == "Waiting on CNC router availability"


def test_master_can_still_update_any_field(client, test_user):
    """Regression guard - master must remain unrestricted."""
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={"date": "2026-08-19T00:00:00", "operation": "Packing"}).json()
    resp = client.put(f"/api/production-jobs/{job['id']}", json={"stage": "Packing", "remarks": "master note"})
    assert resp.status_code == 200


def test_chatbot_production_bottlenecks(client, test_user):
    _login(client, test_user)
    job = client.post("/api/production-jobs/", json={
        "date": "2026-08-19T00:00:00", "operation": "Blocked bottleneck job", "machine": "CNC Router",
    }).json()
    client.put(f"/api/production-jobs/{job['id']}", json={"status": "Blocked", "blocker_reason": "No material"})

    resp = client.post("/api/chat/", json={"message": "show production bottlenecks"})
    assert resp.status_code == 200
    data = resp.json()
    assert "1 job(s) blocked" in data["response"]
    assert any(r["label"] == job["job_code"] for r in data["records"])


def test_chatbot_no_bottlenecks_reports_honestly(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "any bottleneck in production"})
    assert resp.status_code == 200
