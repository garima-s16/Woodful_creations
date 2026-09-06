"""Tests for /api/business-decisions/* (Family P0.49/P0.51). Reuses
compute_order_health (never a second risk calculation) and real
SalarySlip/SalaryAdvance data - master-only for payroll signals,
employees see only operational (order) risk."""
from datetime import datetime, timedelta

from app.platform.security.security import hash_password
from app.modules.auth.models import User
from tests.helpers import _login


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
