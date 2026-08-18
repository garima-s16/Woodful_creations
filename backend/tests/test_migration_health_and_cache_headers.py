"""Tests for two P0 audit findings: (1) a failed startup migration
must not let /health silently claim "ok", and (2) sensitive document
downloads (salary slips, PDFs, Excel exports) must carry an explicit
no-store cache-control header."""
from app.main import _migration_state


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_health_check_ok_when_migrations_succeeded(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_health_check_reports_degraded_on_migration_failure(client):
    """Simulates a failed startup migration (rather than actually
    breaking the schema, which the in-memory SQLite fixture doesn't
    support) and confirms /health honestly reflects it rather than
    silently returning "ok"."""
    original = dict(_migration_state)
    try:
        _migration_state["healthy"] = False
        _migration_state["error"] = "simulated migration failure"
        resp = client.get("/health")
        assert resp.status_code == 503
        assert resp.json()["status"] == "degraded"
    finally:
        _migration_state["healthy"] = original["healthy"]
        _migration_state["error"] = original["error"]


def test_excel_export_has_no_store_cache_control(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/reports/tasks.xlsx")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-store, private"


def test_salary_slip_pdf_has_no_store_cache_control(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Cache Header Test Employee"}).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "9000", "da": "0", "hra": "0", "overtime_amount": "0",
        "pf_deduction": "0", "tds_deduction": "0", "other_deductions": "0",
    }).json()
    resp = client.get(f"/api/reports/salary-slips/{slip['id']}.pdf")
    assert resp.status_code == 200
    assert resp.headers.get("cache-control") == "no-store, private"
