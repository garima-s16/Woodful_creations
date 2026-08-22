"""Client Master Patch 101.1, Part 3: the chatbot must never create,
edit, delete, or merge a Client. Verified two ways:

1. Static/architectural: "create_client" (or any client-write action
   type) must not exist anywhere the AI/chat/agent layer could reach -
   neither as a ProposedAction the backend can construct, nor as an
   executor the frontend could run even if one were somehow proposed.
2. Behavioral: sending the chatbot messages that read like a client-
   creation request must never result in a new Client row, regardless
   of role - the message may be answered conversationally, but nothing
   gets written.
"""
import re

from app.models.client import Client


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


# ---------------------------------------------------------------------
# Static: no client-write action type anywhere in the backend AI layer
# ---------------------------------------------------------------------

def test_chat_service_never_constructs_a_client_row():
    """The chat/agent layer must never instantiate Client(...) directly
    - all client data access must go through query/read paths, never a
    write. Checked at the source level, not just by behavior, since a
    behavioral test can't prove a capability doesn't exist for inputs
    it didn't happen to try."""
    import app.services.chat_service as chat_service
    import app.services.agent_service as agent_service
    import inspect

    for module in (chat_service, agent_service):
        source = inspect.getsource(module)
        assert not re.search(r"\bClient\s*\(", source), (
            f"{module.__name__} must never construct a Client(...) row directly"
        )
        assert "create_client" not in source
        assert "update_client" not in source
        assert "delete_client" not in source
        assert "merge_client" not in source


def test_chat_service_never_proposes_a_client_write_action_type():
    """Every ProposedAction the chat service can construct anywhere in
    its source must use one of the known-safe, already-reviewed action
    types - not a client-mutating one. This is intentionally a broad
    sweep of the whole module's ProposedAction(...) call sites, not a
    single code path, so a new client-write action added anywhere in
    the file would fail this test."""
    import app.services.chat_service as chat_service
    import inspect

    source = inspect.getsource(chat_service)
    action_types = re.findall(r'action_type\s*=\s*"([^"]+)"', source)
    assert action_types, "expected to find at least the known proposable action types"
    forbidden = {"create_client", "update_client", "delete_client", "merge_client", "edit_client"}
    assert not (set(action_types) & forbidden), f"chat_service proposes a forbidden client-write action: {action_types}"


# ---------------------------------------------------------------------
# Behavioral: chatbot messages never create a client, for any role
# ---------------------------------------------------------------------

CLIENT_CREATION_PHRASINGS = [
    "add client Ramesh 9812345670",
    "create a new client named Ramesh",
    "register client Ramesh phone 9812345670",
    "add a new client Ramesh Kumar 9812345670 ramesh@example.com",
]


def test_chatbot_cannot_create_client_master(client, test_user, db_session):
    """Also verifies no OTHER entity gets silently created instead - a
    real, shipped bug: "add client Ramesh 9812345670" was matched by
    the material-add parser (which claimed any message starting with
    "add ", with no check on what was actually being added) and
    proposed creating a Material named "client Ramesh 9812345670".
    Asserting only Client.count() stayed the same would NOT have
    caught that regression, since the bug never touched the Client
    table at all - it silently created a different kind of record."""
    from app.models.material import Material

    _login(client, test_user)
    before_clients = db_session.query(Client).count()
    before_materials = db_session.query(Material).count()
    for message in CLIENT_CREATION_PHRASINGS:
        resp = client.post("/api/chat/", json={"message": message})
        assert resp.status_code == 200
        body = resp.json()
        # Whatever the chatbot said, it must never have proposed a
        # client-creation action, NOR any other entity's create action -
        # a client-creation request must resolve to CLIENT or nothing,
        # never silently reinterpreted as a different entity type.
        if body.get("proposed_action"):
            assert body["proposed_action"]["action_type"] not in (
                "create_client", "update_client", "delete_client", "merge_client",
                "create_material", "create_product", "create_supplier", "create_employee",
            ), f"{message!r} wrongly proposed {body['proposed_action']['action_type']!r}"
    after_clients = db_session.query(Client).count()
    after_materials = db_session.query(Material).count()
    assert after_clients == before_clients, "No chat message should ever result in a new Client row"
    assert after_materials == before_materials, (
        "A client-creation request must never result in a new Material row either"
    )


def test_chatbot_cannot_create_client_master_as_user_role(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User

    user = User(username="chatclientrbacuser", email="chatclientrbacuser@example.com",
                full_name="Chat Client RBAC User", password_hash=hash_password("UserPass1!"),
                role="user", is_active=True)
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": "chatclientrbacuser@example.com", "password": "UserPass1!"})

    before = db_session.query(Client).count()
    resp = client.post("/api/chat/", json={"message": "add client Ramesh 9812345670"})
    assert resp.status_code == 200
    after = db_session.query(Client).count()
    assert after == before


def test_chatbot_can_still_read_client_order_history(client, test_user):
    """The read/assist path must remain functional - this patch removes
    write capability, not the whole Client-context feature."""
    _login(client, test_user)
    client.post("/api/clients/", json={"name": "Chat Read Client", "phone": "9812345699"})
    resp = client.post("/api/chat/", json={"message": "chat read client order history"})
    assert resp.status_code == 200
    assert isinstance(resp.json().get("response"), str)


def test_add_client_phrasing_never_parses_as_a_material_command():
    """Dedicated regression test for the exact shipped bug: 'add client
    Ramesh 9812345670' was matched by parse_add_material_command (which
    claimed any message starting with "add ", with no check on the
    object) and proposed creating a Material literally named
    "client Ramesh 9812345670". Calls the parser function directly,
    independent of the full chat pipeline, so this stays a precise,
    fast unit test of the actual root cause rather than only an
    end-to-end behavioral check."""
    from app.services.chat_service import parse_add_material_command

    should_be_none = [
        "add client Ramesh 9812345670",
        "add a new client Ramesh Kumar 9812345670 ramesh@example.com",
        "add customer Priya 9812345671",
        "add supplier ABC Traders",
        "add an employee named Ravi",
    ]
    for message in should_be_none:
        result = parse_add_material_command(message)
        assert result is None, f"{message!r} should not parse as a material command, got {result!r}"

    # Genuine material commands must still work - the fix must not be
    # so broad it breaks the feature it's protecting.
    should_still_parse = [
        "add 5 hdhmr 18mm sheets to my purchase cart",
        "add a new laminate sheet to my material list",
        "add plywood",
    ]
    for message in should_still_parse:
        result = parse_add_material_command(message)
        assert result is not None, f"{message!r} should still parse as a material command"
