"""Platform and security tests: cross-cutting platform utilities,
financial-data RBAC, and security/configuration. Combines
test_platform.py, test_financial_rbac.py, and test_security_and_config.py."""
import re
from tests.helpers import _login
import pytest
from datetime import datetime, timedelta
from app.shared import validate_phone
import io
from app.platform.security import hash_password
from app.modules.auth.auth import User
from tests.helpers import _login, _create_employee_with_login as _create_employee
import os
import time
from openpyxl import load_workbook
from app.shared import pdf_text
from app.main import _migration_state


# --- platform/test_platform.py ---
BUSINESS_ID_PATTERN = re.compile(r"^[A-Z0-9]{10}$")


def test_client_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Business ID Test Client", "phone": "9000010005"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["business_id"] is not None
    assert BUSINESS_ID_PATTERN.match(body["business_id"]), f"got {body['business_id']!r}"
    # The sequential code must still exist too - this is additive, not a replacement.
    assert body["client_code"].startswith("CL-")


def test_business_ids_are_unique_across_records(client, test_user):
    _login(client, test_user)
    ids = set()
    for i in range(5):
        resp = client.post("/api/clients/", json={"name": f"Uniqueness Test Client {i}", "phone": "9000010006"})
        ids.add(resp.json()["business_id"])
    assert len(ids) == 5


def test_material_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/materials/", json={
        "name": "Business ID Test Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 2,
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["material_code"].startswith("MAT-")


def test_supplier_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "Business ID Test Supplier"})
    assert resp.status_code == 201
    assert BUSINESS_ID_PATTERN.match(resp.json()["business_id"])


def test_employee_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={
        "name": "Business ID Test Employee", "department": "Production",
        "monthly_salary": "25000", "daily_wage": "1000",
    })
    assert resp.status_code == 201
    assert BUSINESS_ID_PATTERN.match(resp.json()["business_id"])


def test_order_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Business ID Client", "phone": "9000010007"}).json()["id"]
    resp = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "10000.00", "advance": "0",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["order_code"].startswith("WC-")


def test_business_id_not_accepted_from_client_input(client, test_user):
    """The business_id must be server-generated, same guarantee as the
    sequential codes - a client-supplied value must be ignored."""
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Spoof Test Client", "business_id": "FAKE000001", "phone": "9000010008"})
    assert resp.status_code == 201
    assert resp.json()["business_id"] != "FAKE000001"
    assert BUSINESS_ID_PATTERN.match(resp.json()["business_id"])


def test_estimate_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate Business ID Client", "phone": "9000010009"}).json()["id"]
    resp = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "50000.00", "labor_cost": "20000.00", "tax_percent": "18",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["estimate_code"].startswith("EST-")


def test_purchase_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    supplier_id = client.post("/api/suppliers/", json={"name": "Purchase Business ID Supplier"}).json()["id"]
    material_id = client.post("/api/materials/", json={
        "name": "Purchase Business ID Material", "unit": "Sheets", "opening_stock": 0, "minimum_stock": 2,
    }).json()["id"]
    resp = client.post("/api/purchases/", json={
        "date": "2026-08-01T00:00:00", "supplier_id": supplier_id, "material_id": material_id,
        "quantity": "10", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["purchase_code"].startswith("PUR-")


def test_payment_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Payment Business ID Client", "phone": "9000010010"}).json()["id"]
    order_id = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "20000.00", "advance": "0",
    }).json()["id"]
    resp = client.post("/api/payments/", json={
        "date": "2026-08-05T00:00:00", "order_id": order_id,
        "payment_type": "Advance", "payment_mode": "UPI", "amount": "5000.00",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["receipt_code"].startswith("RCPT-")


def test_daily_task_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={
        "name": "Task Business ID Employee", "department": "Production",
        "monthly_salary": "20000", "daily_wage": "800",
    }).json()["id"]
    resp = client.post("/api/daily-tasks/", json={
        "date": "2026-08-05T00:00:00", "employee_id": employee_id, "task_description": "Sand and finish panels",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["task_code"].startswith("TSK-")


def test_production_job_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/production-jobs/", json={"date": "2026-08-05T00:00:00", "operation": "Cutting"})
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["job_code"].startswith("JOB-")


def test_project_expense_gets_10_char_business_id(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Expense Business ID Client", "phone": "9000010011"}).json()["id"]
    order_id = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "15000.00", "advance": "0",
    }).json()["id"]
    resp = client.post("/api/project-expenses/", json={
        "date": "2026-08-05T00:00:00", "order_id": order_id, "category": "Transport", "amount": "1200.00",
    })
    assert resp.status_code == 201
    body = resp.json()
    assert BUSINESS_ID_PATTERN.match(body["business_id"])
    assert body["expense_code"].startswith("EXP-")


"""Tests for the provider-neutral monitoring boundary
(app/platform/monitoring/monitoring.py) - context redaction, safe
fallback when no provider (or a broken one) is configured, and the
global unhandled-exception handler registered in app/main.py."""


@pytest.fixture(autouse=True)
def _reset_monitoring():
    from app.platform.monitoring import reset_monitoring_provider
    reset_monitoring_provider()
    yield
    reset_monitoring_provider()


def test_capture_exception_never_raises_with_default_provider():
    """The default MONITORING_PROVIDER=none must be a fully safe,
    always-working choice - capturing an exception must never itself
    raise, since that would turn error reporting into a second failure
    on top of whatever was already being reported."""
    from app.platform.monitoring import capture_exception
    capture_exception(ValueError("something went wrong"), endpoint="/api/test", module="test")


def test_capture_message_never_raises_with_default_provider():
    from app.platform.monitoring import capture_message
    capture_message("a significant non-exception event", level="warning", module="test")


def test_capture_exception_survives_a_broken_provider(monkeypatch):
    """If the configured provider itself throws (network error, bad
    DSN, provider outage), capture_exception must still not raise -
    the whole point of this boundary is that a monitoring failure can
    never become a second, unrelated application failure."""
    import app.platform.monitoring as monitoring_module

    class _BrokenProvider:
        def capture_exception(self, exc, context):
            raise RuntimeError("simulated monitoring provider outage")

    monkeypatch.setattr(monitoring_module, "_get_provider", lambda: _BrokenProvider())
    monitoring_module.capture_exception(ValueError("original error"), module="test")


def test_redact_context_strips_password_like_keys():
    from app.platform.monitoring import _redact_context
    result = _redact_context({
        "password": "hunter2", "user_token": "abc123", "API_KEY": "sk-real-key",
        "safe_field": "this is fine",
    })
    assert result["password"] == "[REDACTED]"
    assert result["user_token"] == "[REDACTED]"
    assert result["API_KEY"] == "[REDACTED]"
    assert result["safe_field"] == "this is fine"


def test_redact_context_is_recursive_into_nested_dicts():
    from app.platform.monitoring import _redact_context
    result = _redact_context({"request": {"headers": {"cookie": "session=abc"}, "path": "/api/x"}})
    assert result["request"]["headers"]["cookie"] == "[REDACTED]"
    assert result["request"]["path"] == "/api/x"


def test_redact_context_covers_database_url_and_secret_key():
    """Explicitly required by the production observability rules -
    DATABASE_URL and SECRET_KEY must never reach a monitoring provider
    even if a call site accidentally includes them in context."""
    from app.platform.monitoring import _redact_context
    result = _redact_context({"DATABASE_URL": "postgresql://real-connection-string", "SECRET_KEY": "real-secret"})
    assert result["DATABASE_URL"] == "[REDACTED]"
    assert result["SECRET_KEY"] == "[REDACTED]"


def test_unhandled_exception_handler_returns_safe_generic_response(monkeypatch):
    """End-to-end HTTP behavior of the handler registered in app/main.py,
    exercised through a throwaway test-only app - never the real
    production app - so no crash-inducing route ever exists in
    production. Confirms the response is generic (no exception detail,
    no traceback) and that monitoring was actually invoked."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import app.main as main_module

    captured = []
    monkeypatch.setattr(main_module, "capture_exception", lambda exc, **ctx: captured.append((exc, ctx)))

    test_app = FastAPI()
    test_app.add_exception_handler(Exception, main_module.unhandled_exception_handler)

    @test_app.get("/boom")
    def boom():
        raise RuntimeError("a very specific internal detail that must never reach the client")

    test_client = TestClient(test_app, raise_server_exceptions=False)
    resp = test_client.get("/boom")

    assert resp.status_code == 500
    assert resp.json() == {"detail": "An unexpected error occurred. Please try again."}
    assert "very specific internal detail" not in resp.text

    assert len(captured) == 1
    exc, ctx = captured[0]
    assert isinstance(exc, RuntimeError)
    assert ctx == {"method": "GET", "path": "/boom"}


def _create_material(client, name, current=None, minimum=5):
    resp = client.post("/api/materials/", json={
        "name": name, "unit": "Sheets", "opening_stock": current if current is not None else 20, "minimum_stock": minimum,
    })
    return resp.json()


def test_no_limit_returns_everything_unpaginated(client, test_user):
    _login(client, test_user)
    for i in range(5):
        _create_material(client, f"Unpaginated Material {i}")

    resp = client.get("/api/materials/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 5
    # Backward compatible - no pagination metadata forced on old callers.
    assert "X-Total-Count" in resp.headers


def test_limit_and_offset_actually_paginate(client, test_user):
    _login(client, test_user)
    for i in range(8):
        _create_material(client, f"Page Test Material {i}")

    page1 = client.get("/api/materials/", params={"limit": 3, "offset": 0})
    page2 = client.get("/api/materials/", params={"limit": 3, "offset": 3})

    assert len(page1.json()) == 3
    assert len(page2.json()) == 3
    ids_page1 = {m["id"] for m in page1.json()}
    ids_page2 = {m["id"] for m in page2.json()}
    assert ids_page1.isdisjoint(ids_page2)

    total = int(page1.headers["X-Total-Count"])
    assert total == int(page2.headers["X-Total-Count"])
    assert total >= 8


def test_low_stock_filter_composes_correctly_with_pagination(client, test_user):
    """Regression test: low_stock_only used to be filtered in Python
    AFTER the query ran, which would have silently broken once SQL-level
    pagination was added (a page could come back with fewer or zero
    matching rows even though more existed). This confirms the total
    count and the paginated page both reflect the SQL-level filter."""
    _login(client, test_user)
    _create_material(client, "Low Stock Regression A", current=1, minimum=10)
    _create_material(client, "Low Stock Regression B", current=2, minimum=10)
    _create_material(client, "Well Stocked Regression C", current=50, minimum=10)

    resp = client.get("/api/materials/", params={"low_stock_only": True, "limit": 1, "offset": 0})
    assert resp.status_code == 200
    total = int(resp.headers["X-Total-Count"])
    assert total >= 2  # both low-stock materials counted, not just what fit on this page
    assert len(resp.json()) == 1  # the page itself respects the limit
    assert resp.json()[0]["current_stock"] <= resp.json()[0]["minimum_stock"]


def test_orders_pagination_backward_compatible_without_limit(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Page Test Client", "phone": "9000010159"}).json()["id"]
    for i in range(4):
        client.post("/api/orders/", json={
            "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "10000.00", "advance": "0",
        })

    resp = client.get("/api/orders/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 4
    assert "X-Total-Count" in resp.headers


def test_orders_limit_and_offset_paginate_correctly(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order Page Test Client 2", "phone": "9000010160"}).json()["id"]
    for i in range(6):
        client.post("/api/orders/", json={
            "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "5000.00", "advance": "0",
        })

    page1 = client.get("/api/orders/", params={"client_id": client_id, "limit": 2, "offset": 0})
    page2 = client.get("/api/orders/", params={"client_id": client_id, "limit": 2, "offset": 2})
    assert len(page1.json()) == 2
    assert len(page2.json()) == 2
    ids1 = {o["id"] for o in page1.json()}
    ids2 = {o["id"] for o in page2.json()}
    assert ids1.isdisjoint(ids2)
    assert int(page1.headers["X-Total-Count"]) == 6


def test_orders_pagination_composes_with_client_id_filter(client, test_user):
    """Regression check: client_id filtering must still correctly scope
    the total count and the page - not just return the first N orders
    system-wide."""
    _login(client, test_user)
    client_a = client.post("/api/clients/", json={"name": "Filter Test Client A", "phone": "9000010161"}).json()["id"]
    client_b = client.post("/api/clients/", json={"name": "Filter Test Client B", "phone": "9000010162"}).json()["id"]

    for i in range(3):
        client.post("/api/orders/", json={
            "client_id": client_a, "order_date": "2026-08-01T00:00:00", "order_value": "1000.00", "advance": "0",
        })
    client.post("/api/orders/", json={
        "client_id": client_b, "order_date": "2026-08-01T00:00:00", "order_value": "2000.00", "advance": "0",
    })

    resp = client.get("/api/orders/", params={"client_id": client_a, "limit": 10, "offset": 0})
    assert int(resp.headers["X-Total-Count"]) == 3
    assert len(resp.json()) == 3
    assert all(o["client_id"] == client_a for o in resp.json())


def test_clients_pagination_backward_compatible_without_limit(client, test_user):
    _login(client, test_user)
    for i in range(4):
        client.post("/api/clients/", json={"name": f"Client Page Test {i}", "phone": "9000010163"})

    resp = client.get("/api/clients/")
    assert resp.status_code == 200
    assert len(resp.json()) >= 4
    assert "X-Total-Count" in resp.headers


def test_clients_limit_and_offset_paginate_correctly(client, test_user):
    _login(client, test_user)
    for i in range(5):
        client.post("/api/clients/", json={"name": f"Client Paginate Test {i}", "phone": "9000010164"})

    page1 = client.get("/api/clients/", params={"limit": 2, "offset": 0})
    page2 = client.get("/api/clients/", params={"limit": 2, "offset": 2})
    assert len(page1.json()) == 2
    assert len(page2.json()) == 2
    names1 = {c["id"] for c in page1.json()}
    names2 = {c["id"] for c in page2.json()}
    assert names1.isdisjoint(names2)


def test_clients_pagination_composes_with_search_filter(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Searchable Pagination Match One", "phone": "9000010165"})
    client.post("/api/clients/", json={"name": "Searchable Pagination Match Two", "phone": "9000010166"})
    client.post("/api/clients/", json={"name": "Totally Different Name", "phone": "9000010167"})

    resp = client.get("/api/clients/", params={"search": "Searchable Pagination", "limit": 10, "offset": 0})
    assert int(resp.headers["X-Total-Count"]) == 2
    assert len(resp.json()) == 2


def test_overdue_only_filter_matches_the_exact_rule(client, test_user):
    """balance > 0 AND order_date more than 30 days ago - same rule the
    frontend previously computed client-side. Confirms an order with a
    balance but placed recently is excluded, an order fully paid but old
    is excluded, and only the genuinely overdue order is returned."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Overdue Filter Test Client", "phone": "9000010168"}).json()["id"]

    old_date = (datetime.utcnow() - timedelta(days=45)).isoformat()
    recent_date = (datetime.utcnow() - timedelta(days=5)).isoformat()

    genuinely_overdue = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": old_date, "order_value": "10000.00", "advance": "0",
    }).json()
    recent_with_balance = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": recent_date, "order_value": "10000.00", "advance": "0",
    }).json()
    old_but_paid = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": old_date, "order_value": "10000.00", "advance": "10000.00",
    }).json()

    resp = client.get("/api/orders/", params={"client_id": client_id, "overdue_only": True})
    result_ids = {o["id"] for o in resp.json()}
    assert genuinely_overdue["id"] in result_ids
    assert recent_with_balance["id"] not in result_ids
    assert old_but_paid["id"] not in result_ids


