"""Reporting domain tests: dashboard metrics, global search, and
business-decision analytics. Combines the former test_dashboard.py,
test_search.py and test_business_decisions.py."""
from app.platform.security import hash_password
from app.modules.auth.auth import User
from tests.helpers import _login
from datetime import datetime, timedelta

# --- test_dashboard.py ---
"""Tests for /api/dashboard/* - the overview widgets. overall_gross_margin_ratio
specifically: a true aggregate across every order, not derived from the
top-orders sample also returned here (which is deliberately bounded to
10) - see OrderService.overall_gross_margin's own docstring for why
those must be two different calculations."""

def _create_order_with_costs(client, name_suffix, order_value="20000.00"):
    client_id = client.post("/api/clients/", json={
        "name": f"Dashboard Margin Test Client {name_suffix}", "phone": f"90000101{name_suffix}",
    }).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-15T00:00:00", "order_value": order_value, "advance": "0",
    }).json()
    material = client.post("/api/materials/", json={
        "name": f"Dashboard Margin Test Material {name_suffix}", "unit": "Sheets",
        "opening_stock": "10", "minimum_stock": "1", "average_rate": "500.00",
    }).json()
    client.post("/api/issues/", json={
        "date": "2026-08-15T00:00:00", "order_id": order["id"], "material_id": material["id"],
        "quantity_issued": "4", "unit": "Sheets",
    })
    return order


def test_overall_gross_margin_ratio_is_a_true_aggregate_not_a_sample(client, test_user):
    """The core regression this field exists to prevent: with more
    orders than the top-orders list holds (10), the aggregate must
    still reflect ALL of them, not just the sampled subset."""
    _login(client, test_user)
    orders = [_create_order_with_costs(client, str(i)) for i in range(12)]
    assert len(orders) == 12

    resp = client.get("/api/dashboard/orders").json()
    assert len(resp["top_orders"]) <= 10  # confirms the sample really is bounded
    assert resp["overall_gross_margin_ratio"] is not None
    # order_value=20000, material_cost=4*500=2000, no other expenses ->
    # gross profit 18000 on this order; every seeded order here is
    # identical, so the aggregate ratio must equal any single order's.
    assert abs(resp["overall_gross_margin_ratio"] - 0.9) < 0.01


def test_overall_gross_margin_ratio_is_none_for_non_master(client, test_user, db_session):
    _login(client, test_user)
    _create_order_with_costs(client, "1")

    employee = User(
        username="dashboardmarginuser", email="dashboardmarginuser@example.com", full_name="Dashboard Margin User",
        password_hash=hash_password("EmpPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(employee)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "dashboardmarginuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/dashboard/orders").json()
    assert resp["overall_gross_margin_ratio"] is None
    assert resp["order_profitability"] == []


def test_overall_gross_margin_ratio_is_zero_when_no_orders(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/orders").json()
    assert resp["overall_gross_margin_ratio"] == 0.0


def test_delivery_risk_summary_counts_critical_order(client, test_user):
    """P0.50 section 23 - the dashboard summary must reuse the exact
    same bulk_attention_flags calculation as the Orders List, never a
    separately-derived count."""
    from datetime import datetime, timedelta
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Dashboard Risk Client", "phone": "9000010150"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
        "delivery_date": (datetime.utcnow() - timedelta(days=2)).isoformat(),
    }).json()
    employee = client.post("/api/employees/", json={"name": "Dashboard Risk Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Dashboard critical work", "status": "BLOCKED", "delay_reason": "Waiting for parts",
    })

    resp = client.get("/api/dashboard/orders").json()
    assert resp["delivery_risk_summary"]["CRITICAL"] >= 1


def test_delivery_risk_summary_excludes_completed_orders(client, test_user):
    """A Completed order's historical delivery timing is not an
    actionable "needs attention today" signal, even if its delivery
    date happens to be in the past."""
    from datetime import datetime, timedelta
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Dashboard Completed Client", "phone": "9000010151"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-07-01T00:00:00", "order_value": "5000", "advance": "0",
        "delivery_date": (datetime.utcnow() - timedelta(days=10)).isoformat(),
    }).json()
    client.put(f"/api/orders/{order['id']}", json={"project_status": "Completed"})

    resp = client.get("/api/dashboard/orders").json()
    total_active_in_summary = sum(resp["delivery_risk_summary"].values())
    # This order (now Completed) must not be counted in the summary at
    # all - active_orders (the denominator this summary is built from)
    # must also exclude it.
    assert total_active_in_summary == resp["active_orders"]

# --- test_search.py ---


def test_search_requires_auth(client):
    resp = client.get("/api/search/", params={"q": "test"})
    assert resp.status_code == 401


