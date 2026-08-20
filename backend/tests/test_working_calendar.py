"""Tests for the working calendar system (Sections 4-5 of the
workforce brief) - working days computed dynamically per month from
the configured weekday pattern and date overrides, never a hardcoded
26. The explicit test criterion from the brief: verify no calculation
assumes a fixed day count across different months."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_default_weekday_config_is_mon_to_sat_working(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/working-calendar/weekdays")
    assert resp.status_code == 200
    weekdays = {w["weekday"]: w["is_working"] for w in resp.json()}
    assert weekdays["Monday"] is True
    assert weekdays["Saturday"] is True
    assert weekdays["Sunday"] is False


def test_working_days_differ_across_months(client, test_user):
    """The core requirement - February and August must not produce the
    same working-day count just because both used to default to 26."""
    _login(client, test_user)
    feb = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 2}).json()
    aug = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 8}).json()
    assert feb["working_days"] == 24  # 2026 is not a leap year: 28 days, 4 Sundays off
    assert aug["working_days"] == 26  # 31 days, 5 Sundays off
    assert feb["working_days"] != aug["working_days"]


def test_declared_holiday_reduces_working_days(client, test_user):
    _login(client, test_user)
    before = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 10}).json()["working_days"]

    client.post("/api/working-calendar/holidays", json={
        "date": "2026-10-02", "name": "Gandhi Jayanti", "is_working": False,
    })
    after = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 10}).json()["working_days"]
    assert after == before - 1


def test_special_working_day_increases_working_days(client, test_user):
    _login(client, test_user)
    # Find a Sunday in November 2026 to declare as a special working day
    before = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 11}).json()["working_days"]
    client.post("/api/working-calendar/holidays", json={
        "date": "2026-11-01", "name": "Special working Sunday", "is_working": True,
    })
    after = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 11}).json()["working_days"]
    assert after == before + 1


def test_weekday_config_requires_master_to_edit(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    weekday_id = client.get("/api/working-calendar/weekdays").json()[0]["id"]

    employee = client.post("/api/employees/", json={"name": "Calendar Permission Test Employee"}).json()
    user = User(
        username="calendarpermuser", email="calendarpermuser@example.com",
        full_name="Calendar Perm User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "calendarpermuser@example.com", "password": "EmpPass1!"})

    resp = client.put(f"/api/working-calendar/weekdays/{weekday_id}", json={"is_working": False})
    assert resp.status_code == 403


def test_attendance_summary_uses_actual_month_working_days(client, test_user):
    """Confirms the payroll suggestion endpoint genuinely uses the
    calendar-computed value, not a leftover fixed constant."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Payroll Calendar Integration Employee", "monthly_salary": "26000"}).json()

    resp = client.get("/api/salary-slips/attendance-summary", params={
        "employee_id": employee["id"], "month": "February", "year": "2026",
    })
    assert resp.json()["suggested_working_days"] == 24