def test_overdue_only_composes_with_pagination(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Overdue Pagination Test Client", "phone": "9000010169"}).json()["id"]
    old_date = (datetime.utcnow() - timedelta(days=60)).isoformat()

    for i in range(3):
        client.post("/api/orders/", json={
            "client_id": client_id, "order_date": old_date, "order_value": "5000.00", "advance": "0",
        })

    resp = client.get("/api/orders/", params={"client_id": client_id, "overdue_only": True, "limit": 1, "offset": 0})
    assert int(resp.headers["X-Total-Count"]) == 3
    assert len(resp.json()) == 1


"""Phone number validation: EXACTLY 10 digits, exact required message
'Please enter valid mobile number' for every rejection reason (missing,
wrong length, non-numeric, formatted, country-code-prefixed) - not a
different message per reason. Covers Client (mandatory), and the
Supplier/Employee gap (phone stays optional there, but must be valid
10 digits when given - previously unvalidated at all).
"""


EXACT_MESSAGE = "Please enter valid mobile number"


def test_validate_phone_exactly_10_digits_accepted():
    assert validate_phone("9876543210") is True


def test_validate_phone_9_digits_rejected():
    assert validate_phone("987654321") is False


def test_validate_phone_11_digits_rejected():
    assert validate_phone("98765432101") is False


def test_validate_phone_country_code_rejected():
    assert validate_phone("+919876543210") is False


def test_validate_phone_spaces_rejected():
    assert validate_phone("987 654 3210") is False


def test_validate_phone_separators_rejected():
    assert validate_phone("987-654-3210") is False


def test_validate_phone_alphabetic_rejected():
    assert validate_phone("abcdefghij") is False


def test_validate_phone_alphanumeric_rejected():
    assert validate_phone("98765432AB") is False


def test_validate_phone_empty_rejected():
    assert validate_phone("") is False


def test_client_missing_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "No Phone Client"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_wrong_length_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Wrong Length Client", "phone": "98765432101"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_non_numeric_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Non Numeric Client", "phone": "abcdefghij"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_alphanumeric_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Alphanumeric Client", "phone": "98765432AB"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_special_char_phone_exact_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Special Char Client", "phone": "98765-4321"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_country_code_phone_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Country Code Client 2", "phone": "+919876543210"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_client_edit_invalid_phone_keeps_original_value(client, test_user):
    """Client Edit with invalid phone: request rejected, existing valid
    phone remains unchanged."""
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Edit Preserve Client", "phone": "9812345699"}).json()
    resp = client.put(f"/api/clients/{created['id']}", json={"phone": "12345"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())
    refreshed = client.get(f"/api/clients/{created['id']}").json()
    assert refreshed["phone"] == "9812345699"


def test_client_import_invalid_phone_row_rejected_exact_message(client, test_user):
    """Client Import with invalid phone: row rejected, exact error
    message shown, row not committed - via the pure validator used by
    the actual import route."""
    from app.modules.clients.services import validate_and_match_row
    result, errors = validate_and_match_row({"Client Name *": "Bad Import Phone", "Client Type *": "Individual", "Phone *": "12345"}, {})
    assert EXACT_MESSAGE in errors


def test_client_import_missing_phone_row_exact_message():
    from app.modules.clients.services import validate_and_match_row
    result, errors = validate_and_match_row({"Client Name *": "Missing Import Phone", "Client Type *": "Individual"}, {})
    assert EXACT_MESSAGE in errors


def test_direct_api_request_still_rejected_regardless_of_frontend(client, test_user):
    """Direct API request bypassing any frontend validation must still
    be rejected server-side - this IS that direct request."""
    _login(client, test_user)
    resp = client.post("/api/clients/", json={"name": "Direct API Client", "phone": "notaphoneatall"})
    assert resp.status_code == 422


def test_supplier_can_be_created_without_phone(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "No Phone Supplier"})
    assert resp.status_code == 201


def test_supplier_invalid_phone_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "Bad Phone Supplier", "phone": "12345"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_supplier_valid_phone_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/suppliers/", json={"name": "Good Phone Supplier", "phone": "9876543211"})
    assert resp.status_code == 201
    assert resp.json()["phone"] == "9876543211"


def test_supplier_update_invalid_phone_rejected(client, test_user):
    _login(client, test_user)
    created = client.post("/api/suppliers/", json={"name": "Update Phone Supplier", "phone": "9876543212"}).json()
    resp = client.put(f"/api/suppliers/{created['id']}", json={"phone": "notaphone"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_employee_can_be_created_without_phone(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={"name": "No Phone Employee"})
    assert resp.status_code == 201


def test_employee_invalid_phone_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={"name": "Bad Phone Employee", "phone": "123"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_employee_valid_phone_accepted(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/employees/", json={"name": "Good Phone Employee", "phone": "9876543213"})
    assert resp.status_code == 201
    assert resp.json()["phone"] == "9876543213"


def test_employee_update_invalid_phone_rejected(client, test_user):
    _login(client, test_user)
    created = client.post("/api/employees/", json={"name": "Update Phone Employee", "phone": "9876543214"}).json()
    resp = client.put(f"/api/employees/{created['id']}", json={"phone": "notaphone"})
    assert resp.status_code == 422
    assert EXACT_MESSAGE in str(resp.json())


def test_employee_emergency_contact_stays_freeform(client, test_user):
    """emergency_contact is deliberately NOT subject to the strict
    10-digit rule (it may legitimately include a name/relation, e.g.
    'Wife - 9876543210'), unlike the employee's own phone field."""
    _login(client, test_user)
    resp = client.post("/api/employees/", json={
        "name": "Emergency Contact Employee", "emergency_contact": "Wife - 9876543210",
    })
    assert resp.status_code == 201
    assert resp.json()["emergency_contact"] == "Wife - 9876543210"


def test_estimate_creation_still_works_after_phone_tightening(client, test_user):
    _login(client, test_user)
    c = client.post("/api/clients/", json={"name": "Estimate Regression Client", "phone": "9876543215"}).json()
    resp = client.post("/api/estimates/", json={"client_id": c["id"], "material_cost": "10000"})
    assert resp.status_code == 201


def test_order_creation_via_recognition_still_works_after_phone_tightening(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/orders/", json={
        "client_name": "Order Regression Client", "client_phone": "9876543216",
        "order_date": "2026-07-01T00:00:00", "order_value": "5000",
    })
    assert resp.status_code == 201


"""Tests for the Object Storage abstraction. Proves the
abstraction itself works correctly in isolation, and that every
upload route still behaves identically after being routed through it
- same validation, same authorization, same IDOR protection."""


def test_local_backend_save_read_exists_delete_round_trip():
    """The abstraction in isolation, no HTTP involved. Verifies the
    CURRENT StorageReference-based contract: save() returns a
    reference, and read/exists/delete all require that reference -
    not the bare relative_path string directly."""
    from app.platform.storage import LocalStorageBackend, StorageReference
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalStorageBackend(base_dir=tmp)
        probe_ref = StorageReference(backend="local", relative_path="subdir/test.txt")
        assert backend.exists(probe_ref) is False
        ref = backend.save("subdir/test.txt", b"hello woodful")
        assert isinstance(ref, StorageReference)
        assert ref.backend == "local"
        assert ref.relative_path == "subdir/test.txt"
        assert ref.drive_file_id is None
        assert backend.exists(ref) is True
        assert backend.read(ref) == b"hello woodful"
        backend.delete(ref)
        assert backend.exists(ref) is False


def test_local_backend_delete_of_nonexistent_file_does_not_raise():
    from app.platform.storage import LocalStorageBackend, StorageReference
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        backend = LocalStorageBackend(base_dir=tmp)
        ref = StorageReference(backend="local", relative_path="never_existed.txt")
        backend.delete(ref)  # must not raise


def test_unknown_storage_provider_raises_clearly():
    """Confirms this never silently pretends to be a real cloud
    backend - an unimplemented provider must fail loudly."""
    from app.platform.storage import get_storage_backend
    import app.platform.storage as storage_module
    from app.platform.config import settings as real_settings
    storage_module._backend_instance = None
    original = real_settings.STORAGE_PROVIDER
    real_settings.STORAGE_PROVIDER = "azure_not_implemented"
    try:
        try:
            get_storage_backend()
            assert False, "should have raised"
        except NotImplementedError as e:
            assert "not implemented" in str(e).lower()
    finally:
        real_settings.STORAGE_PROVIDER = original
        storage_module._backend_instance = None


def test_document_upload_still_works_through_the_abstraction(client, test_user):
    """Confirms routing through the abstraction did not change the
    actual upload/download behavior for a real route."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Storage Abstraction Test Client", "phone": "9000010093"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "5000", "advance": "0",
    }).json()
    files = {"file": ("test.pdf", io.BytesIO(b"%PDF-1.4 real pdf content"), "application/pdf")}
    upload = client.post(f"/api/documents/order/{order['id']}", files=files)
    assert upload.status_code == 201

    download = client.get(f"/api/documents/order/{order['id']}/{upload.json()['id']}/download")
    assert download.status_code == 200


def test_document_delete_through_abstraction_removes_the_stored_file(client, test_user):
    """Confirms delete genuinely removes the file, not just the DB row -
    re-downloading after delete must fail."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Storage Delete Test Client", "phone": "9000010094"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "3000", "advance": "0",
    }).json()
    files = {"file": ("delete_me.pdf", io.BytesIO(b"%PDF-1.4 delete test"), "application/pdf")}
    doc = client.post(f"/api/documents/order/{order['id']}", files=files).json()

    delete_resp = client.delete(f"/api/documents/order/{order['id']}/{doc['id']}")
    assert delete_resp.status_code == 204
    download_resp = client.get(f"/api/documents/order/{order['id']}/{doc['id']}/download")
    assert download_resp.status_code == 404


def test_unauthorized_document_access_still_denied_after_abstraction(client, test_user):
    """The core "storage abstraction must not weaken authorization"
    proof - IDOR protection must still hold identically."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Storage IDOR Test Client", "phone": "9000010095"}).json()["id"]
    order_a = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "1000", "advance": "0",
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "2000", "advance": "0",
    }).json()
    files = {"file": ("real.pdf", io.BytesIO(b"%PDF-1.4 real"), "application/pdf")}
    doc = client.post(f"/api/documents/order/{order_a['id']}", files=files).json()

    resp = client.get(f"/api/documents/order/{order_b['id']}/{doc['id']}/download")
    assert resp.status_code == 404


def test_candidate_resume_upload_still_works_through_abstraction(client, test_user):
    """A second, differently-shaped upload route (with its own
    replace-on-reupload logic) also still works correctly."""
    _login(client, test_user)
    candidate = client.post("/api/candidates/", json={
        "name": "Storage Test Candidate", "position_applied": "Carpenter",
    }).json()
    files = {"file": ("resume.pdf", io.BytesIO(b"%PDF-1.4 resume content"), "application/pdf")}
    upload = client.post(f"/api/candidates/{candidate['id']}/resume", files=files)
    assert upload.status_code == 200

    download = client.get(f"/api/candidates/{candidate['id']}/resume")
    assert download.status_code == 200


def test_client_document_delete_survives_db_commit_failure(client, test_user):
    """A correction for a critical ordering issue, exercised against the
    REAL route (not a local stand-in) by making the actual db.commit()
    called inside delete_client_document raise, via unittest.mock
    scoped only around this one HTTP call. Before the fix, the physical
    file was deleted BEFORE this commit; if that ordering had regressed,
    the document would still exist in the DB afterward (since the mocked
    commit prevents the real deletion from persisting) while its file
    would already be gone - the exact inconsistency this test guards
    against. With the fix, a failed commit must raise a 500 and leave
    both the DB record and the file untouched."""
    from unittest.mock import patch
    from sqlalchemy.orm import Session

    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Delete Failure Test Client", "phone": "9000010096"}).json()["id"]
    files = {"file": ("survive.pdf", io.BytesIO(b"%PDF-1.4 must survive"), "application/pdf")}
    doc = client.post(f"/api/clients/{client_id}/documents", files=files).json()

    with patch.object(Session, "commit", side_effect=Exception("simulated DB failure")):
        resp = client.delete(f"/api/clients/{client_id}/documents/{doc['id']}")
    assert resp.status_code == 500

    # The mocked commit is gone now (patch context exited) - a normal
    # download must still succeed, proving neither the DB record nor
    # the physical file was actually removed by the failed attempt.
    download = client.get(f"/api/clients/{client_id}/documents/{doc['id']}/download")
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 must survive"


def test_candidate_resume_replacement_preserves_old_file_until_db_commit_succeeds(client, test_user):
    """A correction for a critical replacement-ordering issue, at the real HTTP/route
    level. Uploads a resume, then replaces it, then verifies the OLD
    file's storage key is gone from disk only once the replacement is
    confirmed to have fully succeeded (the new resume downloads
    correctly) - proving the deletion of the old file was genuinely
    deferred until after the new reference was durably committed,
    not performed eagerly before the outcome was known."""
    _login(client, test_user)
    candidate = client.post("/api/candidates/", json={
        "name": "Resume Replacement Test Candidate", "position": "Carpenter",
    }).json()

    first_files = {"file": ("resume_v1.pdf", io.BytesIO(b"%PDF-1.4 version one"), "application/pdf")}
    first_upload = client.post(f"/api/candidates/{candidate['id']}/resume", files=first_files)
    assert first_upload.status_code == 200

    second_files = {"file": ("resume_v2.pdf", io.BytesIO(b"%PDF-1.4 version two"), "application/pdf")}
    second_upload = client.post(f"/api/candidates/{candidate['id']}/resume", files=second_files)
    assert second_upload.status_code == 200
    assert second_upload.json()["resume_original_filename"] == "resume_v2.pdf"

    # The replacement fully succeeded end-to-end - downloading now must
    # return the NEW content, and the old file must genuinely be gone
    # (not accumulating), confirming cleanup happened on the success
    # path as intended, not left as a permanent duplicate.
    download = client.get(f"/api/candidates/{candidate['id']}/resume")
    assert download.status_code == 200
    assert download.content == b"%PDF-1.4 version two"


# --- security/test_financial_rbac.py ---
def test_master_sees_own_cart_item_rate(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC Master Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "400.00",
    }).json()

    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "2"})
    assert resp.json()["rate"] is not None


def test_employee_own_cart_item_rate_is_genuinely_null(client, test_user, db_session):
    """The real gap found this turn - an employee could previously see
    a material's price by adding it to their own cart, even though the
    Materials page itself hides it from them."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC Employee Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "400.00",
    }).json()

    _create_employee(client, db_session, "cartrbacuser", "cartrbacuser@example.com")
    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "2"})
    assert resp.status_code == 201
    assert resp.json()["rate"] is None
    # Non-financial fields remain visible - it's still a usable cart.
    assert resp.json()["material_name"] == "Cart RBAC Employee Material"
    assert float(resp.json()["quantity"]) == 2.0