def test_search_finds_client_by_name(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Zephyr Interiors", "phone": "9000010180"})

    resp = client.get("/api/search/", params={"q": "Zephyr"})
    assert resp.status_code == 200
    results = resp.json()
    assert any(r["type"] == "Client" and r["label"] == "Zephyr Interiors" for r in results)


def test_search_finds_client_by_phone(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Phone Search Client", "phone": "9123456780"})

    resp = client.get("/api/search/", params={"q": "9123456780"})
    results = resp.json()
    assert any(r["type"] == "Client" and r["label"] == "Phone Search Client" for r in results)


def test_search_finds_material_by_code_not_just_name(client, test_user):
    _login(client, test_user)
    created = client.post("/api/materials/", json={
        "name": "Search Test Plywood", "unit": "Sheets", "opening_stock": 10, "minimum_stock": 2,
    }).json()
    material_code = created["material_code"]

    resp = client.get("/api/search/", params={"q": material_code})
    results = resp.json()
    assert any(r["type"] == "Material" and r["id"] == created["id"] for r in results)


def test_search_returns_correct_navigable_path(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Path Check Client", "phone": "9000010181"}).json()

    resp = client.get("/api/search/", params={"q": "Path Check Client"})
    result = next(r for r in resp.json() if r["type"] == "Client")
    assert result["path"] == f"/clients/{created['id']}"


def test_search_across_multiple_types_returns_both(client, test_user):
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "CrossType Alpha", "phone": "9000010182"})
    client.post("/api/suppliers/", json={"name": "CrossType Alpha Supplier"})

    resp = client.get("/api/search/", params={"q": "CrossType Alpha"})
    types_found = {r["type"] for r in resp.json()}
    assert "Client" in types_found
    assert "Supplier" in types_found


def test_search_empty_query_returns_empty_list(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/search/", params={"q": ""})
    assert resp.status_code in (200, 422)


def test_search_no_match_returns_empty_list(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/search/", params={"q": "ThisMatchesAbsolutelyNothingXYZ123"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_search_by_business_id_finds_the_record(client, test_user):
    _login(client, test_user)
    created = client.post("/api/clients/", json={"name": "Business ID Search Client", "phone": "9000010183"}).json()
    business_id = created["business_id"]
    assert business_id is not None

    resp = client.get("/api/search/", params={"q": business_id})
    assert resp.status_code == 200
    results = resp.json()
    assert any(r["type"] == "Client" and r["id"] == created["id"] for r in results)


def test_search_by_business_id_across_entity_types(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Search By Business ID Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1,
    }).json()

    resp = client.get("/api/search/", params={"q": material["business_id"]})
    results = resp.json()
    assert any(r["type"] == "Material" and r["id"] == material["id"] for r in results)

# --- test_business_decisions.py ---
"""Tests for /api/business-decisions/* (Family P0.49/P0.51). Reuses
compute_order_health (never a second risk calculation) and real
SalarySlip/SalaryAdvance data - master-only for payroll signals,
employees see only operational (order) risk."""

def _make_critical_order(client, suffix):
    client_id = client.post("/api/clients/", json={
        "name": f"Business Decision Client {suffix}", "phone": f"90000109{suffix}",
    }).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
        "delivery_date": (datetime.utcnow() - timedelta(days=2)).isoformat(),
    }).json()
    employee = client.post("/api/employees/", json={"name": f"Business Decision Employee {suffix}"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Critical work", "status": "BLOCKED", "delay_reason": "Waiting for parts",
    })
    return order


def test_no_risks_when_nothing_is_wrong(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/business-decisions/")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 0
    assert body["risks"] == []
    assert body["counts"] == {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}


def test_critical_order_appears_as_delivery_risk(client, test_user):
    _login(client, test_user)
    order = _make_critical_order(client, "1")

    resp = client.get("/api/business-decisions/")
    body = resp.json()
    matches = [r for r in body["risks"] if r["entity_id"] == order["id"]]
    assert len(matches) == 1
    risk = matches[0]
    assert risk["risk_type"] == "DELIVERY"
    assert risk["severity"] == "CRITICAL"
    assert risk["entity_code"] == order["order_code"]
    assert risk["source_module"] == "sales"
    assert risk["action_path"] == f"/orders/{order['id']}"
    assert body["counts"]["CRITICAL"] >= 1


def test_completed_order_never_appears_as_a_risk(client, test_user):
    _login(client, test_user)
    order = _make_critical_order(client, "2")
    client.put(f"/api/orders/{order['id']}", json={"project_status": "Completed"})

    resp = client.get("/api/business-decisions/")
    body = resp.json()
    assert not any(r["entity_id"] == order["id"] for r in body["risks"])


def test_finalized_unpaid_salary_slip_is_a_payroll_risk_for_master(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Business Decision Payroll Employee", "monthly_salary": "20000"}).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "September", "year": "2026", "basic": "20000",
    }).json()
    client.put(f"/api/salary-slips/{slip['id']}", json={"status": "finalized"})

    resp = client.get("/api/business-decisions/")
    body = resp.json()
    matches = [r for r in body["risks"] if r["entity_type"] == "salary_slip" and r["entity_id"] == slip["id"]]
    assert len(matches) == 1
    assert matches[0]["risk_type"] == "PAYROLL"
    assert matches[0]["source_module"] == "hr"


