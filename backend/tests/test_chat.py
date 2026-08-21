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
    client_id = client.post("/api/clients/", json={"name": "Chat Test Client", "phone": "9000010012"}).json()["id"]
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


def test_chat_payment_with_amount_and_mode_in_one_message_proposes_immediately(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chat Payment Client", "phone": "9000010013"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "50000.00", "advance": "0",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "record a payment of 15000 via bank transfer for this order",
        "context": {"order_id": order["id"]},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["proposed_action"] is not None
    assert body["proposed_action"]["action_type"] == "record_payment"
    assert body["proposed_action"]["payload"]["order_id"] == order["id"]
    assert body["proposed_action"]["payload"]["amount"] == "15000"
    assert body["proposed_action"]["payload"]["payment_mode"] == "Bank"
    assert body["clarification"] is None

    # The proposal must NOT have actually created a payment.
    payments = client.get("/api/payments/", params={"order_id": order["id"]}).json()
    assert len(payments) == 0


def test_chat_payment_without_mode_asks_instead_of_defaulting_to_cash(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chat Payment Client 4", "phone": "9000010014"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "40000.00", "advance": "0",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "record a payment of 15000 for this order",
        "context": {"order_id": order["id"]},
    })
    assert resp.status_code == 200
    body = resp.json()
    # Must NOT silently pick a mode - must ask instead.
    assert body["proposed_action"] is None
    assert "payment mode" in body["response"].lower()
    assert body["clarification"] is not None
    assert body["clarification"]["type"] == "record_payment"
    assert body["clarification"]["amount"] == "15000"


def test_chat_completes_payment_across_two_turns(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chat Payment Client 5", "phone": "9000010015"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "60000.00", "advance": "0",
    }).json()

    first = client.post("/api/chat/", json={
        "message": "record a payment of 20000 for this order",
        "context": {"order_id": order["id"]},
    }).json()
    assert first["proposed_action"] is None
    pending = first["clarification"]
    assert pending is not None

    # Second turn: the frontend echoes back `pending` as context.pending,
    # the user answers with just the mode.
    second = client.post("/api/chat/", json={
        "message": "UPI",
        "context": {"order_id": order["id"], "pending": pending},
    }).json()
    assert second["clarification"] is None
    assert second["proposed_action"] is not None
    assert second["proposed_action"]["payload"]["amount"] == "20000"
    assert second["proposed_action"]["payload"]["payment_mode"] == "UPI"

    # Still not created until the frontend actually calls the real endpoint.
    payments = client.get("/api/payments/", params={"order_id": order["id"]}).json()
    assert len(payments) == 0


def test_chat_continues_asking_if_second_turn_still_has_no_mode(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chat Payment Client 6", "phone": "9000010016"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "25000.00", "advance": "0",
    }).json()

    first = client.post("/api/chat/", json={
        "message": "record a payment of 5000 for this order",
        "context": {"order_id": order["id"]},
    }).json()
    pending = first["clarification"]

    second = client.post("/api/chat/", json={
        "message": "not sure yet",
        "context": {"order_id": order["id"], "pending": pending},
    }).json()
    assert second["proposed_action"] is None
    assert second["clarification"] is not None
    assert "payment mode" in second["response"].lower()


def test_chat_payment_proposal_without_amount_asks_for_one(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chat Payment Client 2", "phone": "9000010017"}).json()["id"]
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
    order_client_id = client.post("/api/clients/", json={"name": "Chat Payment Client 3", "phone": "9000010018"}).json()["id"]
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
    assert "master account" in body["response"].lower()


def test_low_stock_returns_clickable_records(client, test_user):
    _login(client, test_user)
    material = client.post("/api/materials/", json={
        "name": "Chat Records Low Stock Material", "unit": "Sheets", "opening_stock": 1, "minimum_stock": 10,
    }).json()

    resp = client.post("/api/chat/", json={"message": "check low stock"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["records"]) > 0
    match = next((r for r in body["records"] if r["label"] == "Chat Records Low Stock Material"), None)
    assert match is not None
    assert match["type"] == "Material"
    assert match["path"] == f"/materials/{material['id']}"


def test_outstanding_payments_returns_clickable_order_records(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Chat Records Payment Client", "phone": "9000010019"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-01T00:00:00", "order_value": "50000.00", "advance": "10000.00",
    }).json()

    resp = client.post("/api/chat/", json={"message": "which orders have outstanding payments"})
    assert resp.status_code == 200
    body = resp.json()
    match = next((r for r in body["records"] if r["label"] == order["order_code"]), None)
    assert match is not None
    assert match["type"] == "Order"
    assert match["path"] == f"/orders/{order['id']}"
    assert "Chat Records Payment Client" in match["sublabel"]


def test_outstanding_payments_records_respect_rbac(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    limited_user = User(
        username="chatrecordslimited", email="chatrecordslimited@example.com", full_name="Limited User",
        password_hash=hash_password("LimitedPass1!"), role="user", is_active=True,
    )
    db_session.add(limited_user)
    db_session.commit()

    resp = client.post("/api/auth/login", json={"identifier": "chatrecordslimited@example.com", "password": "LimitedPass1!"})
    assert resp.status_code == 200

    chat_resp = client.post("/api/chat/", json={"message": "show me pending payments"})
    body = chat_resp.json()
    assert body["records"] == []
    assert "master accounts only" in body["response"].lower()


def test_no_low_stock_returns_no_records(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "check low stock"})
    body = resp.json()
    # Even with zero matches, the response must be well-formed - not an error.
    assert isinstance(body["records"], list)