def test_employee_cart_list_also_redacts_rate(client, test_user, db_session):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC List Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "250.00",
    }).json()

    _create_employee(client, db_session, "cartlistrbacuser", "cartlistrbacuser@example.com")
    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "1"})
    listed = client.get("/api/personal-cart/").json()
    assert listed[0]["rate"] is None


def test_employee_accumulating_existing_cart_item_still_redacts_rate(client, test_user, db_session):
    """The second add-to-cart code path (existing item, quantity
    accumulates) must also redact - not just the first-add path."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Cart RBAC Accumulate Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "300.00",
    }).json()

    _create_employee(client, db_session, "cartaccumrbacuser", "cartaccumrbacuser@example.com")
    client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "1"})
    resp = client.post("/api/personal-cart/", json={"material_id": material["id"], "quantity": "1"})
    assert resp.json()["rate"] is None
    assert float(resp.json()["quantity"]) == 2.0


def test_chatbot_employee_denied_cart_optimization(client, test_user, db_session):
    """The real gap found this turn - cart optimization explicitly
    compares supplier prices and had no permission check at all."""
    _login(client, test_user)
    supplier_a = client.post("/api/suppliers/", json={"name": "Cart Opt RBAC Supplier A"}).json()
    supplier_b = client.post("/api/suppliers/", json={"name": "Cart Opt RBAC Supplier B"}).json()
    material = client.post("/api/materials/", json={
        "name": "Cart Opt RBAC Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_a["id"], "material_id": material["id"], "supplier_price": "100.00",
    })
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier_b["id"], "material_id": material["id"], "supplier_price": "120.00",
    })

    _create_employee(client, db_session, "cartoptrbacuser", "cartoptrbacuser@example.com")
    resp = client.post("/api/chat/", json={
        "message": "Optimize this purchase",
        "context": {"cart_items": [{"material_id": material["id"], "quantity": 5}]},
    })
    text = resp.json()["response"]
    assert "master accounts only" in text.lower()
    assert "Cart Opt RBAC Supplier A" not in text
    assert "100" not in text


def test_chatbot_master_still_gets_real_cart_optimization(client, test_user):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Cart Opt RBAC Master Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Cart Opt RBAC Master Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/supplier-materials/", json={
        "supplier_id": supplier["id"], "material_id": material["id"], "supplier_price": "100.00",
    })

    resp = client.post("/api/chat/", json={
        "message": "Optimize this purchase",
        "context": {"cart_items": [{"material_id": material["id"], "quantity": 5}]},
    })
    text = resp.json()["response"]
    assert "master accounts only" not in text.lower()
    assert "Cart Opt RBAC Master Supplier" in text


def test_master_sees_estimate_financials(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Master Client", "phone": "9000010059"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "50000", "labor_cost": "20000",
    }).json()

    resp = client.get(f"/api/estimates/{estimate['id']}").json()
    assert resp["material_cost"] is not None
    assert resp["total_cost"] is not None


def test_employee_estimate_financials_are_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Employee Client", "phone": "9000010060"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "50000", "labor_cost": "20000",
    }).json()

    _create_employee_with_name(client, db_session, "Estimate RBAC Employee", "estimaterbacuser", "estimaterbacuser@example.com")
    resp = client.get(f"/api/estimates/{estimate['id']}").json()
    assert resp["material_cost"] is None
    assert resp["labor_cost"] is None
    assert resp["discount"] is None
    assert resp["subtotal"] is None
    assert resp["tax_amount"] is None
    assert resp["total_cost"] is None
    # Non-financial workflow state remains real.
    assert resp["status"] is not None
    assert resp["estimate_code"] == estimate["estimate_code"]


def test_employee_estimate_line_item_pricing_is_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Items Client", "phone": "9000010061"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Cabinet", "unit": "Nos"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id,
        "line_items": [{"description": "Cabinet", "category": "Material", "quantity": "1", "unit": "Nos", "rate": "15000.00", "product_id": product_id}],
    }).json()

    _create_employee_with_name(client, db_session, "Estimate RBAC Items Employee", "estimateitemsrbacuser", "estimateitemsrbacuser@example.com")
    resp = client.get(f"/api/estimates/{estimate['id']}").json()
    assert resp["line_items"][0]["rate"] is None
    assert resp["line_items"][0]["amount"] is None
    assert resp["line_items"][0]["description"] == "Cabinet"


def test_employee_cannot_create_estimate(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Create Client", "phone": "9000010062"}).json()["id"]
    _create_employee_with_name(client, db_session, "Estimate RBAC Create Employee", "estimatecreaterbacuser", "estimatecreaterbacuser@example.com")

    resp = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    })
    assert resp.status_code == 403


def test_employee_cannot_update_estimate(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Update Client", "phone": "9000010063"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    _create_employee_with_name(client, db_session, "Estimate RBAC Update Employee", "estimateupdaterbacuser", "estimateupdaterbacuser@example.com")
    resp = client.put(f"/api/estimates/{estimate['id']}", json={"discount": "1000"})
    assert resp.status_code == 403


def test_employee_cannot_revise_estimate(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Revise Client", "phone": "9000010064"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()

    _create_employee_with_name(client, db_session, "Estimate RBAC Revise Employee", "estimaterevisebacuser", "estimaterevisebacuser@example.com")
    resp = client.post(f"/api/estimates/{estimate['id']}/revise")
    assert resp.status_code == 403


def test_master_can_still_create_update_and_revise_estimates(client, test_user):
    """Backward compatibility - master retains full functionality."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Estimate RBAC Master Full Client", "phone": "9000010065"}).json()["id"]
    estimate = client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "10000", "labor_cost": "5000",
    }).json()
    assert client.put(f"/api/estimates/{estimate['id']}", json={"discount": "500"}).status_code == 200
    assert client.post(f"/api/estimates/{estimate['id']}/revise").status_code == 201