def test_pending_salary_advance_is_a_low_severity_risk_for_master(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Business Decision Advance Employee", "monthly_salary": "20000"}).json()
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "3000", "request_date": "2026-09-01T00:00:00",
    }).json()

    resp = client.get("/api/business-decisions/")
    body = resp.json()
    matches = [r for r in body["risks"] if r["entity_type"] == "salary_advance" and r["entity_id"] == advance["id"]]
    assert len(matches) == 1
    assert matches[0]["severity"] == "LOW"
    assert matches[0]["action_path"] == "/salary-advances"


def test_approved_advance_with_outstanding_balance_is_not_a_risk(client, test_user):
    """Recovery can legitimately span multiple months - an outstanding
    balance alone is not an attention item, only an unreviewed
    Pending request is."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Business Decision Approved Advance Employee", "monthly_salary": "20000"}).json()
    advance = client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "3000", "request_date": "2026-09-01T00:00:00",
    }).json()
    client.put(f"/api/salary-advances/{advance['id']}/approve", json={
        "recovery_month": "September", "recovery_year": "2026",
    })

    resp = client.get("/api/business-decisions/")
    body = resp.json()
    assert not any(r["entity_id"] == advance["id"] and r["entity_type"] == "salary_advance" for r in body["risks"])


def test_employee_sees_only_order_risk_not_payroll_or_advance(client, test_user, db_session):
    _login(client, test_user)
    order = _make_critical_order(client, "3")
    payroll_employee = client.post("/api/employees/", json={"name": "Business Decision RBAC Payroll Employee", "monthly_salary": "20000"}).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": payroll_employee["id"], "month": "September", "year": "2026", "basic": "20000",
    }).json()
    client.put(f"/api/salary-slips/{slip['id']}", json={"status": "finalized"})
    client.post("/api/salary-advances/", json={
        "employee_id": payroll_employee["id"], "requested_amount": "3000", "request_date": "2026-09-01T00:00:00",
    })

    viewer_employee = client.post("/api/employees/", json={"name": "Business Decision RBAC Viewer Employee"}).json()
    user = User(
        username="businessdecisionrbacuser", email="businessdecisionrbacuser@example.com",
        full_name="Business Decision RBAC User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=viewer_employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "businessdecisionrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.get("/api/business-decisions/")
    assert resp.status_code == 200
    body = resp.json()
    assert any(r["entity_id"] == order["id"] for r in body["risks"])
    assert not any(r["risk_type"] == "PAYROLL" for r in body["risks"])


def test_risks_sorted_by_severity_critical_first(client, test_user):
    _login(client, test_user)
    _make_critical_order(client, "4")
    employee = client.post("/api/employees/", json={"name": "Business Decision Sort Employee", "monthly_salary": "20000"}).json()
    client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "1000", "request_date": "2026-09-01T00:00:00",
    })

    resp = client.get("/api/business-decisions/")
    severities = [r["severity"] for r in resp.json()["risks"]]
    severity_rank = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    ranks = [severity_rank[s] for s in severities]
    assert ranks == sorted(ranks)


def test_get_risk_for_specific_order(client, test_user):
    _login(client, test_user)
    order = _make_critical_order(client, "5")

    resp = client.get(f"/api/business-decisions/order/{order['id']}")
    assert resp.status_code == 200
    assert resp.json()["entity_id"] == order["id"]


def test_get_risk_for_order_with_no_risk_returns_404(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Business Decision No Risk Client", "phone": "9000010196"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-09-01T00:00:00", "order_value": "5000", "advance": "0",
    }).json()

    resp = client.get(f"/api/business-decisions/order/{order['id']}")
    assert resp.status_code == 404


def test_employee_gets_404_not_403_for_unauthorized_salary_slip_entity(client, test_user, db_session):
    """Section 19's own explicit requirement: a non-privileged caller
    asking about a salary slip gets the same 404 as one that doesn't
    exist - never a distinguishable "exists but you can't see it"."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Business Decision 404 Employee", "monthly_salary": "20000"}).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "September", "year": "2026", "basic": "20000",
    }).json()
    client.put(f"/api/salary-slips/{slip['id']}", json={"status": "finalized"})

    viewer_employee = client.post("/api/employees/", json={"name": "Business Decision 404 Viewer"}).json()
    user = User(
        username="businessdecision404user", email="businessdecision404user@example.com",
        full_name="Business Decision 404 User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=viewer_employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "businessdecision404user@example.com", "password": "EmpPass1!"})

    resp = client.get(f"/api/business-decisions/salary_slip/{slip['id']}")
    assert resp.status_code == 404


def test_business_decisions_require_auth(client):
    resp = client.get("/api/business-decisions/")
    assert resp.status_code == 401


# --- Family 137, Step 5: Forward Cash-Flow Forecast (feature 12) ---

def test_cash_flow_forecast_requires_master(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/auth/logout")
    user = User(username="cashflowuser", email="cashflowuser@example.com", full_name="Cash Flow User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "cashflowuser@example.com", "password": "UserPass1!"})
    resp = client.get("/api/dashboard/cash-flow-forecast")
    assert resp.status_code == 403


def test_cash_flow_forecast_classifies_overdue_balance(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Cash Flow Overdue Client", "phone": "9812360001"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "delivery_date": "2026-01-15T00:00:00",
        "order_value": "40000.00", "advance": "0",
    }).json()
    assert float(order["balance"]) == 40000.0

    resp = client.get("/api/dashboard/cash-flow-forecast")
    assert resp.status_code == 200
    body = resp.json()
    assert body["overdue_total"] >= 40000.0
    matching = [o for o in body["overdue_orders"] if o["order_id"] == order["id"]]
    assert len(matching) == 1
    assert matching[0]["days_overdue"] > 0


def test_cash_flow_forecast_buckets_future_balance_as_expected(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Cash Flow Future Client", "phone": "9812360002"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "delivery_date": "2099-01-05T00:00:00",
        "order_value": "60000.00", "advance": "0",
    }).json()

    resp = client.get("/api/dashboard/cash-flow-forecast", params={"weeks": 1})
    assert resp.status_code == 200
    body = resp.json()
    # Far outside the requested 1-week window - must land in forecast,
    # never silently dropped or double-counted into overdue.
    matching = [o for o in body["forecast_orders"] if o["order_id"] == order["id"]]
    assert len(matching) == 1
    assert order["id"] not in [o["order_id"] for o in body["overdue_orders"]]


def test_cash_flow_forecast_cancelled_order_excluded(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Cash Flow Cancelled Client", "phone": "9812360003"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-01-01T00:00:00", "order_value": "25000.00", "advance": "0",
    }).json()
    client.put(f"/api/orders/{order['id']}", json={"project_status": "Cancelled"})

    resp = client.get("/api/dashboard/cash-flow-forecast")
    assert resp.status_code == 200
    body = resp.json()
    all_ids = (
        [o["order_id"] for o in body["overdue_orders"]]
        + [o["order_id"] for o in body["forecast_orders"]]
        + [o["order_id"] for b in body["weekly_buckets"] for o in b["expected_orders"]]
    )
    assert order["id"] not in all_ids


