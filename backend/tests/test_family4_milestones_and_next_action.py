"""Tests for Family 4 (Project Management): the new milestones
model (a genuine gap - lightweight, distinct from Order.project_status
which already tracks the detailed production phase), and the
"recommend next action" chatbot handler, which replicates the exact
"Next Action" definition already established on OrderDetailPage
(earliest not-DONE task by date) rather than a new one."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_create_milestone(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Milestone Test Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    }).json()
    resp = client.post("/api/milestones/", json={
        "order_id": order["id"], "name": "Design approval", "target_date": "2026-09-01T00:00:00",
    })
    assert resp.status_code == 201
    assert resp.json()["completed_date"] is None


def test_milestone_creation_requires_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Milestone Permission Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "5000", "advance": "0",
    }).json()
    employee = client.post("/api/employees/", json={"name": "Milestone Permission Employee"}).json()
    user = User(
        username="milestonepermuser", email="milestonepermuser@example.com",
        full_name="Milestone Perm User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "milestonepermuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/milestones/", json={"order_id": order["id"], "name": "Should be blocked"})
    assert resp.status_code == 403


def test_milestone_can_be_marked_complete(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Milestone Complete Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "8000", "advance": "0",
    }).json()
    milestone = client.post("/api/milestones/", json={"order_id": order["id"], "name": "Material delivery"}).json()

    resp = client.put(f"/api/milestones/{milestone['id']}", json={"completed_date": "2026-08-20T00:00:00"})
    assert resp.status_code == 200
    assert resp.json()["completed_date"] is not None


def test_milestones_list_filters_by_order(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Milestone Filter Client"}).json()["id"]
    order_a = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "1000", "advance": "0",
    }).json()
    order_b = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "2000", "advance": "0",
    }).json()
    client.post("/api/milestones/", json={"order_id": order_a["id"], "name": "Milestone for A"})
    client.post("/api/milestones/", json={"order_id": order_b["id"], "name": "Milestone for B"})

    resp = client.get("/api/milestones/", params={"order_id": order_a["id"]})
    names = [m["name"] for m in resp.json()]
    assert "Milestone for A" in names
    assert "Milestone for B" not in names


def test_chatbot_next_action_via_client_name(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Mahek"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "5000", "advance": "0",
    }).json()
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-25T00:00:00", "task_description": "Later task", "order_id": order["id"],
    })
    client.post("/api/daily-tasks/", json={
        "date": "2026-08-20T00:00:00", "task_description": "Earlier task", "order_id": order["id"],
    })

    resp = client.post("/api/chat/", json={"message": "what's next on mahek"})
    assert resp.status_code == 200
    assert "Earlier task" in resp.json()["response"]


def test_chatbot_next_action_flags_blocked_task(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Shruti"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "5000", "advance": "0",
    }).json()
    task = client.post("/api/daily-tasks/", json={
        "date": "2026-08-20T00:00:00", "task_description": "Blocked task", "order_id": order["id"],
    }).json()
    client.put(f"/api/daily-tasks/{task['id']}", json={"status": "BLOCKED", "delay_reason": "Waiting on material"})

    resp = client.post("/api/chat/", json={"message": "recommend next action for shruti"})
    assert "BLOCKED" in resp.json()["response"]
    assert "Waiting on material" in resp.json()["response"]


def test_chatbot_next_action_no_open_tasks(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Behlool"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "3000", "advance": "0",
    })
    resp = client.post("/api/chat/", json={"message": "what's next on behlool"})
    assert resp.status_code == 200
    assert "no open tasks" in resp.json()["response"].lower()