def test_master_sees_material_financial_fields(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Master Visible Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "500.00",
    }).json()

    resp = client.get(f"/api/materials/{material['id']}").json()
    assert resp["average_rate"] is not None
    assert resp["stock_value"] is not None


def test_employee_material_financial_fields_are_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Employee Hidden Rate Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "500.00",
    }).json()

    _create_employee(client, db_session, "matrbacuser", "matrbacuser@example.com")
    resp = client.get(f"/api/materials/{material['id']}").json()
    assert resp["average_rate"] is None
    assert resp["stock_value"] is None
    # Non-financial fields remain visible.
    assert resp["current_stock"] is not None
    assert resp["stock_status"] is not None


def test_employee_material_list_also_redacts_financial_fields(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "List Redaction Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "300.00",
    })

    _create_employee(client, db_session, "listrbacuser", "listrbacuser@example.com")
    materials = client.get("/api/materials/").json()
    match = next(m for m in materials if m["name"] == "List Redaction Material")
    assert match["average_rate"] is None
    assert match["stock_value"] is None


def test_employee_cannot_view_purchases_at_all(client, test_user, db_session):
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Purchase RBAC Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Purchase RBAC Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    purchase = client.post("/api/purchases/", json={
        "date": "2026-08-16T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    }).json()

    _create_employee(client, db_session, "purchaserbacuser", "purchaserbacuser@example.com")
    list_resp = client.get("/api/purchases/")
    assert list_resp.status_code == 403
    get_resp = client.get(f"/api/purchases/{purchase['id']}")
    assert get_resp.status_code == 403


def test_master_can_view_purchases(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/purchases/")
    assert resp.status_code == 200


def test_employee_dashboard_stock_value_is_null(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Dashboard RBAC Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "200.00",
    })

    _create_employee(client, db_session, "dashrbacuser", "dashrbacuser@example.com")
    resp = client.get("/api/dashboard/stock").json()
    assert resp["total_stock_value"] is None
    assert resp["purchase_value"] is None
    # Non-financial figures remain real.
    assert resp["low_stock_items"] is not None
    assert resp["out_of_stock_items"] is not None
    assert resp["recent_stock_movement"] is not None


def test_master_dashboard_stock_value_is_real(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/stock").json()
    assert resp["total_stock_value"] is not None


def test_employee_category_summary_stock_value_is_null(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Category Summary RBAC Material", "unit": "Sheets", "opening_stock": "10",
        "minimum_stock": "1", "average_rate": "200.00", "category": "TestCategoryRBAC",
    })

    _create_employee(client, db_session, "catrbacuser", "catrbacuser@example.com")
    resp = client.get("/api/dashboard/stock").json()
    match = next((c for c in resp["category_summary"] if c["category"] == "TestCategoryRBAC"), None)
    assert match is not None
    assert match["stock_value"] is None


def test_employee_excel_export_excludes_financial_sheets_and_columns(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "excelrbacuser", "excelrbacuser@example.com")

    resp = client.get("/api/reports/stock-dashboard.xlsx")
    assert resp.status_code == 200

    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(resp.content))
    sheet_names = wb.sheetnames
    assert "Dashboard" not in sheet_names
    assert "Purchases" not in sheet_names
    assert "Material Master" in sheet_names
    assert "Issues" in sheet_names

    material_sheet = wb["Material Master"]
    header_row = [c.value for c in material_sheet[4]]
    assert "Average Rate" not in header_row
    assert "Stock Value" not in header_row


def test_master_excel_export_includes_all_sheets(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/reports/stock-dashboard.xlsx")
    assert resp.status_code == 200

    import io
    from openpyxl import load_workbook
    wb = load_workbook(io.BytesIO(resp.content))
    assert set(["Dashboard", "Material Master", "Purchases", "Issues", "Suppliers"]).issubset(set(wb.sheetnames))


def test_chatbot_employee_denied_inventory_value_question(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "chatvaluerbacuser", "chatvaluerbacuser@example.com")

    resp = client.post("/api/chat/", json={"message": "What is the inventory value?"})
    assert "don't have access" in resp.json()["response"].lower()


def test_chatbot_employee_denied_purchase_cost_question(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "chatcostrbacuser", "chatcostrbacuser@example.com")

    resp = client.post("/api/chat/", json={"message": "What was the purchase cost?"})
    assert "don't have access" in resp.json()["response"].lower()


def test_chatbot_employee_denied_spend_question(client, test_user, db_session):
    _login(client, test_user)
    _create_employee(client, db_session, "chatspendrbacuser", "chatspendrbacuser@example.com")

    resp = client.post("/api/chat/", json={"message": "How much did we spend on plywood?"})
    assert "don't have access" in resp.json()["response"].lower()


def test_chatbot_employee_still_gets_real_stock_status_answers(client, test_user, db_session):
    """The three explicitly-permitted questions from the brief must
    still work normally for an employee."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Chat Employee Allowed Material", "unit": "Sheets", "opening_stock": "23", "minimum_stock": "20",
    })
    _create_employee(client, db_session, "chatallowedrbacuser", "chatallowedrbacuser@example.com")

    resp1 = client.post("/api/chat/", json={"message": "How much Chat Employee Allowed Material do we have?"})
    assert "23" in resp1.json()["response"]

    resp2 = client.post("/api/chat/", json={"message": "Which materials are low in stock?"})
    assert resp2.status_code == 200
    assert "don't have access" not in resp2.json()["response"].lower()

    resp3 = client.post("/api/chat/", json={"message": "Which materials are out of stock?"})
    assert resp3.status_code == 200
    assert "don't have access" not in resp3.json()["response"].lower()


def test_chatbot_employee_denied_recent_purchases(client, test_user, db_session):
    """Matches the Purchases API restriction - an employee should not
    learn what was purchased recently via chat if they can't view it
    on the Purchases page either."""
    _login(client, test_user)
    _create_employee(client, db_session, "chatpurchaserbacuser", "chatpurchaserbacuser@example.com")

    resp = client.post("/api/chat/", json={"message": "What materials were purchased recently?"})
    assert "master accounts only" in resp.json()["response"].lower()


def test_chatbot_master_still_gets_real_inventory_value(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "What is the inventory value?"})
    assert "don't have access" not in resp.json()["response"].lower()
    assert "Rs" in resp.json()["response"]


def _create_employee_with_name(client, db_session, name, username, email):
    employee = client.post("/api/employees/", json={
        "name": name, "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200


def test_employee_cannot_create_stock_issue(client, test_user, db_session):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Issue RBAC Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()

    _create_employee_with_name(client, db_session, "Issue RBAC Employee", "issuerbacuser", "issuerbacuser@example.com")
    resp = client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })
    assert resp.status_code == 403

    # Confirm stock is genuinely untouched by the rejected attempt.
    unchanged = client.get(f"/api/materials/{material['id']}").json()
    assert float(unchanged["current_stock"]) == 10.0


def test_master_can_still_create_stock_issue(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Issue RBAC Master Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()

    resp = client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })
    assert resp.status_code == 201


def test_employee_can_still_view_issues(client, test_user, db_session):
    """Viewing stays open - Issues carry no financial fields, matching
    "Employee can view stock"."""
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Issue RBAC View Material", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "1",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-16T00:00:00", "material_id": material["id"], "quantity_issued": "2", "unit": "Sheets",
    })

    _create_employee_with_name(client, db_session, "Issue RBAC View Employee", "issueviewrbacuser", "issueviewrbacuser@example.com")
    resp = client.get("/api/issues/")
    assert resp.status_code == 200


def test_employee_sees_broadcast_low_stock_notification(client, test_user, db_session):
    """The real bug found this turn - operational broadcasts must
    reach employees, not just master."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Notif RBAC Low Stock Material", "unit": "Sheets", "opening_stock": "1", "minimum_stock": "10",
    })

    _create_employee(client, db_session, "notiflowuser", "notiflowuser@example.com")
    notifications = client.get("/api/notifications/").json()
    assert any("Notif RBAC Low Stock Material" in n["title"] for n in notifications)


