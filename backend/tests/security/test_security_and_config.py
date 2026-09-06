"""Consolidated smaller feature/validation tests: GSTIN validation,
settings/config edge cases, staff dashboard performance RBAC, client
financial RBAC (direct + Excel export), PDF text-escaping safety,
client activities, Excel formula-injection safety, global security
(rate limiting, DEBUG/production cross-field validation), task
category/completion-timestamp fields, candidate field validation,
migration-health/cache-header checks, core authentication (login/
session), financial-mutation audit logging, salary-slip audit logging,
delete-audit logging (material/supplier/client/employee), and
master-only delete enforcement across entity types."""
import io
import os
import time
from openpyxl import load_workbook

from app.platform.security.security import hash_password
from app.modules.auth.models import User
from app.shared.document_style import pdf_text
from app.main import _migration_state
from tests.helpers import _login


# ===========================================================================
# From test_gstin_validation.py
# ===========================================================================
def test_short_gstin_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "GSTIN Test Supplier", "gstin": "TOOSHORT"})
    assert resp.status_code == 422


def test_valid_15_char_gstin_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "GSTIN Valid Supplier", "gstin": "27AAAAA0000A1Z5"})
    assert resp.status_code == 201
    assert resp.json()["gstin"] == "27AAAAA0000A1Z5"


def test_empty_gstin_allowed(client, test_user):
    """GSTIN is optional - not every supplier will have one recorded
    immediately."""
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "GSTIN Empty Supplier"})
    assert resp.status_code == 201


def test_update_also_validates_gstin(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "GSTIN Update Supplier"}).json()
    resp = client.put(f"/api/suppliers/{supplier['id']}", json={"gstin": "TOOSHORT"})
    assert resp.status_code == 422

