"""Tests for the Manus-inspired order-risk AI workspace - a real
persisted artifact combining only genuinely existing data (linked
tasks, production jobs, materials issued), never a fabricated
materials-shortage figure. Includes the read-time re-redaction
guarantee: a report created by master must not leak payment data to
an employee viewing it later."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_blocking_query_creates_persisted_report(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "AI Workspace Client", "phone": "9000010001"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "60000", "advance": "10000",
    }).json()
    employee = client.post("/api/employees/", json={"name": "AI Workspace Employee"}).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-20T00:00:00", "employee_id": employee["id"], "order_id": order["id"],
        "task_description": "Fit hardware", "status": "BLOCKED", "delay_reason": "Waiting for hinges",
    })

    resp = client.post("/api/chat/", json={
        "message": "what is blocking this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    assert "AT RISK" in resp.json()["response"]
    assert "hinges" in resp.json()["response"].lower()

    reports = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert len(reports) == 1
    assert reports[0]["risk_level"] == "AT_RISK"
    assert reports[0]["findings"]["blocked_tasks"][0]["reason"] == "Waiting for hinges"


def test_order_with_no_blockers_is_on_track(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "AI Workspace On Track Client", "phone": "9000010002"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "20000", "advance": "0",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "what is blocking this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert "ON TRACK" in resp.json()["response"]

    reports = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert reports[0]["risk_level"] == "ON_TRACK"


def test_deictic_followup_triggers_order_risk_check(client, test_user):
    """"usme kya scene hai" style follow-up, using last turn's
    conversational memory mechanism together with this one."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "AI Workspace Deictic Client", "phone": "9000010003"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "35000", "advance": "0",
    }).json()

    first = client.post("/api/chat/", json={
        "message": "tell me about this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    last_entity = first.json()["last_entity"]

    followup = client.post("/api/chat/", json={
        "message": "kya problem hai usme",
        "context": {"last_entity": last_entity},
    })
    reports = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert len(reports) == 1


def test_employee_viewing_master_created_report_does_not_see_payment(client, test_user, db_session):
    """The core security guarantee - re-redaction happens at read
    time based on the CURRENT viewer's role, not the role that
    created the report."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "AI Workspace Redaction Client", "phone": "9000010004"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "50000", "advance": "5000",
    }).json()

    # Master creates the report - findings include pending_payment.
    client.post("/api/chat/", json={
        "message": "what is blocking this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    master_view = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert "pending_payment" in master_view[0]["findings"]

    employee = client.post("/api/employees/", json={"name": "AI Workspace Redaction Employee"}).json()
    user = User(
        username="aiworkspaceredactionuser", email="aiworkspaceredactionuser@example.com",
        full_name="AI Workspace Redaction User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "aiworkspaceredactionuser@example.com", "password": "EmpPass1!"})

    employee_view = client.get(f"/api/orders/{order['id']}/ai-reports").json()
    assert "pending_payment" not in employee_view[0]["findings"]