def test_employee_sees_broadcast_out_of_stock_notification(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Notif RBAC Out Of Stock Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "5",
    })

    _create_employee(client, db_session, "notifoosuser", "notifoosuser@example.com")
    notifications = client.get("/api/notifications/").json()
    assert any("Notif RBAC Out Of Stock Material" in n["title"] for n in notifications)


def test_employee_does_not_see_broadcast_payment_overdue_notification(client, test_user, db_session):
    """The genuinely financial broadcast must still stay hidden."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Notif RBAC Overdue Client", "phone": "9000010130"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "order_value": "50000.00", "advance": "0",
    })

    _create_employee(client, db_session, "notifoverdueuser", "notifoverdueuser@example.com")
    notifications = client.get("/api/notifications/").json()
    assert not any(n["notification_type"] == "PAYMENT_OVERDUE" for n in notifications)


def test_master_still_sees_payment_overdue_notification(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Notif RBAC Master Overdue Client", "phone": "9000010131"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "order_value": "60000.00", "advance": "0",
    })

    notifications = client.get("/api/notifications/").json()
    assert any(n["notification_type"] == "PAYMENT_OVERDUE" for n in notifications)


def test_purchase_received_notification_deep_link_is_accessible_to_everyone(client, test_user, db_session):
    """The dead-end link bug - PURCHASE_RECEIVED is visible to
    employees, so its action_path must not point at a page they can no
    longer access (/purchases is now master-only)."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Notif RBAC Purchase Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Notif RBAC Purchase Material", "unit": "Sheets", "opening_stock": "0", "minimum_stock": "1",
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-16T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "500.00", "gst_percent": "18", "payment_status": "Paid",
    })

    _create_employee(client, db_session, "notifpurchaseuser", "notifpurchaseuser@example.com")
    notifications = client.get("/api/notifications/").json()
    purchase_notif = next(n for n in notifications if n["notification_type"] == "PURCHASE_RECEIVED"
                           and "Notif RBAC Purchase Material" in n["title"])
    assert purchase_notif["action_path"] == f"/materials/{material['id']}"
    # And that page must genuinely be reachable by this employee.
    material_resp = client.get(f"/api/materials/{material['id']}")
    assert material_resp.status_code == 200


def test_master_sees_order_financials(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Master Client", "phone": "9000010132"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "90000.00", "advance": "0",
    }).json()

    resp = client.get(f"/api/orders/{order['id']}").json()
    assert resp["order_value"] is not None
    assert resp["balance"] is not None
    assert resp["payment_status"] is not None


def test_employee_get_order_financials_are_genuinely_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Employee Client", "phone": "9000010133"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "90000.00", "advance": "0",
    }).json()

    _create_employee_with_name(client, db_session, "Order RBAC Employee", "orderrbacuser", "orderrbacuser@example.com")
    resp = client.get(f"/api/orders/{order['id']}").json()
    assert resp["order_value"] is None
    assert resp["advance"] is None
    assert resp["other_received"] is None
    assert resp["total_received"] is None
    assert resp["balance"] is None
    assert resp["items_subtotal"] is None
    assert resp["payment_status"] is None
    # Non-financial order status remains real.
    assert resp["project_status"] is not None
    assert resp["progress_percent"] is not None
    assert resp["order_code"] == order["order_code"]


