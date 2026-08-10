def test_login_success_sets_cookie_and_omits_token_from_body(client, test_user):
    response = client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})

    assert response.status_code == 200
    body = response.json()
    assert "token" not in body  # web login must never expose the JWT to page JS
    assert body["user"]["email"] == "test@example.com"
    assert "access_token" in response.cookies


def test_login_invalid_credentials(client, test_user):
    response = client.post("/api/auth/login", json={"email": "test@example.com", "password": "wrong-password"})
    assert response.status_code == 401


def test_login_unknown_email(client):
    response = client.post("/api/auth/login", json={"email": "nobody@example.com", "password": "whatever"})
    assert response.status_code == 401


def test_login_missing_fields(client):
    response = client.post("/api/auth/login", json={"email": "test@example.com"})
    assert response.status_code == 422


def test_login_deactivated_account_rejected(client, db_session, test_user):
    test_user.is_active = False
    db_session.add(test_user)
    db_session.commit()

    response = client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})
    assert response.status_code == 403


def test_mobile_login_returns_token(client, test_user):
    response = client.post("/api/auth/login/mobile", json={"email": "test@example.com", "password": "TestPass123!"})
    assert response.status_code == 200
    body = response.json()
    assert body["token"]
    assert body["user"]["email"] == "test@example.com"


def test_protected_route_without_cookie_is_rejected(client):
    response = client.get("/api/clients/")
    assert response.status_code == 401


def test_me_requires_authentication(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 401


def test_login_then_access_me(client, test_user):
    login = client.post("/api/auth/login", json={"email": "test@example.com", "password": "TestPass123!"})
    assert login.status_code == 200

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["email"] == "test@example.com"
