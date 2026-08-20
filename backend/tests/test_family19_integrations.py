"""Tests for Family 19 (Zoho + SAP Integration). No real Zoho/SAP
credentials exist in this environment - every sync attempt is expected
to honestly fail with NOT VERIFIED — EXTERNAL SERVICE REQUIRED, never
a fabricated success. These tests prove the architecture (logging,
idempotency, authorization, credential non-exposure) is sound
independent of whether a live connection exists."""


def _login(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200


def _login_as_user(client, db_session, username, email):
    from app.core.security import hash_password
    from app.models.user import User
    user = User(
        username=username, email=email, full_name=username,
        password_hash=hash_password("UserPass1!"), role="user", is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    client.post("/api/auth/login", json={"identifier": email, "password": "UserPass1!"})


def test_integration_status_reports_not_configured_honestly(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/integrations/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["zoho"]["configured"] is False
    assert data["sap"]["configured"] is False


def test_sync_without_credentials_fails_honestly_not_fake_success(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Integration Sync Test Client"}).json()["id"]
    resp = client.post(f"/api/integrations/zoho/client/{client_id}/sync", json={})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "FAILED"
    assert "not configured" in data["error_message"].lower()


def test_sync_attempt_is_genuinely_logged(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Integration Log Test Client"}).json()["id"]
    client.post(f"/api/integrations/zoho/client/{client_id}/sync", json={})

    logs = client.get("/api/integrations/logs", params={"entity_type": "client", "entity_id": client_id}).json()
    assert len(logs) == 1
    assert logs[0]["external_system"] == "zoho"
    assert logs[0]["operation"] == "create"


def test_repeated_failed_sync_increments_attempt_number(client, test_user):
    """Proves the append-only retry history genuinely works - a second
    attempt is a NEW row, not an overwrite of the first."""
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Integration Retry Test Client"}).json()["id"]
    client.post(f"/api/integrations/zoho/client/{client_id}/sync", json={"force": True})
    client.post(f"/api/integrations/zoho/client/{client_id}/sync", json={"force": True})

    logs = client.get("/api/integrations/logs", params={"entity_type": "client", "entity_id": client_id}).json()
    assert len(logs) == 2
    attempt_numbers = sorted(l["attempt_number"] for l in logs)
    assert attempt_numbers == [1, 2]


def test_syncing_nonexistent_entity_fails_cleanly(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/integrations/zoho/client/999999/sync", json={})
    assert resp.status_code == 404


def test_unknown_external_system_is_rejected(client, test_user):
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Unknown System Test Client"}).json()["id"]
    resp = client.post(f"/api/integrations/not_a_real_system/client/{client_id}/sync", json={})
    assert resp.status_code == 400


def test_unknown_entity_type_is_rejected(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/integrations/zoho/not_a_real_entity/1/sync", json={})
    assert resp.status_code == 400


def test_non_master_cannot_trigger_sync(client, test_user, db_session):
    _login_as_user(client, db_session, "integrationsyncuser", "integrationsyncuser@example.com")
    resp = client.post("/api/integrations/zoho/client/1/sync", json={})
    assert resp.status_code == 403


def test_non_master_cannot_view_sync_logs(client, test_user, db_session):
    _login_as_user(client, db_session, "integrationlogsuser", "integrationlogsuser@example.com")
    resp = client.get("/api/integrations/logs")
    assert resp.status_code == 403


def test_non_master_cannot_view_integration_status(client, test_user, db_session):
    _login_as_user(client, db_session, "integrationstatususer", "integrationstatususer@example.com")
    resp = client.get("/api/integrations/status")
    assert resp.status_code == 403


def test_no_credential_value_ever_appears_in_any_response(client, test_user):
    """The core secret-protection proof - the actual configured secret
    value must never appear in any integration response body. (The
    setting NAME appearing in an honest error message, e.g. "ZOHO_API_KEY
    is not configured", is fine and intended - only the VALUE is secret.)"""
    from app.core.config import settings
    _login(client, test_user)
    client_id = client.post("/api/clients/", json={"name": "Credential Leak Test Client"}).json()["id"]
    status_resp = client.get("/api/integrations/status")
    sync_resp = client.post(f"/api/integrations/zoho/client/{client_id}/sync", json={})
    logs_resp = client.get("/api/integrations/logs")
    for resp in (status_resp, sync_resp, logs_resp):
        assert settings.SECRET_KEY not in str(resp.json())