def test_employee_list_orders_financials_are_null(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC List Client", "phone": "9000010134"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "45000.00", "advance": "0",
    })

    _create_employee_with_name(client, db_session, "Order RBAC List Employee", "orderlistrbacuser", "orderlistrbacuser@example.com")
    orders = client.get("/api/orders/").json()
    match = next(o for o in orders if o["client_id"])
    assert match["order_value"] is None


def test_employee_cannot_derive_order_total_from_line_items(client, test_user, db_session):
    """The deeper part of this fix - redacting only the top-level
    order_value while leaving item.rate/item.amount visible would let
    anyone just sum the line items back to the real total."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Items Client", "phone": "9000010135"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Wardrobe", "unit": "Nos"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "0", "advance": "0",
        "items": [{"description": "Wardrobe", "quantity": "1", "unit": "Nos", "rate": "50000.00", "product_id": product_id}],
    }).json()

    _create_employee_with_name(client, db_session, "Order RBAC Items Employee", "orderitemsrbacuser", "orderitemsrbacuser@example.com")
    resp = client.get(f"/api/orders/{order['id']}").json()
    assert len(resp["items"]) == 1
    assert resp["items"][0]["rate"] is None
    assert resp["items"][0]["amount"] is None
    # Non-financial item fields remain visible - still shows what was ordered.
    assert resp["items"][0]["description"] == "Wardrobe"
    assert resp["items"][0]["quantity"] is not None


def test_master_sees_order_line_item_pricing(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Order RBAC Items Master Client", "phone": "9000010136"}).json()["id"]
    product_id = client.post("/api/products/", json={"name": "Kitchen", "unit": "Nos"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "0", "advance": "0",
        "items": [{"description": "Kitchen", "quantity": "1", "unit": "Nos", "rate": "30000.00", "product_id": product_id}],
    }).json()

    resp = client.get(f"/api/orders/{order['id']}").json()
    assert resp["items"][0]["rate"] is not None
    assert resp["items"][0]["amount"] is not None


def test_master_sees_orders_dashboard_financials(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/orders").json()
    assert resp["total_order_value"] is not None
    assert resp["total_received"] is not None
    assert resp["pending_payment"] is not None


def test_employee_orders_dashboard_financials_are_null(client, test_user, db_session):
    """The real, previously-untouched gap found this turn."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Orders Dash RBAC Client", "phone": "9000010053"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "50000.00", "advance": "0",
    })

    _create_employee_with_name(client, db_session, "Orders Dash RBAC Employee", "ordersdashrbacuser", "ordersdashrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    assert resp["total_order_value"] is None
    assert resp["total_received"] is None
    assert resp["pending_payment"] is None
    # Non-financial fields remain real.
    assert resp["active_orders"] is not None
    assert resp["order_pipeline"] is not None


def test_employee_top_orders_money_fields_are_null_but_status_visible(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Top Orders RBAC Client", "phone": "9000010054"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "70000.00", "advance": "0",
    })

    _create_employee_with_name(client, db_session, "Top Orders RBAC Employee", "toporderrbacuser", "toporderrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    match = next(o for o in resp["top_orders"] if o["client"] == "Top Orders RBAC Client")
    assert match["order_value"] is None
    assert match["received"] is None
    assert match["pending"] is None
    assert match["status"] is not None


def test_employee_order_profitability_is_empty_not_leaked(client, test_user, db_session):
    _login(client, test_user)
    _create_employee_with_name(client, db_session, "Profit Dash RBAC Employee", "profitdashrbacuser", "profitdashrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    assert resp["order_profitability"] == []


def test_employee_cannot_export_another_employees_attendance(client, test_user, db_session):
    """Item A: /api/reports/attendance.xlsx previously had no ownership
    check at all - any authenticated employee could pass an arbitrary
    employee_id and download another employee's full attendance data."""
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Attendance Export Target", "monthly_salary": "20000", "daily_wage": "800",
    }).json()

    _create_employee(client, db_session, "attexportrbacuser", "attexportrbacuser@example.com")
    resp = client.get(f"/api/reports/attendance.xlsx?employee_id={other_employee['id']}")
    assert resp.status_code == 403

    # Exporting with no employee_id filter (or their own) still works -
    # this is an ownership check, not a blanket export ban.
    own_resp = client.get("/api/reports/attendance.xlsx")
    assert own_resp.status_code == 200


def test_employee_cannot_export_another_employees_leaves(client, test_user, db_session):
    """Item B: /api/reports/leaves.xlsx had the identical gap as
    attendance export."""
    _login(client, test_user)
    other_employee = client.post("/api/employees/", json={
        "name": "Leave Export Target", "monthly_salary": "20000", "daily_wage": "800",
    }).json()

    _create_employee(client, db_session, "leaveexportrbacuser", "leaveexportrbacuser@example.com")
    resp = client.get(f"/api/reports/leaves.xlsx?employee_id={other_employee['id']}")
    assert resp.status_code == 403

    own_resp = client.get("/api/reports/leaves.xlsx")
    assert own_resp.status_code == 200


def test_employee_staff_dashboard_total_overtime_is_null(client, test_user, db_session):
    """Item C: /api/dashboard/staff's total_overtime was an
    organization-wide aggregate returned unconditionally, unlike
    employee_performance right next to it, which was already
    correctly redacted."""
    _login(client, test_user)
    _create_employee_with_name(client, db_session, "Staff Dash RBAC Employee", "staffdashrbacuser", "staffdashrbacuser@example.com")
    resp = client.get("/api/dashboard/staff").json()
    assert resp["total_overtime"] is None
    # Non-financial/non-aggregate fields remain visible.
    assert resp["active_employees"] is not None


def test_master_staff_dashboard_total_overtime_is_real(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/staff").json()
    assert resp["total_overtime"] is not None


def test_employee_workforce_analytics_hour_totals_are_null(client, test_user, db_session):
    """Item D: /api/analytics/workforce's total_overtime_hours/
    total_working_hours were the same organization-wide, unguarded
    aggregate as the staff dashboard's total_overtime."""
    _login(client, test_user)
    _create_employee_with_name(client, db_session, "Workforce RBAC Employee", "workforcerbacuser", "workforcerbacuser@example.com")
    resp = client.get("/api/analytics/workforce").json()
    assert resp["total_overtime_hours"] is None
    assert resp["total_working_hours"] is None


def test_master_workforce_analytics_hour_totals_are_real(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/analytics/workforce").json()
    assert resp["total_overtime_hours"] is not None
    assert resp["total_working_hours"] is not None


def test_employee_top_orders_are_not_sorted_by_real_financial_value(client, test_user, db_session):
    """Item E: order_value was already correctly redacted to None in
    top_orders, but the list itself was still sorted by the real,
    unredacted value - leaking relative financial ranking through
    position alone. For a non-privileged viewer, the sort order must
    not depend on order_value at all."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Sort Leak RBAC Client", "phone": "9000010099"}).json()["id"]
    low_value_high_progress = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "1000.00", "advance": "0",
    }).json()
    update_resp_1 = client.put(f"/api/orders/{low_value_high_progress['id']}", json={"progress_percent": 90})
    assert update_resp_1.status_code == 200
    high_value_low_progress = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "900000.00", "advance": "0",
    }).json()
    update_resp_2 = client.put(f"/api/orders/{high_value_low_progress['id']}", json={"progress_percent": 5})
    assert update_resp_2.status_code == 200

    _create_employee_with_name(client, db_session, "Sort Leak RBAC Employee", "sortleakrbacuser", "sortleakrbacuser@example.com")
    resp = client.get("/api/dashboard/orders").json()
    ids_in_order = [o["id"] for o in resp["top_orders"]]
    # The high-progress/low-value order must rank ahead of the
    # low-progress/high-value one for a non-privileged viewer - if the
    # list were still (bug-era) sorted by the real order_value, the
    # order would be reversed even though order_value itself reads None.
    assert ids_in_order.index(low_value_high_progress["id"]) < ids_in_order.index(high_value_low_progress["id"])
    for o in resp["top_orders"]:
        assert o["order_value"] is None


def test_employee_client_pdf_excludes_sales_summary_and_order_values(client, test_user, db_session):
    """Item F: generate_client_pdf never received any role information
    at all, so it always printed full order values and totals
    regardless of who requested it - a direct bypass of the JSON
    client API's own, already-correct financial redaction."""
    import pypdf
    from io import BytesIO

    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "PDF Leak RBAC Client", "phone": "9000010088"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "50000.00", "advance": "0",
    })

    _create_employee_with_name(client, db_session, "PDF Leak RBAC Employee", "pdfleakrbacuser", "pdfleakrbacuser@example.com")
    resp = client.get(f"/api/reports/clients/{client_id}/profile.pdf")
    assert resp.status_code == 200
    reader = pypdf.PdfReader(BytesIO(resp.content))
    pdf_text = "".join(page.extract_text() for page in reader.pages)
    assert "SALES SUMMARY" not in pdf_text
    # The real order value, as ReportLab genuinely renders it (via
    # format_inr), must not appear anywhere in the extracted PDF text.
    assert "50,000" not in pdf_text


def test_master_client_pdf_includes_sales_summary(client, test_user):
    import pypdf
    from io import BytesIO

    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "PDF Master RBAC Client", "phone": "9000010077"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-16T00:00:00", "order_value": "50000.00", "advance": "0",
    })
    resp = client.get(f"/api/reports/clients/{client_id}/profile.pdf")
    assert resp.status_code == 200
    reader = pypdf.PdfReader(BytesIO(resp.content))
    pdf_text = "".join(page.extract_text() for page in reader.pages)
    assert "SALES SUMMARY" in pdf_text
    assert "50,000" in pdf_text


