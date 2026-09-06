"""Direct tests for the 3 chatbot tools added in Family 131:
get_business_attention, get_salary_advance_status, get_overtime_status.
Calls the tool functions directly (db_session) rather than through the
full Gemini stack - each one reuses an existing, already-tested
service function (business_risk_service.get_business_risks,
hr/payroll_service.get_salary_advance_summary/get_overtime_summary),
so this proves the tool wiring itself, not a second calculation."""
from datetime import datetime, timedelta

from tests.helpers import _login
from app.modules.ai.tools import _tool_get_business_attention, _tool_get_salary_advance_status, _tool_get_overtime_status


def test_business_attention_reports_nothing_when_clean(client, test_user, db_session):
    _login(client, test_user)
    text, records = _tool_get_business_attention(db_session, {}, "master")
    assert "Nothing needs attention" in text
    assert records == []


def test_business_attention_reports_a_real_order_risk(client, test_user, db_session):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chatbot Attention Client", "phone": "9000010197"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-07-01T00:00:00", "order_value": "10000", "advance": "0",
        "delivery_date": (datetime.utcnow() - timedelta(days=2)).isoformat(),
    }).json()
    employee = client.post("/api/employees/", json={"name": "Chatbot Attention Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-07-01T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Chatbot critical work", "status": "BLOCKED", "delay_reason": "Waiting for parts",
    })

    text, records = _tool_get_business_attention(db_session, {}, "master")
    assert order["order_code"] in text or any(r["path"] == f"/orders/{order['id']}" for r in records)


def test_business_attention_hides_payroll_from_employee(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Chatbot Attention Payroll Employee", "monthly_salary": "20000"}).json()
    slip = client.post("/api/salary-slips/", json={
        "employee_id": employee["id"], "month": "September", "year": "2026", "basic": "20000",
    }).json()
    client.put(f"/api/salary-slips/{slip['id']}", json={"status": "finalized"})

    text, records = _tool_get_business_attention(db_session, {}, "user")
    assert "payroll" not in text.lower()


def test_salary_advance_status_requires_master(client, test_user, db_session):
    _login(client, test_user)
    text, records = _tool_get_salary_advance_status(db_session, {}, "user")
    assert "do not have permission" in text.lower()


def test_salary_advance_status_reports_real_pending_request(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Chatbot Advance Employee", "monthly_salary": "20000"}).json()
    client.post("/api/salary-advances/", json={
        "employee_id": employee["id"], "requested_amount": "3000", "request_date": "2026-09-01T00:00:00",
    })

    text, records = _tool_get_salary_advance_status(db_session, {}, "master")
    assert "1 request(s) awaiting review" in text


def test_overtime_status_requires_master(client, test_user, db_session):
    _login(client, test_user)
    text, records = _tool_get_overtime_status(db_session, {}, "user")
    assert "do not have permission" in text.lower()


def test_overtime_status_reports_real_recorded_overtime(client, test_user, db_session):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Chatbot Overtime Employee", "monthly_salary": "20000"}).json()
    client.post("/api/attendance/overtime", json={
        "employee_id": employee["id"], "dates": ["2026-09-06T00:00:00"], "hours": "3", "mode": "add",
    })

    text, records = _tool_get_overtime_status(db_session, {"month": "September", "year": "2026"}, "master")
    assert "Chatbot Overtime Employee" in text
    assert "3" in text
    assert len(records) == 1


def test_overtime_status_no_overtime_recorded(client, test_user, db_session):
    _login(client, test_user)
    text, records = _tool_get_overtime_status(db_session, {"month": "January", "year": "2020"}, "master")
    assert "No approved overtime" in text
    assert records == []
