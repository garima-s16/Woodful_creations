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
    _login(client, test_user)
    before = db_session.query(Client).count()
    for message in CLIENT_CREATION_PHRASINGS:
        resp = client.post("/api/chat/", json={"message": message})
        assert resp.status_code == 200
        body = resp.json()
        # Whatever the chatbot said, it must never have proposed a
        # client-creation action.
        if body.get("proposed_action"):
            assert body["proposed_action"]["action_type"] not in (
                "create_client", "update_client", "delete_client", "merge_client",
            )
    after = db_session.query(Client).count()
    assert after == before, "No chat message should ever result in a new Client row"


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
