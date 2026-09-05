"""Tests for the /api/agents/ endpoints - a thin, named-agent wrapper
around the same ChatService.process_message pipeline the plain
/api/chat/ endpoint uses (see agent_service.py's own docstring).
Previously merged into test_chatbot.py, which was the wrong home:
/api/agents/ is a genuinely separate route (app/api/routes/agents.py,
prefix /api/agents) from /api/chat/, not a chatbot behavior - grouping
by the real product domain means these get their own file."""
from tests.helpers import _login


def _login_as_user(client, db_session, username, email):
    from app.platform.security.security import hash_password
    from app.modules.auth.models import User
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("UserPass1!"), role="user", is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": email, "password": "UserPass1!"})


def test_list_agents_reports_all_eight(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/agents/")
    assert resp.status_code == 200
    agent_keys = [a["key"] for a in resp.json()["agents"] if a["key"]]
    for expected in ["inventory", "sales", "project", "production", "procurement", "finance_insight", "document", "operations"]:
        assert expected in agent_keys


def test_agent_list_does_not_overclaim_reasoning(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/agents/")
    entries = resp.json()["agents"]
    reasoning_entry = next(e for e in entries if "LLM-based reasoning" in e["description"])
    assert reasoning_entry["status"] == "EXTERNAL-SERVICE DEPENDENT"


def test_unknown_agent_key_is_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/agents/not_a_real_agent/query", json={"message": "hello"})
    assert resp.status_code == 404


def test_inventory_agent_returns_real_grounded_data(client, test_user):
    """The core grounding proof - an agent's answer must reflect an
    actual database record, not a fabricated one."""
    _login(client, test_user)
    client.post("/api/materials/", json={
        "name": "Agent Grounding Test Material", "unit": "Sheets", "opening_stock": "1", "minimum_stock": "10",
    })
    resp = client.post("/api/agents/inventory/query", json={"message": "what material low"})
    assert resp.status_code == 200
    data = resp.json()
    assert any(r.get("label") == "Agent Grounding Test Material" for r in data["records"])


def test_finance_insight_agent_still_enforces_master_only(client, test_user, db_session):
    """The core permission-inheritance proof - the agent route must
    not grant access process_message itself would deny."""
    _login_as_user(client, db_session, "agentfinancepermuser", "agentfinancepermuser@example.com")
    resp = client.post("/api/agents/finance_insight/query", json={"message": "what is our overall profit margin?"})
    assert resp.status_code == 200
    assert "master accounts only" in resp.json()["response"].lower()


def test_agent_route_does_not_grant_extra_privilege_beyond_chat(client, test_user, db_session):
    """Querying the SAME message through the agent route and the plain
    chat route as a non-master user must produce the same refusal -
    proving agent_key carries no elevated privilege of its own."""
    _login_as_user(client, db_session, "agentparityuser", "agentparityuser@example.com")
    chat_resp = client.post("/api/chat/", json={"message": "what is our overall profit margin?"})
    agent_resp = client.post("/api/agents/finance_insight/query", json={"message": "what is our overall profit margin?"})
    assert chat_resp.json()["response"] == agent_resp.json()["response"]


def test_agent_proposed_action_still_requires_confirmation(client, test_user):
    """Reuses the exact same guarantee through the new route -
    an agent must never auto-execute a mutation."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Agent Action Confirm Test Client", "phone": "9000010092"}).json()["id"]
    orders_before = client.get("/api/orders/", params={"client_id": client_id}).json()
    client.post("/api/agents/sales/query", json={
        "message": "create order for agent action confirm test client worth 10000",
    })
    orders_after = client.get("/api/orders/", params={"client_id": client_id}).json()
    assert len(orders_after) == len(orders_before)


def test_agent_query_requires_authentication(client):
    resp = client.post("/api/agents/inventory/query", json={"message": "what material low"})
    assert resp.status_code in (401, 403)
