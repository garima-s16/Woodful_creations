def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_chat_requires_auth(client):
    resp = client.post("/api/chat/", json={"message": "hello"})
    assert resp.status_code == 401


def test_chat_generic_low_stock_question(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "what materials are low on stock?"})
    assert resp.status_code == 200
    assert "response" in resp.json()


def test_chat_contextual_order_summary_uses_real_order(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chat Test Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "project_type": "Dining Table",
        "order_date": "2026-08-01T00:00:00", "order_value": "80000.00", "advance": "20000.00",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "summarize this order",
        "context": {"order_id": order["id"]},
    })
    assert resp.status_code == 200
    text = resp.json()["response"]
    assert order["order_code"] in text
    assert "Dining Table" in text
    assert "Chat Test Client" in text


def test_chat_contextual_reorder_question_uses_real_stock_levels(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Chat Test Plywood", "unit": "Sheets", "opening_stock": 2, "minimum_stock": 10,
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "should I reorder this material?",
        "context": {"material_id": material["id"]},
    })
    assert resp.status_code == 200
    text = resp.json()["response"]
    assert "Yes" in text
    assert "Chat Test Plywood" in text


def test_chat_contextual_falls_back_when_record_missing(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={
        "message": "summarize this order",
        "context": {"order_id": 999999},
    })
    assert resp.status_code == 200
    # No matching order - should not crash, should fall through to a generic answer
    assert "response" in resp.json()


def test_chat_without_context_ignores_this_order_phrasing(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "summarize this order"})
    assert resp.status_code == 200
    assert "response" in resp.json()


def test_chat_proposes_payment_but_does_not_create_it(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chat Payment Client"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "50000.00", "advance": "0",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "record a payment of 15000 for this order",
        "context": {"order_id": order["id"]},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposed_action"] is not None
    assert body["proposed_action"]["action_type"] == "record_payment"
    assert body["proposed_action"]["payload"]["order_id"] == order["id"]
    assert body["proposed_action"]["payload"]["amount"] == "15000"

    # The proposal must NOT have actually created a payment.
    payments = client.get("/api/payments/", params={"order_id": order["id"]}).json()
    assert len(payments) == 0


def test_chat_payment_proposal_without_amount_asks_for_one(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chat Payment Client 2"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "30000.00", "advance": "0",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "record a payment for this order",
        "context": {"order_id": order["id"]},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposed_action"] is None
    assert "amount" in body["response"].lower()


def test_chat_payment_proposal_requires_master_or_manager(client, test_user, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    _login(client, test_user)
    order_client_id = client.post("/api/clients/", json={"name": "Chat Payment Client 3"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": order_client_id, "order_date": "2026-08-01T00:00:00", "order_value": "20000.00", "advance": "0",
    }).json()

    limited_user = User(
        username="limiteduser", email="limited@example.com", full_name="Limited User",
        password_hash=hash_password("LimitedPass1!"), role="user", is_active=True,
    )
    db_session.add(limited_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "limited@example.com", "password": "LimitedPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={
        "message": "record a payment of 5000 for this order",
        "context": {"order_id": order["id"]},
    })
    body = chat_resp.json()
    assert body["proposed_action"] is None
    assert "master or manager" in body["response"].lower()