# ===========================================================================
# From test_config.py
# ===========================================================================
def test_settings_accepts_comma_separated_cors_origins(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key-not-for-real-use-1234567890")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    # Re-import fresh so it picks up the monkeypatched env vars rather than
    # any cached settings instance from a prior test.
    import importlib
    from app.platform.configuration import config as config_module
    importlib.reload(config_module)

    fresh_settings = config_module.Settings()
    assert fresh_settings.cors_origins_list == [
        "http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000",
    ]


def test_settings_allowed_extensions_split_correctly(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key-not-for-real-use-1234567890")
    monkeypatch.setenv("ALLOWED_EXTENSIONS", "pdf,xlsx,docx")

    import importlib
    from app.platform.configuration import config as config_module
    importlib.reload(config_module)

    fresh_settings = config_module.Settings()
    assert fresh_settings.allowed_extensions_list == ["pdf", "xlsx", "docx"]

# ===========================================================================
# From test_staff_dashboard_performance_rbac.py
# ===========================================================================
def test_master_sees_all_employee_performance(client, test_user):
    _login(client, test_user)
    client.post("/api/employees/", json={"name": "Perf RBAC Employee One"})
    client.post("/api/employees/", json={"name": "Perf RBAC Employee Two"})

    resp = client.get("/api/dashboard/staff").json()
    names = [p["employee"] for p in resp["employee_performance"]]
    assert "Perf RBAC Employee One" in names
    assert "Perf RBAC Employee Two" in names


def test_employee_sees_only_own_performance(client, test_user, db_session):
    _login(client, test_user)
    other = client.post("/api/employees/", json={"name": "Perf RBAC Other Employee"}).json()
    own = client.post("/api/employees/", json={"name": "Perf RBAC Own Employee"}).json()
    user = User(
        username="perfrbacuser", email="perfrbacuser@example.com", full_name="Perf RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=own["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "perfrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/dashboard/staff").json()
    names = [p["employee"] for p in resp["employee_performance"]]
    assert "Perf RBAC Own Employee" in names
    assert "Perf RBAC Other Employee" not in names

# ===========================================================================
# From test_client_financial_rbac.py
# ===========================================================================
def test_master_sees_client_total_sales(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Client RBAC Master Test", "phone": "9000010049"}).json()
    resp = client.get(f"/api/clients/{created['id']}").json()
    assert resp["total_sales"] is not None


def test_employee_client_total_sales_is_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Client RBAC Employee Test", "phone": "9000010050"}).json()
    client.post("/api/orders/", json={
        "client_id": created["id"], "order_date": "2026-08-16T00:00:00", "order_value": "80000.00", "advance": "0",
    })

    employee = client.post("/api/employees/", json={
        "name": "Client RBAC Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username="clientrbacuser", email="clientrbacuser@example.com", full_name="Client RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/clients/{created['id']}").json()
    assert resp["total_sales"] is None
    # Non-financial fields remain real - total_orders is a count, not money.
    assert resp["total_orders"] == 1
    assert resp["name"] == "Client RBAC Employee Test"

# ===========================================================================
# From test_pdf_text_safety.py
# ===========================================================================
def test_escapes_ampersand_and_angle_brackets():
    assert pdf_text("Sharma & Sons") == "Sharma &amp; Sons"
    assert pdf_text("<b>fake bold</b>") == "&lt;b&gt;fake bold&lt;/b&gt;"


def test_none_becomes_empty_string():
    assert pdf_text(None) == ""


def test_plain_text_unaffected():
    assert pdf_text("Siddharth Residence") == "Siddharth Residence"


def test_non_string_values_are_stringified():
    assert pdf_text(42) == "42"


def test_order_pdf_generates_with_malicious_remarks(client, test_user):
    """The real, end-to-end guarantee - a remarks field crafted to
    break XML parsing must not crash PDF generation."""
    resp_login = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp_login.status_code == 200

    client_id = client.post("/api/clients/", json={"name": "PDF Safety Client", "phone": "9000010170"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "10000", "advance": "0",
        "remarks": '<b onclick="evil()">Fake &injected tag</b> & unescaped <ampersand',
    }).json()

    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000

# ===========================================================================
# From test_client_activities.py
# ===========================================================================
def _create_client(client):
    resp = client.post("/api/clients/", json={"client_code": "CL-ACT", "name": "Activity Test Client", "phone": "9000010040"})
    return resp.json()["id"]


def test_log_and_list_client_activity(client, test_user):
    _login(client, test_user)
    client_id = _create_client(client)

    resp = client.post("/api/client-activities/", json={
        "client_id": client_id, "activity_type": "Call", "date": "2026-08-11T10:00:00",
        "summary": "Discussed dining table dimensions and delivery timeline.", "logged_by": "Garima",
    })
    assert resp.status_code == 201

    listed = client.get("/api/client-activities/", params={"client_id": client_id})
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["activity_type"] == "Call"


def test_activities_filtered_by_client(client, test_user):
    _login(client, test_user)
    client_a = _create_client(client)
    client_b_resp = client.post("/api/clients/", json={"client_code": "CL-ACT-B", "name": "Other Client", "phone": "9000010041"})
    client_b = client_b_resp.json()["id"]

    client.post("/api/client-activities/", json={
        "client_id": client_a, "activity_type": "Meeting", "date": "2026-08-11T10:00:00", "summary": "Site visit.",
    })
    client.post("/api/client-activities/", json={
        "client_id": client_b, "activity_type": "Email", "date": "2026-08-11T11:00:00", "summary": "Sent quote.",
    })

    only_a = client.get("/api/client-activities/", params={"client_id": client_a})
    assert len(only_a.json()) == 1
    assert only_a.json()[0]["activity_type"] == "Meeting"


def test_client_activities_require_auth(client):
    resp = client.get("/api/client-activities/")
    assert resp.status_code == 401

# ===========================================================================
# From test_excel_formula_injection.py
# ===========================================================================
def test_malicious_client_name_is_escaped_in_export(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": '=cmd|"/c calc"!A1', "phone": "9000010078"})

    resp = client.get("/api/reports/clients.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    found = False
    for row in ws.iter_rows():
        for cell in row:
            if isinstance(cell.value, str) and "cmd|" in cell.value:
                found = True
                # Verified empirically: openpyxl preserves the leading
                # apostrophe on read-back (it's an Excel-UI-layer
                # convention, not something openpyxl simulates). The
                # actual security guarantee is data_type == 's' -
                # this cell is stored as a string, never as type 'f'
                # (formula), so Excel can never execute it.
                assert cell.data_type == "s"
    assert found, "expected the sanitized client name to appear in the export"


def test_legitimate_currency_value_unaffected(client, test_user):
    """The sanitizer must not corrupt genuinely safe values."""
    from app.shared.exporters import _sanitize_cell_value
    assert _sanitize_cell_value("Rs 1,25,000.00") == "Rs 1,25,000.00"
    assert _sanitize_cell_value(42) == 42
    assert _sanitize_cell_value(None) is None
    assert _sanitize_cell_value("Normal Client Name") == "Normal Client Name"


def test_all_four_dangerous_prefixes_are_escaped():
    from app.shared.exporters import _sanitize_cell_value
    for dangerous in ["=SUM(A1)", "+1+1", "-2+3", "@SUM(A1)"]:
        result = _sanitize_cell_value(dangerous)
        assert result.startswith("'")
        assert result == "'" + dangerous

# ===========================================================================
# From test_client_excel_financial_rbac.py
# ===========================================================================
def test_master_client_export_includes_financial_columns(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/reports/clients.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb["Clients"]
    header_row = [c.value for c in ws[5]]
    assert "Total Order Value" in header_row
    assert "Outstanding" in header_row


def test_employee_client_export_excludes_financial_columns(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Client Excel RBAC Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username="clientexcelrbacuser", email="clientexcelrbacuser@example.com", full_name="Client Excel RBAC User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientexcelrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/reports/clients.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb["Clients"]
    header_row = [c.value for c in ws[5]]
    assert "Total Order Value" not in header_row
    assert "Total Paid" not in header_row
    assert "Outstanding" not in header_row
    # Non-financial contact/status columns remain useful and present.
    assert "Client Name" in header_row
    assert "Phone" in header_row
    assert "Status" in header_row

# ===========================================================================
# From test_global_security.py
# ===========================================================================
def test_debug_true_in_production_is_rejected():
    from app.platform.configuration.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(SECRET_KEY="a" * 48, DATABASE_URL="sqlite:///test.db", ENVIRONMENT="production", DEBUG=True)


def test_debug_true_in_development_is_allowed():
    from app.platform.configuration.config import Settings
    s = Settings(SECRET_KEY="a" * 48, DATABASE_URL="sqlite:///test.db", ENVIRONMENT="development", DEBUG=True)
    assert s.DEBUG is True


def test_debug_false_in_production_is_allowed():
    # DEBUG=False alone doesn't make a production config valid - every
    # other production requirement (real Postgres URL, secure cookies,
    # explicit non-localhost CORS, shared rate-limit backend) must also
    # be satisfied, or this raises for one of those reasons instead of
    # exercising what this test is actually about.
    from app.platform.configuration.config import Settings
    s = Settings(
        SECRET_KEY="a" * 48,
        DATABASE_URL="postgresql://user:pass@prod-db.example.com:5432/woodful",
        ENVIRONMENT="production",
        DEBUG=False,
        COOKIE_SECURE=True,
        CORS_ORIGINS="https://app.example.com",
        RATE_LIMIT_BACKEND="redis",
    )
    assert s.DEBUG is False


def _prod_settings_kwargs(**overrides):
    base = dict(
        SECRET_KEY="a" * 48,
        DATABASE_URL="postgresql://user:pass@prod-db.example.com:5432/woodful",
        ENVIRONMENT="production",
        DEBUG=False,
        COOKIE_SECURE=True,
        CORS_ORIGINS="https://app.example.com",
        RATE_LIMIT_BACKEND="redis",
    )
    base.update(overrides)
    return base


def test_production_rejects_memory_rate_limit_backend():
    from app.platform.configuration.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(RATE_LIMIT_BACKEND="memory"))


def test_production_allows_redis_rate_limit_backend():
    from app.platform.configuration.config import Settings
    s = Settings(**_prod_settings_kwargs())
    assert s.RATE_LIMIT_BACKEND == "redis"


def test_production_rejects_localhost_cors_origin():
    from app.platform.configuration.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(CORS_ORIGINS="http://localhost:3000"))


def test_production_rejects_empty_cors_origins():
    from app.platform.configuration.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(CORS_ORIGINS=""))


def test_wildcard_cors_origin_rejected_in_any_environment():
    from app.platform.configuration.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(
            SECRET_KEY="a" * 48, DATABASE_URL="sqlite:///test.db",
            ENVIRONMENT="development", CORS_ORIGINS="*",
        )


def test_gemini_enabled_without_api_key_is_rejected():
    from app.platform.configuration.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(GEMINI_ENABLED=True, GEMINI_API_KEY=""))


def test_gemini_enabled_with_api_key_is_allowed():
    from app.platform.configuration.config import Settings
    s = Settings(**_prod_settings_kwargs(GEMINI_ENABLED=True, GEMINI_API_KEY="fake-key-for-test"))
    assert s.GEMINI_ENABLED is True


def test_drive_enabled_without_credentials_is_rejected():
    from app.platform.configuration.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(GOOGLE_DRIVE_ENABLED=True))


def test_storage_provider_drive_without_enabled_flag_is_rejected():
    from app.platform.configuration.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(STORAGE_PROVIDER="drive"))


def test_global_rate_limit_middleware_blocks_after_threshold(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200

    from app.platform.configuration.config import settings
    responses = [client.get("/api/materials/") for _ in range(settings.RATE_LIMIT_DEFAULT_PER_MINUTE + 5)]
    assert any(r.status_code == 429 for r in responses)


def test_health_endpoint_is_exempt_from_global_rate_limit(client):
    """The health check must never be rate-limited - infrastructure
    monitoring depends on it staying reachable."""
    responses = [client.get("/health") for _ in range(50)]
    assert all(r.status_code == 200 for r in responses)


def test_purchase_import_rejects_non_xlsx_extension(client, test_user):
    import io
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200
    files = {"file": ("data.csv", io.BytesIO(b"not,an,xlsx"), "text/csv")}
    resp = client.post("/api/purchase-imports/preview", files=files)
    assert resp.status_code == 400

# ===========================================================================
# From test_task_category_and_completion_timestamp.py
# ===========================================================================
def test_task_category_can_be_set_on_create(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Task Category Test Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"],
        "task_description": "Cut plywood panels", "task_category": "Cutting",
    }).json()
    assert task["task_category"] == "Cutting"


def test_actual_completed_at_is_set_on_transition_to_done(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Completion Timestamp Test Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"],
        "task_description": "Assemble wardrobe frame",
    }).json()
    assert task["actual_completed_at"] is None

    resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DONE"})
    assert resp.status_code == 200
    assert resp.json()["actual_completed_at"] is not None


def test_actual_completed_at_does_not_change_on_resave(client, test_user):
    """Re-saving an already-done task must not bump the completion
    timestamp - it should reflect when the task was FIRST completed."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Completion Timestamp Resave Employee"}).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-19T00:00:00", "employee_id": employee["id"],
        "task_description": "Install hinges",
    }).json()
    client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DONE"})
    first = client.get(f"/api/daily-tasks/{task['id']}").json()

    resp = client.put(f"/api/daily-tasks/{task['id']}", json={"status": "DONE", "remarks": "double-checked"})
    second = resp.json()
    assert second["actual_completed_at"] == first["actual_completed_at"]

# ===========================================================================
# From test_candidate_validation.py
# ===========================================================================
def test_valid_indian_mobile_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Valid Phone Candidate", "phone": "9876543210"})
    assert resp.status_code == 201
    assert resp.json()["phone"] == "9876543210"


def test_phone_not_starting_6to9_rejected(client, test_user):
    """The brief's exact recommended pattern (^[6-9][0-9]{9}$) - a
    10-digit number starting with 0-5 is not a valid Indian mobile
    number, even though it's the right length."""
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Bad Prefix Candidate", "phone": "5123456789"})
    assert resp.status_code == 422


def test_phone_wrong_length_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Short Phone Candidate", "phone": "98765"})
    assert resp.status_code == 422


def test_invalid_email_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Bad Email Candidate", "email": "not-an-email"})
    assert resp.status_code == 422


def test_experience_outside_controlled_options_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Bad Experience Candidate", "experience": "a decade or so"})
    assert resp.status_code == 422


def test_experience_valid_option_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Good Experience Candidate", "experience": "2-5 years"})
    assert resp.status_code == 201
    assert resp.json()["experience"] == "2-5 years"


def test_candidate_still_gets_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/candidates/", json={"name": "Business ID Check Candidate"})
    assert resp.status_code == 201
    assert len(resp.json()["business_id"]) == 10

# ===========================================================================
# From test_migration_health_and_cache_headers.py
# ===========================================================================
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


def test_health_check_reports_degraded_when_database_unreachable(client, monkeypatch):
    """/health must not claim readiness from the one-time startup flag
    alone - it should re-check the database live and report degraded if
    that live check fails, even though startup migrations succeeded."""
    import app.main as main_module

    class _BrokenConn:
        def __enter__(self):
            raise Exception("simulated database connection failure")

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(main_module.engine, "connect", lambda: _BrokenConn())
    resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["status"] == "degraded"
    # No internal detail (connection strings, driver errors) leaked to the caller.
    assert "simulated database connection failure" not in resp.text


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

# ===========================================================================
# Pluggable rate-limiter backend (from test_auth_and_chatbot_misc.py)
# ===========================================================================
# ===========================================================================
# From test_rate_limiter_abstraction.py
# ===========================================================================
def test_in_memory_backend_allows_up_to_the_limit():
    from app.platform.security.rate_limit import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(5):
        assert backend.is_allowed("test-key", max_requests=5, window_seconds=60) is True


def test_in_memory_backend_blocks_beyond_the_limit():
    from app.platform.security.rate_limit import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(5):
        backend.is_allowed("test-key", max_requests=5, window_seconds=60)
    assert backend.is_allowed("test-key", max_requests=5, window_seconds=60) is False


def test_in_memory_backend_keys_are_independent():
    from app.platform.security.rate_limit import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(5):
        backend.is_allowed("key-a", max_requests=5, window_seconds=60)
    # A different key must have its own independent budget.
    assert backend.is_allowed("key-b", max_requests=5, window_seconds=60) is True


def test_in_memory_backend_window_expires():
    from app.platform.security.rate_limit import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(3):
        backend.is_allowed("test-key", max_requests=3, window_seconds=1)
    assert backend.is_allowed("test-key", max_requests=3, window_seconds=1) is False
    time.sleep(1.1)
    assert backend.is_allowed("test-key", max_requests=3, window_seconds=1) is True


def test_redis_is_not_imported_at_module_level():
    """The core requirement - a plain local dev environment must never
    need the redis package installed just to import this file."""
    import ast
    import app.platform.security.rate_limit as module
    with open(module.__file__) as f:
        tree = ast.parse(f.read())
    module_level_names = [n.names[0].name for n in tree.body if isinstance(n, ast.Import)]
    assert "redis" not in module_level_names


def test_public_rate_limit_function_signature_unchanged(client, test_user):
    """Every existing caller (login, chat, password reset) uses
    rate_limit(bucket, max_requests, window_seconds) - confirms the
    endpoints that depend on it still respond normally rather than
    erroring on a broken dependency."""
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_chat_endpoint_is_rate_limited(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200

    from app.platform.configuration.config import settings
    responses = [client.post("/api/chat/", json={"message": "hello"}) for _ in range(settings.RATE_LIMIT_CHAT_PER_MINUTE + 3)]
    assert any(r.status_code == 429 for r in responses)

# ===========================================================================
# Core authentication - login/session (from test_auth_and_chatbot_misc.py)
# ===========================================================================
# ===========================================================================
def test_login_success_sets_cookie_and_omits_token_from_body(client, test_user):
    response = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert response.status_code == 200
    body = response.json()
    assert "token" not in body
    assert body["user"]["email"] == "test@example.com"
    assert "access_token" in response.cookies


def test_login_invalid_credentials(client, test_user):
    response = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_login_wrong_password_message(client, test_user):
    """Message must be generic - not "Incorrect password", which would
    confirm to an attacker that the account exists (account
    enumeration)."""
    response = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_login_by_username_works(client, test_user):
    response = client.post("/api/auth/login", json={"identifier": "testuser", "password": "TestPass123!"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "test@example.com"


def test_login_by_email_still_works(client, test_user):
    response = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert response.status_code == 200


def test_login_unknown_email_message(client, test_user):
    """Message must be generic - not "No account found", which would
    confirm to an attacker that the identifier does NOT exist
    (account enumeration)."""
    response = client.post("/api/auth/login", json={"identifier": "nobody@example.com", "password": "whatever"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_login_does_not_leak_account_existence(client, test_user):
    """The actual security property: a wrong password for a real
    account and a login attempt against a non-existent account must
    be genuinely indistinguishable to the caller - same status code,
    same message, not just similar wording."""
    wrong_password = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "wrong"})
    unknown_account = client.post("/api/auth/login", json={"identifier": "nobody@example.com", "password": "wrong"})
    assert wrong_password.status_code == unknown_account.status_code
    assert wrong_password.json()["detail"] == unknown_account.json()["detail"]


def test_mobile_login_returns_token(client, test_user):
    response = client.post("/api/auth/login/mobile", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert response.status_code == 200
    assert response.json()["token"]


def test_protected_route_without_cookie_is_rejected(client):
    response = client.get("/api/materials/")
    assert response.status_code == 401


def test_login_then_access_me(client, test_user):
    login = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert login.status_code == 200
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "test@example.com"

# ===========================================================================
# Financial-mutation audit logging (from test_auth_and_chatbot_misc.py)
# ===========================================================================
# ===========================================================================
def test_update_payment_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Audit Client", "phone": "9000010126"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "40000", "advance": "0",
    }).json()
    payment = client.post("/api/payments/", json={
        "order_id": order["id"], "date": "2026-08-21T00:00:00", "amount": "5000",
        "payment_type": "Advance", "payment_mode": "Cash",
    }).json()

    resp = client.put(f"/api/payments/{payment['id']}", json={"amount": "6000"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "update_payment" and l["record_id"] == payment["id"]), None)
    assert match is not None
    assert match["old_value"]["amount"] == 5000.0
    assert match["new_value"]["amount"] == 6000.0


def test_create_order_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Audit Client", "phone": "9000010127"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "25000", "advance": "0",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "create_order" and l["record_id"] == order["id"]), None)
    assert match is not None
    assert match["new_value"]["order_value"] == 25000.0


def test_update_order_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Update Audit Client", "phone": "9000010128"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "25000", "advance": "0",
    }).json()

    resp = client.put(f"/api/orders/{order['id']}", json={"project_type": "Kitchen"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "update_order" and l["record_id"] == order["id"]), None)
    assert match is not None
    assert match["new_value"]["project_type"] == "Kitchen"


def test_create_and_update_project_expense_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Expense Audit Client", "phone": "9000010129"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-21T00:00:00", "order_value": "30000", "advance": "0",
    }).json()
    expense = client.post("/api/project-expenses/", json={
        "order_id": order["id"], "date": "2026-08-21T00:00:00", "category": "Material", "amount": "5000",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    create_match = next((l for l in logs if l["action"] == "create_project_expense" and l["record_id"] == expense["id"]), None)
    assert create_match is not None
    assert create_match["new_value"]["category"] == "Material"

    resp = client.put(f"/api/project-expenses/{expense['id']}", json={"amount": "5500"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    update_match = next((l for l in logs if l["action"] == "update_project_expense" and l["record_id"] == expense["id"]), None)
    assert update_match is not None
    assert update_match["old_value"]["amount"] == 5000.0
    assert update_match["new_value"]["amount"] == 5500.0

# ===========================================================================
# Estimate/purchase audit logging (from test_client_hr_and_export_features.py)
# ===========================================================================
def test_create_estimate_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Audit Client", "phone": "9000010056"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "create_estimate" and l["record_id"] == estimate["id"]), None)
    assert match is not None
    assert match["new_value"]["client_id"] == client_id


def test_update_estimate_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Update Audit Client", "phone": "9000010057"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    resp = client.put(f"/api/estimates/{estimate['id']}", json={"material_cost": "12000"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "update_estimate" and l["record_id"] == estimate["id"]), None)
    assert match is not None
    assert match["old_value"]["material_cost"] == 10000.0
    assert match["new_value"]["material_cost"] == 12000.0


def test_revise_estimate_is_audit_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Revise Audit Client", "phone": "9000010058"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    revision = client.post(f"/api/estimates/{estimate['id']}/revise").json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "revise_estimate" and l["record_id"] == revision["id"]), None)
    assert match is not None
    assert match["old_value"]["source_estimate_id"] == estimate["id"]


def test_create_purchase_is_audit_logged(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Purchase Audit Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Purchase Audit Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()

    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-22T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "create_purchase" and l["record_id"] == purchase["id"]), None)
    assert match is not None
    assert match["new_value"]["material_id"] == material["id"]


def test_receive_purchase_is_audit_logged(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Purchase Receive Audit Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Purchase Receive Audit Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-22T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18",
        "payment_status": "Paid", "receipt_status": "Ordered",
    }).json()

    client.post(f"/api/purchases/{purchase['id']}/receive")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "receive_purchase" and l["record_id"] == purchase["id"]), None)
    assert match is not None
    assert match["new_value"]["receipt_status"] == "Received"

