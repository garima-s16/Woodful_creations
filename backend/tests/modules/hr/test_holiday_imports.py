"""Company holiday import - commit-to-DB persistence chain. Previously
untested: holiday-imports/commit had only ever been proven to return
HTTP 200, never proven to actually write real CompanyHoliday rows to
the database, or that a same-date row is genuinely skipped (not
duplicated or silently overwritten) unless overwrite_existing is
explicitly set. Mirrors test_inventory_import.py's pattern - re-fetch
via a separate client.get() call, which the app's per-request session
override makes a genuine fresh-session read-back, not just trusting
the commit response body."""
from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


def test_holiday_import_commit_creates_real_persisted_holiday(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/holiday-imports/commit", json={"rows": [{
        "date": "2026-10-02", "name": "Holiday Import Test Day", "is_working": False,
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["created"] == 1
    assert body["error"] is None

    holidays = client.get("/api/working-calendar/holidays").json()
    match = next((h for h in holidays if h["name"] == "Holiday Import Test Day"), None)
    assert match is not None
    assert match["is_working"] is False


def test_holiday_import_commit_skips_existing_date_without_overwrite(client, test_user):
    _login(client, test_user)
    client.post("/api/holiday-imports/commit", json={"rows": [{
        "date": "2026-10-03", "name": "Holiday Import Original Name", "is_working": False,
    }]})

    resp = client.post("/api/holiday-imports/commit", json={"rows": [{
        "date": "2026-10-03", "name": "Holiday Import Should Not Apply", "is_working": False,
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["skipped"] == 1
    assert body["created"] == 0

    holidays = client.get("/api/working-calendar/holidays").json()
    match = next(h for h in holidays if h["date"].startswith("2026-10-03"))
    assert match["name"] == "Holiday Import Original Name"  # unchanged, not overwritten


def test_holiday_import_commit_overwrites_when_explicitly_requested(client, test_user):
    _login(client, test_user)
    client.post("/api/holiday-imports/commit", json={"rows": [{
        "date": "2026-10-04", "name": "Holiday Import Before Overwrite", "is_working": False,
    }]})

    resp = client.post("/api/holiday-imports/commit", json={"rows": [{
        "date": "2026-10-04", "name": "Holiday Import After Overwrite", "is_working": True,
        "overwrite_existing": True,
    }]})
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == 1

    holidays = client.get("/api/working-calendar/holidays").json()
    match = next(h for h in holidays if h["date"].startswith("2026-10-04"))
    assert match["name"] == "Holiday Import After Overwrite"
    assert match["is_working"] is True


def test_holiday_import_commit_requires_master(client, db_session):
    employee = User(
        username="holidayimportuser", email="holidayimportuser@example.com", full_name="Holiday Import User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "holidayimportuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.post("/api/holiday-imports/commit", json={"rows": [{
        "date": "2026-10-05", "name": "Unauthorized Holiday", "is_working": False,
    }]})
    assert resp.status_code == 403


def test_holiday_import_template_requires_master(client, db_session):
    employee = User(
        username="holidaytemplateuser", email="holidaytemplateuser@example.com", full_name="Holiday Template User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": "holidaytemplateuser@example.com", "password": "EmpPass1!"})
    assert resp.status_code == 200

    resp = client.get("/api/holiday-imports/template")
    assert resp.status_code == 403


def test_holiday_import_template_unauthenticated_rejected(client):
    resp = client.get("/api/holiday-imports/template")
    assert resp.status_code in (401, 403)