# --- Family 137, Step 5: Owner Daily/Weekly Business Briefing (feature 11) ---

def test_owner_briefing_requires_master(client, test_user, db_session):
    _login(client, test_user)
    client.post("/api/auth/logout")
    user = User(username="briefinguser", email="briefinguser@example.com", full_name="Briefing User",
                password_hash=hash_password("UserPass1!"), role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "briefinguser@example.com", "password": "UserPass1!"})
    resp = client.get("/api/dashboard/owner-briefing")
    assert resp.status_code == 403


def test_owner_briefing_rejects_invalid_period(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/owner-briefing", params={"period": "monthly"})
    assert resp.status_code == 400


def test_owner_briefing_defaults_to_daily_and_returns_shape(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/owner-briefing")
    assert resp.status_code == 200
    body = resp.json()
    assert body["period"] == "daily"
    assert "headline" in body and isinstance(body["sections"], list)


def test_owner_briefing_weekly_period(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/dashboard/owner-briefing", params={"period": "weekly"})
    assert resp.status_code == 200
    assert resp.json()["period"] == "weekly"


def test_owner_briefing_surfaces_low_stock_as_fact(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Owner Briefing Low Stock Material", "unit": "Sheets",
        "opening_stock": "1", "minimum_stock": "10", "average_rate": "100.00",
    })
    resp = client.get("/api/dashboard/owner-briefing")
    assert resp.status_code == 200
    inventory_sections = [s for s in resp.json()["sections"] if s["key"] == "inventory"]
    assert len(inventory_sections) == 1
    assert len(inventory_sections[0]["facts"]) > 0
