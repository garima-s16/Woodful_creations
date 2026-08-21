"""Tests for the seeded company holidays (Section 13 - demo data must
include working-calendar data and company holidays). Verifies the
seed function itself produces the right data by calling it directly
against the test database - the test fixtures use a fresh, empty
database, not the dev database seed_sample_data.py's __main__ block
populates, so this cannot rely on demo data already being present."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from seed_sample_data import seed_company_holidays


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_seeded_holidays_are_listed(client, test_user, db_session):
    _login(client, test_user)
    seed_company_holidays(db_session)

    resp = client.get("/api/working-calendar/holidays")
    assert resp.status_code == 200
    names = [h["name"] for h in resp.json()]
    assert "Independence Day" in names
    assert "Gandhi Jayanti" in names


def test_seeded_holiday_reduces_october_working_days(client, test_user, db_session):
    """Confirms the seeded Gandhi Jayanti holiday genuinely affects the
    real calendar calculation, not just that a row exists. October is
    used specifically because it's the only seeded month with a single,
    unopposed holiday - August also has a special working day from the
    same seed call, which would cancel out Independence Day's effect
    and make that month a misleading choice for this assertion."""
    _login(client, test_user)
    without_holiday = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 10}).json()["working_days"]

    seed_company_holidays(db_session)
    with_holiday = client.get("/api/working-calendar/working-days", params={"year": 2026, "month": 10}).json()["working_days"]

    assert with_holiday == without_holiday - 1
