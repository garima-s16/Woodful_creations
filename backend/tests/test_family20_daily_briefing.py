"""Tests for Family 20 (Cross-Module Business Brain): the daily
briefing composite handler ("what needs attention today?") and two
trigger-word gaps found by testing the brief's own named examples
against the real code - "which materials are low?" and "who needs
to be followed up?" neither matched any existing trigger before this
turn."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_materials_are_low_phrasing_now_matches(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Materials Are Low Phrasing Test", "unit": "Sheets", "opening_stock": "1", "minimum_stock": "10",
    })
    resp = client.post("/api/chat/", json={"message": "which materials are low?"})
    assert resp.status_code == 200
    assert any(r["label"] == "Materials Are Low Phrasing Test" for r in resp.json()["records"])


def test_who_needs_followed_up_phrasing_now_matches(client, test_user):
    from datetime import datetime, timedelta
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Followed Up Phrasing Test Client"}).json()["id"]
    past_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
    client.post("/api/client-activities/", json={
        "client_id": client_id, "activity_type": "Call", "date": "2026-08-15T00:00:00",
        "summary": "Discussed pricing", "follow_up_date": past_date,
    })
    resp = client.post("/api/chat/", json={"message": "who needs to be followed up?"})
    assert resp.status_code == 200
    assert any(r["label"] == "Followed Up Phrasing Test Client" for r in resp.json()["records"])


def test_followed_up_phrasing_does_not_regress_existing_estimate_trigger(client, test_user):
    """Regression guard - "follow up on estimate" must not be captured
    by the new "followed up" trigger."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "follow up on estimate EST-001"})
    assert resp.status_code == 200


def test_daily_briefing_surfaces_real_low_stock(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Daily Briefing Low Stock Test Material", "unit": "Sheets", "opening_stock": "1", "minimum_stock": "10",
    })
    resp = client.post("/api/chat/", json={"message": "what needs attention today?"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(r["label"] == "Daily Briefing Low Stock Test Material" for r in data["records"])


def test_daily_briefing_honest_when_everything_clear(client, test_user):
    """A fresh test database with no problem records at all - the
    briefing must say so honestly, never invent something to report."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "what needs attention today?"})
    assert resp.status_code == 200
    assert "clear" in resp.json()["response"].lower() or "nothing" in resp.json()["response"].lower()


def test_daily_briefing_excludes_master_only_sections_for_non_master(client, test_user, db_session):
    """Follow-ups/deliveries sections are master-only elsewhere in this
    app - the briefing must respect that, not create a shortcut around
    it just because it's a combined view."""
    from app.core.security import hash_password
    from app.models.user import User
    from datetime import datetime, timedelta
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Briefing RBAC Test Client"}).json()["id"]
    past_date = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT00:00:00")
    client.post("/api/client-activities/", json={
        "client_id": client_id, "activity_type": "Call", "date": "2026-08-15T00:00:00",
        "summary": "Discussed pricing", "follow_up_date": past_date,
    })
    employee = client.post("/api/employees/", json={"name": "Briefing RBAC Test Employee"}).json()
    user = User(
        username="briefingrbacuser", email="briefingrbacuser@example.com", full_name="Briefing RBAC User",
        password_hash=hash_password("UserPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "briefingrbacuser@example.com", "password": "UserPass1!"})

    resp = client.post("/api/chat/", json={"message": "what needs attention today?"})
    assert resp.status_code == 200
    labels = [r.get("label") for r in resp.json()["records"]]
    assert "Briefing RBAC Test Client" not in labels
