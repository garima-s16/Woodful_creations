"""Tests for two new chatbot capabilities from the multilingual/broken-
text brief: (1) resolving a client name to their most recent order
("patel ka payment?", "order sanket" from the brief's own examples),
and (2) generating an Excel export through chat, reusing the SAME
authorized export service - never a separate AI-only route."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_client_order_query_hindi_possessive(client, test_user):
    """"patel ka payment?" - the brief's own example."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Patel"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "50000", "advance": "20000",
    }).json()

    resp = client.post("/api/chat/", json={"message": "patel ka payment?"})
    assert resp.status_code == 200
    assert order["order_code"] in resp.json()["response"]


def test_client_order_query_reversed_word_order(client, test_user):
    """"order sanket" - the brief's other explicit example."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Sanket"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "30000", "advance": "0",
    }).json()

    resp = client.post("/api/chat/", json={"message": "order sanket"})
    assert order["order_code"] in resp.json()["response"]


def test_client_order_query_asks_when_ambiguous(client, test_user):
    """Never confidently guess when multiple clients match - the
    brief's own explicit instruction."""
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Ashu Kumar"})
    client.post("/api/clients/", json={"name": "Ashu Singh"})

    resp = client.post("/api/chat/", json={"message": "ashu ka order"})
    assert "which one" in resp.json()["response"].lower()


def test_client_order_query_employee_sees_no_payment_figure(client, test_user, db_session):
    """RBAC must apply the same way it does everywhere else - an
    employee resolving a client's order must not see the balance."""
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Mahek"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "40000", "advance": "0",
    })
    employee = client.post("/api/employees/", json={"name": "Client Query RBAC Employee"}).json()
    user = User(
        username="clientqueryrbacuser", email="clientqueryrbacuser@example.com",
        full_name="Client Query RBAC User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "clientqueryrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": "mahek ka payment"})
    assert "Rs" not in resp.json()["response"]
    assert "pending" not in resp.json()["response"].lower()


def test_excel_via_chat_generates_download_link(client, test_user):
    """"pankaj ki August attendance Excel bana do" - resolves employee
    and month, returns a link to the real export endpoint."""
    _login(client, test_user)
    employee_id = client.post("/api/employees/", json={"name": "Pankaj"}).json()["id"]

    resp = client.post("/api/chat/", json={"message": "pankaj ki august attendance excel bana do"})
    assert resp.status_code == 200
    data = resp.json()
    action = data["records"][0]["actions"][0]
    assert action["download_path"].startswith("attendance.xlsx?")
    assert f"employee_id={employee_id}" in action["download_path"]
    assert "month=August" in action["download_path"]


def test_excel_via_chat_requires_master(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "Excel Chat RBAC Employee"}).json()
    user = User(
        username="excelchatrbacuser", email="excelchatrbacuser@example.com",
        full_name="Excel Chat RBAC User", password_hash=hash_password("EmpPass1!"),
        role="user", employee_id=employee["id"], is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "excelchatrbacuser@example.com", "password": "EmpPass1!"})

    resp = client.post("/api/chat/", json={"message": "excel chat rbac employee ka august attendance excel bana do"})
    assert "master account" in resp.json()["response"].lower()


def test_excel_via_chat_asks_when_employee_not_found(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "totally unknown person ka august attendance excel bana do"})
    assert resp.json()["records"] == []
