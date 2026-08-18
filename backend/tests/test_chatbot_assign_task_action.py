"""Tests for the chatbot's task-assignment action - creates a real
task via the same fields/notification path the real POST endpoint
uses, not a second creation mechanism."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_assign_task_creates_real_task(client, test_user):
    _login(client, test_user)
    client.post("/api/employees/", json={"name": "Pankaj Chat Assign"})

    resp = client.post("/api/chat/", json={"message": "assign wardrobe cutting to pankaj"})
    assert resp.status_code == 200
    assert "assigned" in resp.json()["response"].lower()
    assert resp.json()["records"]

    tasks = client.get("/api/daily-tasks/").json()
    match = next((t for t in tasks if "wardrobe cutting" in t["task_description"].lower()), None)
    assert match is not None
    assert match["status"] == "TO DO"


def test_assign_task_strips_leading_article(client, test_user):
    _login(client, test_user)
    client.post("/api/employees/", json={"name": "Ravi Chat Assign"})

    client.post("/api/chat/", json={"message": "assign the panel sanding to ravi"})
    tasks = client.get("/api/daily-tasks/").json()
    match = next((t for t in tasks if "panel sanding" in t["task_description"].lower()), None)
    assert match is not None
    assert not match["task_description"].lower().startswith("the ")


def test_assign_task_unknown_employee_gives_clear_message(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "assign cutting to nonexistentperson"})
    assert "couldn't find" in resp.json()["response"].lower()


def test_assign_task_links_order_from_context(client, test_user):
    _login(client, test_user)
    client.post("/api/employees/", json={"name": "Shweta Chat Assign"})
    client_id = client.post("/api/clients/", json={"name": "Chat Assign Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "20000", "advance": "0",
    }).json()

    client.post("/api/chat/", json={
        "message": "assign edge banding to shweta",
        "context": {"order_id": order["id"]},
    })
    tasks = client.get("/api/daily-tasks/").json()
    match = next((t for t in tasks if "edge banding" in t["task_description"].lower()), None)
    assert match is not None
    assert match["order_id"] == order["id"]


def test_query_who_is_assigned_does_not_falsely_trigger_assignment(client, test_user):
    """Regression guard - 'assigned to' (past participle query) must
    not be mistaken for 'assign ... to' (imperative action)."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "what tasks are assigned to ravi"})
    assert "assigned \"" not in resp.json()["response"].lower()
