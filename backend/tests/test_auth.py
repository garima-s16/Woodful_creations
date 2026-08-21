def test_login_success_sets_cookie_and_omits_token_from_body(client, test_user):
    response = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert response.status_code == 200
    body = response.json()
    assert "token" not in body
    assert body["user"]["email"] == "test@example.com"
    assert "access_token" in response.cookies


def test_login_invalid_credentials(client, test_user):
    response = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "wrong"})
    assert response.status_code == 401


def test_login_wrong_password_message(client, test_user):
    """Message must be generic - not "Incorrect password", which would
    confirm to an attacker that the account exists (account
    enumeration)."""
    response = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_login_by_username_works(client, test_user):
    response = client.post("/api/auth/login", json={"identifier": "testuser", "password": "TestPass123!"})
    assert response.status_code == 200
    assert response.json()["user"]["email"] == "test@example.com"


def test_login_by_email_still_works(client, test_user):
    response = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert response.status_code == 200


def test_login_unknown_email_message(client, test_user):
    """Message must be generic - not "No account found", which would
    confirm to an attacker that the identifier does NOT exist
    (account enumeration)."""
    response = client.post("/api/auth/login", json={"identifier": "nobody@example.com", "password": "whatever"})
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid username or password."


def test_login_does_not_leak_account_existence(client, test_user):
    """The actual security property: a wrong password for a real
    account and a login attempt against a non-existent account must
    be genuinely indistinguishable to the caller - same status code,
    same message, not just similar wording."""
    wrong_password = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "wrong"})
    unknown_account = client.post("/api/auth/login", json={"identifier": "nobody@example.com", "password": "wrong"})
    assert wrong_password.status_code == unknown_account.status_code
    assert wrong_password.json()["detail"] == unknown_account.json()["detail"]


def test_mobile_login_returns_token(client, test_user):
    response = client.post("/api/auth/login/mobile", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert response.status_code == 200
    assert response.json()["token"]


def test_protected_route_without_cookie_is_rejected(client):
    response = client.get("/api/materials/")
    assert response.status_code == 401


def test_login_then_access_me(client, test_user):
    login = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert login.status_code == 200
    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "test@example.com"
