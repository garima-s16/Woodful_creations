"""Priority 12: every suggestion the chatbot offers must actually work
when clicked - clicking a suggestion sends its exact text back as a new
message (see ChatWidget.jsx's send(s) on click), so a suggestion that
doesn't independently resolve to a real answer is a broken action, not
just an imprecise one."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _assert_not_generic_fallback(client, message):
    resp = client.post("/api/chat/", json={"message": message})
    assert resp.status_code == 200
    text = resp.json()["response"].lower()
    assert "didn't quite catch" not in text, f"suggestion {message!r} falls through to the generic fallback"


def test_low_stock_suggestions_all_resolve(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Action Integrity Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 10,
    }).json()

    resp = client.post("/api/chat/", json={"message": "check low stock"})
    assert resp.status_code == 200
    for suggestion in resp.json()["suggestions"]:
        _assert_not_generic_fallback(client, suggestion)


def test_material_context_reorder_suggestion_resolves(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Reorder Suggestion Material", "unit": "Sheets", "opening_stock": 5, "minimum_stock": 20,
    }).json()

    resp = client.post("/api/chat/", json={"message": "summarize this material", "context": {"material_id": material["id"]}})
    assert resp.status_code == 200
    for suggestion in resp.json()["suggestions"]:
        chat_resp = client.post("/api/chat/", json={"message": suggestion, "context": {"material_id": material["id"]}})
        assert "didn't quite catch" not in chat_resp.json()["response"].lower()


def test_order_context_suggestions_resolve(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Action Integrity Order Client", "phone": "9000010020"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "50000.00", "advance": "0",
    }).json()

    resp = client.post("/api/chat/", json={"message": "summarize this order", "context": {"order_id": order["id"]}})
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert "Record Payment" in suggestions
    # "Record Payment" with order context must trigger the real
    # propose-confirm flow, not fall back to a passive summary.
    payment_resp = client.post("/api/chat/", json={"message": "Record Payment", "context": {"order_id": order["id"]}})
    assert payment_resp.json()["proposed_action"] is None  # no amount given yet
    assert "amount" in payment_resp.json()["response"].lower() or "how much" in payment_resp.json()["response"].lower()


def test_employee_context_suggestion_actually_finds_their_tasks(client, test_user):
    """Regression test for the specific bug found in this audit: the
    old "Assign Task"/"Record Attendance" suggestions fell through to
    the generic fallback or a misleading passive summary. The
    replacement must genuinely resolve to that employee's real tasks."""
    _login(client, test_user)
    employee = client.post("/api/employees/", json={
        "name": "Rajesh Kumar", "monthly_salary": "20000", "daily_wage": "800",
    }).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-13T00:00:00", "employee_id": employee["id"], "task_description": "Action integrity test task",
    }).json()

    resp = client.post("/api/chat/", json={"message": "summarize this employee", "context": {"employee_id": employee["id"]}})
    assert resp.status_code == 200
    suggestions = resp.json()["suggestions"]
    assert len(suggestions) == 1
    assert "rajesh" in suggestions[0].lower()

    follow_up = client.post("/api/chat/", json={"message": suggestions[0]})
    paths = [r["path"] for r in follow_up.json()["records"]]
    assert f"/daily-tasks/{task['id']}" in paths


def test_payments_summary_suggestions_all_resolve(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Action Integrity Payment Client", "phone": "9000010021"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-13T00:00:00", "order_value": "20000.00", "advance": "5000.00",
    })

    resp = client.post("/api/chat/", json={"message": "show pending payments"})
    assert resp.status_code == 200
    for suggestion in resp.json()["suggestions"]:
        _assert_not_generic_fallback(client, suggestion)
