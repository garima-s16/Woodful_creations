"""Tests for the user's specific reported scenario: "4 sheet add kr
do 12mm ki" must ask which material, never silently add or create
anything. Also serves as a regression guard for a severe tuple-arity
bug found while building this - several chat handlers returned
3-tuples where process_message's 5-tuple contract was expected
(and, in three other cases, I nearly "fixed" handlers that were
actually correct, since they live inside _dispatch's genuine
3-tuple contract instead)."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def test_ambiguous_hindi_add_asks_which_material(client, test_user):
    """The user's exact reported message."""
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "4 sheet add kr do 12mm ki"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["proposed_action"] is None
    assert data["records"] == []
    assert "konsi" in data["response"].lower()


def test_ambiguous_hindi_add_variant_verb_phrasing(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/chat/", json={"message": "5 sheet add karo 6mm ka"})
    assert resp.status_code == 200
    assert resp.json()["proposed_action"] is None


def test_hindi_add_with_real_material_name_is_not_blocked(client, test_user):
    """When a real material IS named, this safeguard must get out of
    the way and let the message fall through normally, rather than
    always ask for clarification regardless of what was said."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "HDHMR", "unit": "Sheets", "opening_stock": "10", "minimum_stock": "5",
    })
    resp = client.post("/api/chat/", json={"message": "4 hdhmr sheet add kr do 12mm ki"})
    # Must NOT be the "konsi wali sheet" clarification, since a real
    # material name is present in the message.
    assert "konsi" not in resp.json()["response"].lower()


def test_chat_endpoint_does_not_500_on_client_order_query(client, test_user):
    """Regression guard for the tuple-arity bug - this code path lives
    inside _dispatch and must return correctly through the real HTTP
    endpoint, not just compile."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "TupleBugRegressionClient"}).json()["id"]
    client.post("/api/orders/", json={
        "client_id": client_id, "order_date": "2026-08-19T00:00:00", "order_value": "10000", "advance": "0",
    })
    resp = client.post("/api/chat/", json={"message": "tuplebugregressionclient ka order"})
    assert resp.status_code == 200


def test_chat_endpoint_does_not_500_on_material_query(client, test_user):
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Tuple Bug Regression Material", "unit": "Sheets", "opening_stock": "5", "minimum_stock": "2",
    })
    resp = client.post("/api/chat/", json={"message": "stock of tuple bug regression material"})
    assert resp.status_code == 200


def test_chat_endpoint_does_not_500_on_excel_via_chat(client, test_user):
    _login(client, test_user)
    client.post("/api/employees/", json={"name": "Tuple Bug Regression Employee"})
    resp = client.post("/api/chat/", json={"message": "tuple bug regression employee ka august attendance excel bana do"})
    assert resp.status_code == 200