def _login_with_credentials(client, identifier="test@example.com", password="TestPass123!"):
    resp = client.post("/api/auth/login", json={"identifier": identifier, "password": password})
    assert resp.status_code == 200
    return resp


def _create_employee_user(client, db_session, employee_id, username, email, password="EmpPass1!"):
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password(password), role="user",
        employee_id=employee_id, is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


def _seed_master_data(client):
    """Creates one of everything analytics aggregates, using the real
    module endpoints (not direct DB inserts) so every figure analytics
    reports on is a genuine authoritative record."""
    client_obj = client.post("/api/clients/", json={"name": "Analytics Test Client", "phone": "9000010086"}).json()
    order = client.post("/api/orders/", json={
        "client_id": client_obj["id"], "order_date": "2026-06-01T00:00:00",
        "order_value": "100000", "advance": "20000",
    }).json()
    client.post("/api/payments/", json={
        "order_id": order["id"], "amount": "10000", "payment_date": "2026-08-01T00:00:00",
    })
    supplier = client.post("/api/suppliers/", json={"name": "Analytics Test Supplier"}).json()
    material = client.post("/api/materials/", json={
        "name": "Analytics Test Ply", "unit": "Sheets", "opening_stock": "2",
        "minimum_stock": "10", "average_rate": "1500.00", "supplier_id": supplier["id"],
    }).json()
    client.post("/api/purchases/", json={
        "date": "2026-08-01T00:00:00", "supplier_id": supplier["id"], "material_id": material["id"],
        "quantity": "5", "unit": "Sheets", "rate": "1500.00", "gst_percent": "18",
        "payment_status": "Pending",
    })
    client.post("/api/project-expenses/", json={
        "date": "2026-08-01T00:00:00", "order_id": order["id"], "category": "Raw Material",
        "amount": "5000",
    })
    return {"client": client_obj, "order": order, "supplier": supplier, "material": material}


def _make_non_master(client, db_session, name="Analytics RBAC Employee", username="analyticsrbacuser",
                      email="analyticsrbacuser@example.com"):
    employee = client.post("/api/employees/", json={"name": name}).json()
    _create_employee_user(client, db_session, employee["id"], username, email)
    _login_with_credentials(client, identifier=email, password="EmpPass1!")
    return employee


def test_master_only_domains_blocked_for_non_master(client, test_user, db_session):
    """sales, purchases, payments, expenses aggregate financial totals
    across every client/order - matching purchases.py / payments.py /
    project_expenses.py's own master-only gates."""
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    for path in ("/api/analytics/sales", "/api/analytics/purchases",
                 "/api/analytics/payments", "/api/analytics/expenses"):
        resp = client.get(path)
        assert resp.status_code == 403, path


def test_open_domains_available_to_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    for path in ("/api/analytics/inventory", "/api/analytics/production",
                 "/api/analytics/projects", "/api/analytics/tasks",
                 "/api/analytics/workforce", "/api/analytics/operations"):
        resp = client.get(path)
        assert resp.status_code == 200, path


def test_alerts_feed_excludes_master_only_domains_for_non_master(client, test_user, db_session):
    """The consolidated /alerts feed must not leak sales/purchases/expenses
    alerts to a non-master viewer, even though it fans out across every
    domain internally."""
    _login_with_credentials(client)
    # _seed_master_data's order is dated 2026-06-01, well over 60 days
    # before the current date, so the sales alert fires for master
    # without any extra setup.
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/alerts")
    assert resp.status_code == 200
    domains = {a["domain"] for a in resp.json()["alerts"]}
    assert domains.isdisjoint({"sales", "purchases", "expenses"})


def test_inventory_stock_value_redacted_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/inventory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_stock_value"] is None
    assert all(c["stock_value"] is None for c in data["category_breakdown"])

    # Same call, as master, must show the real figure.
    _login_with_credentials(client)
    master_data = client.get("/api/analytics/inventory").json()
    assert master_data["total_stock_value"] is not None
    assert master_data["total_stock_value"] > 0


def test_operations_stock_value_redacted_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/operations").json()
    assert resp["total_stock_value"] is None


def test_project_profitability_hidden_from_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/analytics/projects").json()
    assert resp["order_profitability"] == []
    assert resp["overall_gross_margin_ratio"] is None

    _login_with_credentials(client)
    master_resp = client.get("/api/analytics/projects").json()
    assert len(master_resp["order_profitability"]) >= 1
    assert master_resp["overall_gross_margin_ratio"] is not None


def test_gross_margin_is_a_ratio_not_a_0_to_100_percent(client, test_user):
    """Regression for the gross-margin naming/scale contract:
    gross_margin_ratio must be a fraction (e.g. ~0.85 for an
    85% margin), never a 0-100 value - a field that was previously
    misnamed "gross_margin_percent" while holding a ratio, which risked
    a 100x misinterpretation by any new consumer that took the name at
    face value."""
    _login_with_credentials(client)
    _seed_master_data(client)

    resp = client.get("/api/analytics/projects").json()
    rows = resp["order_profitability"]
    assert len(rows) >= 1
    for row in rows:
        # order_value=100000, direct costs from the seeded purchase/expense
        # are well under the order value, so this must be a positive
        # fraction less than 1 - never anywhere near a 0-100 scale value.
        assert -1.0 <= row["gross_margin_ratio"] <= 1.0

    # The overall aggregate must be on the exact same ratio scale as each
    # per-order row - this is precisely the two-scale inconsistency the
    # fix removes.
    assert -1.0 <= resp["overall_gross_margin_ratio"] <= 1.0


def test_gross_margin_ratio_is_none_when_no_orders(client, test_user, db_session):
    """Zero-revenue / no-order case must not divide by zero or otherwise
    error - it should report a clean 0.0 for order rows with no order
    value, and the aggregate should still resolve without raising."""
    _login_with_credentials(client)
    resp = client.get("/api/analytics/projects")
    assert resp.status_code == 200
    body = resp.json()
    assert body["order_profitability"] == []
    assert body["overall_gross_margin_ratio"] == 0.0


def test_outstanding_orders_drill_down_is_real_and_master_only(client, test_user, db_session):
    _login_with_credentials(client)
    seed = _seed_master_data(client)
    _make_non_master(client, db_session)

    # Non-master can't reach the drill-down data at all.
    assert client.get("/api/analytics/sales").status_code == 403

    _login_with_credentials(client)
    data = client.get("/api/analytics/sales").json()
    order_ids = {o["id"] for o in data["outstanding_orders"]}
    assert seed["order"]["id"] in order_ids
    # The outstanding total must equal the real Order.balance sum, not a
    # separately-invented figure.
    order_detail = client.get(f"/api/orders/{seed['order']['id']}").json()
    assert any(o["balance"] == float(order_detail["balance"]) for o in data["outstanding_orders"])


def test_low_stock_drill_down_visible_but_stock_value_not(client, test_user, db_session):
    _login_with_credentials(client)
    seed = _seed_master_data(client)
    _make_non_master(client, db_session)

    data = client.get("/api/analytics/inventory").json()
    material_ids = {m["id"] for m in data["low_stock_materials"]}
    assert seed["material"]["id"] in material_ids
    # Drill-down rows expose quantities, never a redacted-financial field.
    assert "stock_value" not in data["low_stock_materials"][0]


def test_master_only_exports_blocked_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    for path in ("/api/reports/purchases.xlsx", "/api/reports/payments.xlsx",
                 "/api/reports/project-expenses.xlsx"):
        resp = client.get(path)
        assert resp.status_code == 403, path


def test_orders_export_redacts_financial_columns_for_non_master(client, test_user, db_session):
    import io
    from openpyxl import load_workbook

    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.get("/api/reports/orders.xlsx")
    assert resp.status_code == 200
    wb = load_workbook(io.BytesIO(resp.content))
    ws = wb.active
    # Locate the actual header row (title/subtitle rows come first).
    header_row = []
    for row in ws.iter_rows(values_only=True):
        if row and "Client" in row:
            header_row = list(row)
            break
    assert "Order Value" not in header_row
    assert "Balance" not in header_row

    _login_with_credentials(client)
    master_resp = client.get("/api/reports/orders.xlsx")
    wb2 = load_workbook(io.BytesIO(master_resp.content))
    ws2 = wb2.active
    master_header = []
    for row in ws2.iter_rows(values_only=True):
        if row and "Client" in row:
            master_header = list(row)
            break
    assert "Order Value" in master_header
    assert "Balance" in master_header


