"""Tests for Manus-inspired conversational memory ("usme kya scene
hai" resolving to whatever order/client was just discussed) - a
stateless echo-back mechanism, not server-side conversation storage,
gated on an explicit deictic reference so it never misattributes an
unrelated question to the previous topic."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_response_includes_last_entity_when_context_resolved(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Context Memory Client", "phone": "9000010034"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "40000", "advance": "0",
    }).json()

    resp = client.post("/api/chat/", json={
        "message": "summarize this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    assert resp.status_code == 200
    assert resp.json()["last_entity"] == {"type": "order", "id": order["id"]}


def test_deictic_followup_resolves_to_last_entity(client, test_user):
    """The core scenario - a follow-up message with no page context but
    a deictic word ("usme") should resolve using last_entity echoed
    back from the previous turn."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Deictic Followup Client", "phone": "9000010035"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "55000", "advance": "0",
    }).json()

    first = client.post("/api/chat/", json={
        "message": "tell me about this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    last_entity = first.json()["last_entity"]
    assert last_entity == {"type": "order", "id": order["id"]}

    followup = client.post("/api/chat/", json={
        "message": "usme kya scene hai",
        "context": {"last_entity": last_entity},
    })
    assert followup.status_code == 200
    assert "couldn't find" not in followup.json()["response"].lower()


def test_unrelated_message_does_not_use_last_entity(client, test_user):
    """Without a deictic word, an unrelated question must not be
    misattributed to whatever was discussed previously."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "No Misattribution Client", "phone": "9000010036"}).json()["id"]
    order = client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-20T00:00:00", "order_value": "30000", "advance": "0",
    }).json()

    first = client.post("/api/chat/", json={
        "message": "tell me about this order",
        "context": {"record_type": "order", "record_id": order["id"]},
    })
    last_entity = first.json()["last_entity"]

    # Genuinely unrelated query (no deictic word) carrying the same
    # last_entity - a low-stock question has nothing to do with any
    # order, so this response must not mention the order at all.
    unrelated = client.post("/api/chat/", json={
        "message": "show me low stock",
        "context": {"last_entity": last_entity},
    })
    assert order["order_code"] not in unrelated.json()["response"]
