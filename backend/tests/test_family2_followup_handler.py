"""Tests for the follow-up-suggestions chatbot handler - the genuinely
half-finished item from Family 2 (data model was built, handler was
not). Uses real ClientActivity.follow_up_date records, never an
inferred suggestion."""
from datetime import datetime, timedelta


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_follow_up_due_shows_past_due_activity(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Follow Up Handler Test Client"}).json()["id"]
    past_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
    client.post("/api/client-activities/", json={
        "client_id": client_id, "activity_type": "Call", "date": "2026-08-15T00:00:00",
        "summary": "Discussed final pricing", "follow_up_date": past_date,
    })

    resp = client.post("/api/chat/", json={"message": "follow-ups due today"})
    assert resp.status_code == 200
    data = resp.json()
    assert "1 follow-up" in data["response"]
    assert any(r["label"] == "Follow Up Handler Test Client" for r in data["records"])


def test_future_follow_up_not_shown_as_due(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Future Follow Up Test Client"}).json()["id"]
    future_date = (datetime.utcnow() + timedelta(days=30)).strftime("%Y-%m-%dT00:00:00")
    client.post("/api/client-activities/", json={
        "client_id": client_id, "activity_type": "Note", "date": "2026-08-19T00:00:00",
        "summary": "Will follow up next month", "follow_up_date": future_date,
    })

    resp = client.post("/api/chat/", json={"message": "follow ups pending"})
    assert resp.status_code == 200
    names = [r["label"] for r in resp.json()["records"]]
    assert "Future Follow Up Test Client" not in names


def test_follow_up_requires_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Follow Up Permission Employee"}).json()
    user = User(
        username="followuppermuser", email="followuppermuser@example.com",
        full_name="Follow Up Perm User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "followuppermuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": "follow-ups due today"})
    assert "master account" in resp.json()["response"].lower()


def test_no_follow_ups_reports_honestly(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "any follow up pending"})
    assert resp.status_code == 200
    assert "no follow-ups" in resp.json()["response"].lower()