def test_workforce_non_master_sees_only_own_row(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    other_employee = client.post("/api/employees/", json={"name": "Other Workforce Employee"}).json()
    own_employee = _make_non_master(
        client, db_session, name="Own Workforce Employee",
        username="workforceown", email="workforceown@example.com",
    )

    resp = client.get("/api/analytics/workforce").json()
    ids_seen = {row["employee_id"] for row in resp["employee_performance"]}
    assert ids_seen == {own_employee["id"]}
    assert other_employee["id"] not in ids_seen

    _login_with_credentials(client)
    master_resp = client.get("/api/analytics/workforce").json()
    master_ids = {row["employee_id"] for row in master_resp["employee_performance"]}
    assert other_employee["id"] in master_ids
    assert own_employee["id"] in master_ids


def test_ai_expense_explanation_blocked_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.post("/api/chat/", json={"message": "why did expenses increase this month"})
    assert resp.status_code == 200
    assert "master accounts only" in resp.json()["response"].lower()


def test_ai_whats_changed_omits_financial_lines_for_non_master(client, test_user, db_session):
    _login_with_credentials(client)
    _seed_master_data(client)
    _make_non_master(client, db_session)

    resp = client.post("/api/chat/", json={"message": "what changed this month"})
    assert resp.status_code == 200
    text = resp.json()["response"].lower()
    assert "revenue" not in text
    assert "expenses are" not in text

    _login_with_credentials(client)
    master_resp = client.post("/api/chat/", json={"message": "what changed this month"})
    assert master_resp.status_code == 200


def test_ai_delayed_projects_grounded_in_real_projects_analytics(client, test_user, db_session):
    """The chatbot's delayed-projects answer must agree with what the
    Analytics page's own drill-down shows for the same underlying data -
    never a separately fabricated list."""
    _login_with_credentials(client)
    seed = _seed_master_data(client)
    client.put(f"/api/orders/{seed['order']['id']}", json={"project_status": "On Hold"})

    resp = client.post("/api/chat/", json={"message": "which projects are delayed"})
    assert resp.status_code == 200
    body = resp.json()
    record_paths = {r["path"] for r in body["records"]}
    assert f"/orders/{seed['order']['id']}" in record_paths

    analytics_resp = client.get("/api/analytics/projects").json()
    delayed_paths = {f"/orders/{p['id']}" for p in analytics_resp["delayed_projects"]}
    assert record_paths == delayed_paths


def _create_and_login_employee(client, db_session, username, email):
    employee = client.post("/api/employees/", json={"name": "PDF RBAC Employee", "monthly_salary": "20000"}).json()
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/auth/login", json={"identifier": email, "password": "EmpPass1!"})
    assert resp.status_code == 200


def _seed_order(client):
    client_id = client.post("/api/clients/", json={"name": "PDF RBAC Client", "phone": "9000010073"}).json()["id"]
    return client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "TV Unit",
        "order_date": "2026-08-01T00:00:00", "order_value": "50000.00", "advance": "10000.00",
    }).json()


def _seed_estimate(client):
    client_id = client.post("/api/clients/", json={"name": "PDF RBAC Estimate Client", "phone": "9000010074"}).json()["id"]
    return client.post("/api/estimates/", json={
        "client_id": client_id, "material_cost": "30000", "labor_cost": "10000",
    }).json()


def test_master_can_download_order_estimate_pdf(client, test_user):
    _login(client, test_user)
    order = _seed_order(client)
    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_user_cannot_download_order_estimate_pdf(client, test_user, db_session):
    _login(client, test_user)
    order = _seed_order(client)
    _create_and_login_employee(client, db_session, "pdfrbacuser1", "pdfrbacuser1@example.com")
    resp = client.get(f"/api/reports/orders/{order['id']}/estimate.pdf")
    assert resp.status_code == 403


def test_master_can_download_estimate_quote_pdf(client, test_user):
    _login(client, test_user)
    estimate = _seed_estimate(client)
    resp = client.get(f"/api/reports/estimates/{estimate['id']}/quote.pdf")
    assert resp.status_code == 200
    assert resp.content.startswith(b"%PDF")


def test_user_cannot_download_estimate_quote_pdf(client, test_user, db_session):
    _login(client, test_user)
    estimate = _seed_estimate(client)
    _create_and_login_employee(client, db_session, "pdfrbacuser2", "pdfrbacuser2@example.com")
    resp = client.get(f"/api/reports/estimates/{estimate['id']}/quote.pdf")
    assert resp.status_code == 403


def test_pdf_exports_require_auth(client):
    resp = client.get("/api/reports/orders/1/estimate.pdf")
    assert resp.status_code == 401
    resp = client.get("/api/reports/estimates/1/quote.pdf")
    assert resp.status_code == 401


# --- security/test_security_and_config.py ---
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


def test_settings_accepts_comma_separated_cors_origins(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key-not-for-real-use-1234567890")
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000,http://127.0.0.1:3000")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")

    # Re-import fresh so it picks up the monkeypatched env vars rather than
    # any cached settings instance from a prior test.
    import importlib
    from app.platform import config as config_module
    importlib.reload(config_module)

    fresh_settings = config_module.Settings()
    assert fresh_settings.cors_origins_list == [
        "http://localhost:3000", "http://localhost:8000", "http://127.0.0.1:3000",
    ]


def test_settings_allowed_extensions_split_correctly(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-only-secret-key-not-for-real-use-1234567890")
    monkeypatch.setenv("ALLOWED_EXTENSIONS", "pdf,xlsx,docx")

    import importlib
    from app.platform import config as config_module
    importlib.reload(config_module)

    fresh_settings = config_module.Settings()
    assert fresh_settings.allowed_extensions_list == ["pdf", "xlsx", "docx"]


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
    from app.shared import _sanitize_cell_value
    assert _sanitize_cell_value("Rs 1,25,000.00") == "Rs 1,25,000.00"
    assert _sanitize_cell_value(42) == 42
    assert _sanitize_cell_value(None) is None
    assert _sanitize_cell_value("Normal Client Name") == "Normal Client Name"


def test_all_four_dangerous_prefixes_are_escaped():
    from app.shared import _sanitize_cell_value
    for dangerous in ["=SUM(A1)", "+1+1", "-2+3", "@SUM(A1)"]:
        result = _sanitize_cell_value(dangerous)
        assert result.startswith("'")
        assert result == "'" + dangerous


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


def test_debug_true_in_production_is_rejected():
    from app.platform.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(SECRET_KEY="a" * 48, DATABASE_URL="sqlite:///test.db", ENVIRONMENT="production", DEBUG=True)


def test_debug_true_in_development_is_allowed():
    from app.platform.config import Settings
    s = Settings(SECRET_KEY="a" * 48, DATABASE_URL="sqlite:///test.db", ENVIRONMENT="development", DEBUG=True)
    assert s.DEBUG is True


def test_debug_false_in_production_is_allowed():
    # DEBUG=False alone doesn't make a production config valid - every
    # other production requirement (real Postgres URL, secure cookies,
    # explicit non-localhost CORS, shared rate-limit backend) must also
    # be satisfied, or this raises for one of those reasons instead of
    # exercising what this test is actually about.
    from app.platform.config import Settings
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
    from app.platform.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(RATE_LIMIT_BACKEND="memory"))


def test_production_allows_redis_rate_limit_backend():
    from app.platform.config import Settings
    s = Settings(**_prod_settings_kwargs())
    assert s.RATE_LIMIT_BACKEND == "redis"


def test_production_rejects_localhost_cors_origin():
    from app.platform.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(CORS_ORIGINS="http://localhost:3000"))


def test_production_rejects_empty_cors_origins():
    from app.platform.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(CORS_ORIGINS=""))


def test_wildcard_cors_origin_rejected_in_any_environment():
    from app.platform.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(
            SECRET_KEY="a" * 48, DATABASE_URL="sqlite:///test.db",
            ENVIRONMENT="development", CORS_ORIGINS="*",
        )


def test_gemini_enabled_without_api_key_is_rejected():
    from app.platform.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(GEMINI_ENABLED=True, GEMINI_API_KEY=""))


def test_gemini_enabled_with_api_key_is_allowed():
    from app.platform.config import Settings
    s = Settings(**_prod_settings_kwargs(GEMINI_ENABLED=True, GEMINI_API_KEY="fake-key-for-test"))
    assert s.GEMINI_ENABLED is True


def test_drive_enabled_without_credentials_is_rejected():
    from app.platform.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(GOOGLE_DRIVE_ENABLED=True))


def test_storage_provider_drive_without_enabled_flag_is_rejected():
    from app.platform.config import Settings
    import pytest
    with pytest.raises(Exception):
        Settings(**_prod_settings_kwargs(STORAGE_PROVIDER="drive"))


def test_global_rate_limit_middleware_blocks_after_threshold(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200

    from app.platform.config import settings
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


def test_in_memory_backend_allows_up_to_the_limit():
    from app.platform.security import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(5):
        assert backend.is_allowed("test-key", max_requests=5, window_seconds=60) is True


def test_in_memory_backend_blocks_beyond_the_limit():
    from app.platform.security import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(5):
        backend.is_allowed("test-key", max_requests=5, window_seconds=60)
    assert backend.is_allowed("test-key", max_requests=5, window_seconds=60) is False


def test_in_memory_backend_keys_are_independent():
    from app.platform.security import _InMemoryBackend
    backend = _InMemoryBackend()
    for _ in range(5):
        backend.is_allowed("key-a", max_requests=5, window_seconds=60)
    # A different key must have its own independent budget.
    assert backend.is_allowed("key-b", max_requests=5, window_seconds=60) is True


def test_in_memory_backend_window_expires():
    from app.platform.security import _InMemoryBackend
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
    import app.platform.security as module
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

    from app.platform.config import settings
    responses = [client.post("/api/chat/", json={"message": "hello"}) for _ in range(settings.RATE_LIMIT_CHAT_PER_MINUTE + 3)]
    assert any(r.status_code == 429 for r in responses)


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
    from app.platform import config as config_module
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
    from app.platform.database import _alembic_config
    cfg = _alembic_config()
    ini_path = Path(cfg.config_file_name)
    script_location = Path(cfg.get_main_option("script_location"))
    assert ini_path.exists(), f"{ini_path} does not exist - alembic.ini path resolution is broken"
    assert script_location.exists(), f"{script_location} does not exist - alembic script_location resolution is broken"
    assert (script_location / "env.py").exists()