# ===========================================================================
# Salary slip audit logging (from test_admin_and_ai_gateway.py, itself from
# test_salary_slip_audit_logging.py)
# ===========================================================================
def test_create_salary_slip_is_audit_logged(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Salary Audit Test Employee"}).json()

    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "9500", "da": "0", "hra": "6000", "overtime_amount": "0",
        "pf_deduction": "1140", "tds_deduction": "0", "other_deductions": "300",
    }).json()

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "create_salary_slip" and l["record_id"] == slip["id"]), None)
    assert match is not None
    assert match["new_value"]["employee_id"] == employee["id"]


def test_update_salary_slip_is_audit_logged_with_old_and_new_values(client, test_user):
    """The real regression guard - this must not raise a
    JSON-serialization error on commit, since basic/da/hra etc. are
    Decimal-typed Numeric columns, not plain floats."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Salary Audit Update Employee"}).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "August", "year": "2026",
        "working_days": "26", "paid_days": "26",
        "basic": "9500", "da": "0", "hra": "6000", "overtime_amount": "0",
        "pf_deduction": "1140", "tds_deduction": "0", "other_deductions": "300",
    }).json()

    resp = client.put(f"/api/salary-slips/{slip['id']}", json={"basic": "10000"})
    assert resp.status_code == 200

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "update_salary_slip" and l["record_id"] == slip["id"]), None)
    assert match is not None
    assert match["old_value"]["basic"] == 9500.0
    assert match["new_value"]["basic"] == 10000.0

# ===========================================================================


# ===========================================================================
# Delete audit logging - material/supplier/client/employee (from
# test_admin_and_ai_gateway.py, itself from test_delete_audit_logging.py)
# ===========================================================================
def test_material_deletion_is_audit_logged(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Audit Log Test Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()

    client.delete(f"/api/materials/{material['id']}")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "delete_material" and l["record_id"] == material["id"]), None)
    assert match is not None
    assert match["module_name"] == "materials"
    assert match["old_value"]["name"] == "Audit Log Test Material"


def test_supplier_deletion_is_audit_logged(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Audit Log Test Supplier"}).json()

    client.delete(f"/api/suppliers/{supplier['id']}")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "delete_supplier" and l["record_id"] == supplier["id"]), None)
    assert match is not None


def test_client_deletion_is_audit_logged(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Audit Log Test Client", "phone": "9000010055"}).json()

    client.delete(f"/api/clients/{created['id']}")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "delete_client" and l["record_id"] == created["id"]), None)
    assert match is not None


def test_employee_deletion_is_audit_logged(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Audit Log Test Employee"}).json()

    client.delete(f"/api/employees/{employee['id']}")

    logs = client.get("/api/audit-logs/").json()
    match = next((l for l in logs if l["action"] == "delete_employee" and l["record_id"] == employee["id"]), None)
    assert match is not None

# ===========================================================================


# ===========================================================================
# Master-only delete enforcement across entity types (from
# test_admin_and_ai_gateway.py, itself from test_global_delete_master_only.py)
# ===========================================================================
def _login_as_user(client, username, email):
    """The application has only two roles - master and user. This
    creates a non-master account to confirm delete endpoints reject
    it, not an obsolete third role."""
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("UserPass1!"), role="user", is_active=True,
    )
    return user


def test_employee_delete_rejects_non_master(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Global Delete Guard Employee", "monthly_salary": "20000"}).json()
    non_master = _login_as_user(client, "globaldeleteguarduser1", "globaldeleteguarduser1@example.com")
    db_session.add(non_master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "globaldeleteguarduser1@example.com", "password": "UserPass1!"})

    resp = client.delete(f"/api/employees/{employee['id']}")
    assert resp.status_code == 403


def test_lookup_value_delete_rejects_non_master(client, test_user, db_session):
    _login(client, test_user)
    value = client.post("/api/settings/units", json={"name": "Global Delete Guard Unit"}).json()
    non_master = _login_as_user(client, "globaldeleteguarduser2", "globaldeleteguarduser2@example.com")
    db_session.add(non_master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "globaldeleteguarduser2@example.com", "password": "UserPass1!"})

    resp = client.delete(f"/api/settings/units/{value['id']}")
    assert resp.status_code == 403


def test_supplier_material_delete_rejects_non_master(client, test_user, db_session):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Global Delete Guard Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Global Delete Guard Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "1",
    }).json()
    link = client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "100.00",
    }).json()
    non_master = _login_as_user(client, "globaldeleteguarduser3", "globaldeleteguarduser3@example.com")
    db_session.add(non_master)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "globaldeleteguarduser3@example.com", "password": "UserPass1!"})

    resp = client.delete(f"/api/supplier-materials/{link['id']}")
    assert resp.status_code == 403


def test_master_can_still_delete_employee(client, test_user):
    """Backward compatibility - master retains full delete access."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Global Delete Guard Master Employee", "monthly_salary": "20000"}).json()
    resp = client.delete(f"/api/employees/{employee['id']}")
    assert resp.status_code == 204


