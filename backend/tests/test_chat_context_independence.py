"""Regression tests proving the assistant answers ANY question correctly
regardless of what page/context it was opened from - e.g. opened from a
Supplier page, "today's tasks" or "my leaves" must still work exactly as
if asked from the dashboard. Context should only ADD capability (answering
"this supplier"-style questions), never restrict what else can be asked."""
from app.core.security import hash_password
from app.models.user import User


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_task_question_works_with_unrelated_supplier_context(client, test_user, db_session):
    """The user's exact reported scenario: chatbot opened from a Supplier
    page, user asks about their tasks - must not be blocked or confused
    by the supplier context."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Context Independence Supplier"}).json()
    employee = client.post("/api/employees/", json={
        "name": "Context Independence Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee["id"], "task_description": "Cross-context test task",
    }).json()
    linked_user = User(
        username="contextindepuser", email="contextindepuser@example.com", full_name="Context Independence User",
        password_hash=hash_password("ContextPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(linked_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "contextindepuser@example.com", "password": "ContextPass1!"})
    assert resp.status_code == 200

    # Context says "I'm on the supplier page" - message asks about tasks.
    chat_resp = client.post("/api/chat/", json={
        "message": "Show my tasks", "context": {"supplier_id": supplier["id"]},
    })
    assert chat_resp.status_code == 200
    paths = [r["path"] for r in chat_resp.json()["records"]]
    assert f"/daily-tasks/{task['id']}" in paths


def test_leave_question_works_with_unrelated_material_context(client, test_user, db_session):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Context Independence Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 1,
    }).json()
    employee = client.post("/api/employees/", json={
        "name": "Leave Context Employee", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    leave = client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "CL",
        "start_date": "2026-08-20T00:00:00", "end_date": "2026-08-20T00:00:00", "reason": "Personal",
    }).json()
    linked_user = User(
        username="leavecontextuser", email="leavecontextuser@example.com", full_name="Leave Context User",
        password_hash=hash_password("ContextPass1!"), role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(linked_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "leavecontextuser@example.com", "password": "ContextPass1!"})
    assert resp.status_code == 200

    # Context says "I'm on the material page" - message asks about leaves.
    chat_resp = client.post("/api/chat/", json={
        "message": "What are my leaves?", "context": {"material_id": material["id"]},
    })
    assert chat_resp.status_code == 200
    assert "1 leave record" in chat_resp.json()["response"]


def test_leaves_found_by_employee_name(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Ramesh", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    client.post("/api/leaves/", json={
        "employee_id": employee["id"], "leave_type": "SL",
        "start_date": "2026-09-01T00:00:00", "end_date": "2026-09-02T00:00:00", "reason": "Sick",
    })

    resp = client.post("/api/chat/", json={"message": "Show Ramesh's leaves"})
    assert resp.status_code == 200
    assert len(resp.json()["records"]) == 1
    assert resp.json()["records"][0]["type"] == "Leave"


def test_supplier_context_answer_is_real_not_fabricated(client, test_user):
    """Confirms the new supplier-context answer uses only real purchase
    data - no invented reliability scores or made-up metrics."""
    _login(client, test_user)
    supplier = client.post("/api/suppliers/", json={"name": "Real Data Supplier"}).json()

    resp = client.post("/api/chat/", json={
        "message": "Tell me about this supplier", "context": {"supplier_id": supplier["id"]},
    })
    assert resp.status_code == 200
    assert "0 purchases" in resp.json()["response"]


def test_unlinked_account_asking_about_leaves_gets_clear_message(client, test_user, db_session):
    _login(client, test_user)
    unlinked = User(
        username="unlinkedleaveuser", email="unlinkedleaveuser@example.com", full_name="Unlinked",
        password_hash=hash_password("ContextPass1!"), role="user", employee_id=None, is_active=True,
    )
    db_session.add(unlinked)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "unlinkedleaveuser@example.com", "password": "ContextPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={"message": "Show my leaves"})
    assert "not linked" in chat_resp.json()["response"].lower()