def test_settings_env_file_resolves_inside_backend_directory():
    """Regression test for a real bug: _PROJECT_ROOT was off by one
    directory level (backend/app/ instead of backend/), so a genuinely
    correct, fully-populated backend/.env was silently never found or
    read at all - Settings would fail with "SECRET_KEY Field required"
    even when SECRET_KEY was actually set, because the file containing
    it was never located. Asserts the resolved default env file path
    is a direct child of the real backend/ directory (parent of app/),
    not of app/ itself."""
    from pathlib import Path
    from app.platform.configuration import config as config_module
    backend_dir = Path(config_module.__file__).resolve().parent.parent.parent
    assert config_module._DEFAULT_ENV_FILE.parent == backend_dir
    assert config_module._DEFAULT_ENV_FILE.name == ".env"


def test_alembic_config_resolves_to_real_backend_files():
    """Regression test for the same class of bug in
    auto_migrate.py's _alembic_config - it was resolving to
    backend/app/ instead of backend/, meaning run_startup_migrations
    (called on every backend startup, with main.py explicitly refusing
    to start the server if it fails) could never find the real
    alembic.ini or alembic/ folder. Asserts the config genuinely
    points at files that exist on disk, not merely a plausible-looking
    path."""
    from pathlib import Path
    from app.platform.database.auto_migrate import _alembic_config
    cfg = _alembic_config()
    ini_path = Path(cfg.config_file_name)
    script_location = Path(cfg.get_main_option("script_location"))
    assert ini_path.exists(), f"{ini_path} does not exist - alembic.ini path resolution is broken"
    assert script_location.exists(), f"{script_location} does not exist - alembic script_location resolution is broken"
    assert (script_location / "env.py").exists()
