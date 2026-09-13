"""Auth domain tests: user/account administration and audit-log
access, plus the password recovery flow (forgot/reset password).
Combines the former test_admin.py and test_password_recovery.py."""
from app.platform.security import hash_password
from app.modules.auth.auth import User
from tests.helpers import _login


def test_list_users_requires_master(client):
    resp = client.get("/api/users/")
    assert resp.status_code == 401


def test_master_can_create_and_list_users(client, test_user):
    _login(client, test_user)
    employee = client.post("/api/employees/", json={"name": "New Staff Employee"}).json()
    resp = client.post("/api/users/", json={
        "username": "newstaff", "email": "staff@example.com", "password": "StaffPass1!",
        "full_name": "New Staff", "role": "user", "employee_id": employee["id"],
    })
    assert resp.status_code == 201
    new_id = resp.json()["id"]

    resp = client.get("/api/users/")
    assert resp.status_code == 200
    assert any(u["id"] == new_id for u in resp.json())


def test_non_master_user_requires_an_employee_link(client, test_user):
    """The invariant every 'own records only' RBAC check across the app
    depends on: a non-master account with no employee_id would make
    those filters no-op (returning every employee's records instead of
    none), so creation must refuse it outright."""
    _login(client, test_user)
    resp = client.post("/api/users/", json={
        "username": "unlinkedstaff", "email": "unlinked@example.com", "password": "StaffPass1!",
        "full_name": "Unlinked Staff", "role": "user",
    })
    assert resp.status_code == 400


def test_non_master_user_employee_id_must_reference_a_real_employee(client, test_user):
    _login(client, test_user)
    resp = client.post("/api/users/", json={
        "username": "ghoststaff", "email": "ghost@example.com", "password": "StaffPass1!",
        "full_name": "Ghost Staff", "role": "user", "employee_id": 999999,
    })
    assert resp.status_code == 400


def test_cannot_deactivate_protected_account(client, test_user, db_session):
    _login(client, test_user)
    test_user.cannot_be_deleted = True
    db_session.add(test_user)
    db_session.commit()

    resp = client.put(f"/api/users/{test_user.id}", json={"is_active": False})
    assert resp.status_code == 403


def test_cannot_delete_own_account(client, test_user):
    _login(client, test_user)
    resp = client.delete(f"/api/users/{test_user.id}")
    assert resp.status_code == 400


def test_cannot_delete_protected_account(client, test_user, db_session):
    _login(client, test_user)
    resp = client.post("/api/users/", json={
        "username": "protectedstaff", "email": "protected@example.com", "password": "StaffPass1!",
        "full_name": "Protected Staff", "role": "master",
    })
    protected_id = resp.json()["id"]

    protected_user = db_session.query(User).filter(User.id == protected_id).first()
    protected_user.cannot_be_deleted = True
    db_session.add(protected_user)
    db_session.commit()

    resp = client.delete(f"/api/users/{protected_id}")
    assert resp.status_code == 403


def test_audit_logs_requires_master(client):
    resp = client.get("/api/audit-logs/")
    assert resp.status_code == 401


def test_audit_logs_capture_login(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/audit-logs/", params={"action": "login"})
    assert resp.status_code == 200
    assert len(resp.json()) >= 1


# --- Password recovery ---

from datetime import datetime, timedelta


def test_forgot_password_same_response_for_real_and_fake_identifier(client, test_user):
    """The core account-enumeration protection - response must be
    identical whether or not the account exists."""
    real = client.post("/api/auth/forgot-password", json={"identifier": "test@example.com"})
    fake = client.post("/api/auth/forgot-password", json={"identifier": "definitely-not-a-real-account@example.com"})
    assert real.status_code == 200
    assert fake.status_code == 200
    assert real.json() == fake.json()


def test_forgot_password_creates_a_token_for_real_account(client, test_user, db_session):
    from app.modules.auth.auth import PasswordResetToken
    from app.modules.auth.auth import User
    user = db_session.query(User).filter(User.email == "test@example.com").first()
    before = db_session.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).count()

    client.post("/api/auth/forgot-password", json={"identifier": "test@example.com"})

    after = db_session.query(PasswordResetToken).filter(PasswordResetToken.user_id == user.id).count()
    assert after == before + 1


def test_reset_password_with_invalid_token_fails(client, test_user):
    resp = client.post("/api/auth/reset-password", json={"token": "not-a-real-token", "new_password": "NewPass123!"})
    assert resp.status_code == 400


def test_reset_password_rejects_short_password(client, test_user):
    resp = client.post("/api/auth/reset-password", json={"token": "anything", "new_password": "short"})
    assert resp.status_code == 400
    assert "8 characters" in resp.json()["detail"]


def test_reset_password_full_flow_and_login_with_new_password(client, test_user, db_session):
    """The complete real path: request a token directly (bypassing
    email, which we can't intercept in a test), use it to reset, then
    confirm the new password actually works for login."""
    import hashlib
    import secrets
    from app.modules.auth.auth import PasswordResetToken
    from app.modules.auth.auth import User

    user = db_session.query(User).filter(User.email == "test@example.com").first()
    raw_token = secrets.token_urlsafe(32)
    token_row = PasswordResetToken(
        user_id=user.id, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db_session.add(token_row)
    db_session.commit()

    resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "BrandNewPass123!"})
    assert resp.status_code == 200

    login_old = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert login_old.status_code == 401

    login_new = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "BrandNewPass123!"})
    assert login_new.status_code == 200


def test_reset_token_cannot_be_used_twice(client, test_user, db_session):
    import hashlib
    import secrets
    from app.modules.auth.auth import PasswordResetToken
    from app.modules.auth.auth import User

    user = db_session.query(User).filter(User.email == "test@example.com").first()
    raw_token = secrets.token_urlsafe(32)
    token_row = PasswordResetToken(
        user_id=user.id, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db_session.add(token_row)
    db_session.commit()

    first = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "FirstReset123!"})
    assert first.status_code == 200

    second = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "SecondReset123!"})
    assert second.status_code == 400


def test_expired_reset_token_is_rejected(client, test_user, db_session):
    import hashlib
    import secrets
    from app.modules.auth.auth import PasswordResetToken
    from app.modules.auth.auth import User

    user = db_session.query(User).filter(User.email == "test@example.com").first()
    raw_token = secrets.token_urlsafe(32)
    token_row = PasswordResetToken(
        user_id=user.id, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.utcnow() - timedelta(minutes=5),  # already expired
    )
    db_session.add(token_row)
    db_session.commit()

    resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "ExpiredTest123!"})
    assert resp.status_code == 400


def test_successful_reset_invalidates_other_outstanding_tokens(client, test_user, db_session):
    """A second, earlier, still-unused reset link must stop working
    once a different one has already been used to reset the
    password."""
    import hashlib
    import secrets
    from app.modules.auth.auth import PasswordResetToken
    from app.modules.auth.auth import User

    user = db_session.query(User).filter(User.email == "test@example.com").first()
    old_raw = secrets.token_urlsafe(32)
    new_raw = secrets.token_urlsafe(32)
    db_session.add(PasswordResetToken(
        user_id=user.id, token_hash=hashlib.sha256(old_raw.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    ))
    db_session.add(PasswordResetToken(
        user_id=user.id, token_hash=hashlib.sha256(new_raw.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    ))
    db_session.commit()

    used = client.post("/api/auth/reset-password", json={"token": new_raw, "new_password": "UsedFirst123!"})
    assert used.status_code == 200

    stale = client.post("/api/auth/reset-password", json={"token": old_raw, "new_password": "TriesToUseStale123!"})
    assert stale.status_code == 400


# --- Session stability (WOODFUL AUTH + STARTUP LATENCY DEFECT REPAIR) ---
"""Regression coverage for the "login 200, then every request 401"
defect: the root cause (see frontend/src/utils/api.js and
frontend/.env.example) was a browser-only SameSite/cross-site cookie
behavior that a server-side TestClient can never reproduce - httpx's
cookie jar has no concept of SameSite at all, so these tests cannot
catch that specific regression directly. What they DO pin down is
everything the fix must NOT have broken along the way: the cookie is
still genuinely set on login, still genuinely valid across repeated
requests, still genuinely rejected once it should be (expired,
malformed, deactivated account, or a password reset since issued), and
CORS is still configured correctly for local dev - i.e. every part of
the auth contract this defect repair touched or relied on."""
from datetime import timedelta
from app.platform.config import settings
from app.platform.security import create_access_token


def test_login_sets_the_auth_cookie(client, test_user):
    resp = client.post("/api/auth/login", json={"identifier": "test@example.com", "password": "TestPass123!"})
    assert resp.status_code == 200
    assert settings.COOKIE_NAME in resp.cookies
    # The JWT itself must never appear in the JSON body - it lives only
    # in the HttpOnly cookie, so page JavaScript can never read it.
    assert "token" not in resp.json()
    assert "access_token" not in resp.json()


def test_me_works_immediately_after_login(client, test_user):
    _login(client, test_user)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 200
    assert resp.json()["email"] == "test@example.com"


def test_same_cookie_stays_valid_across_multiple_protected_requests(client, test_user):
    """C + D combined: the exact same session cookie, reused for
    several genuinely different protected requests in a row, must keep
    working every time - a valid JWT does not randomly become invalid
    between requests within the same backend process."""
    _login(client, test_user)
    for _ in range(5):
        resp = client.get("/api/auth/me")
        assert resp.status_code == 200
    # A different protected endpoint, not just /me repeated - proves
    # the cookie is genuinely usable app-wide, not special-cased.
    resp = client.get("/api/users/")
    assert resp.status_code == 200


def test_expired_jwt_returns_401(client, test_user):
    _login(client, test_user)
    expired_token = create_access_token(
        {"user_id": test_user.id, "email": test_user.email, "role": test_user.role, "employee_id": test_user.employee_id},
        expires_delta=timedelta(minutes=-5),
    )
    client.cookies.set(settings.COOKIE_NAME, expired_token)
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_malformed_jwt_returns_401(client, test_user):
    client.cookies.set(settings.COOKIE_NAME, "not-a-real-jwt-token-at-all")
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_deactivated_account_is_rejected_mid_session(client, test_user, db_session):
    """An admin deactivating a user mid-session must take effect on the
    very next request, not only at that user's next login attempt -
    see get_current_user's own docstring."""
    _login(client, test_user)
    assert client.get("/api/auth/me").status_code == 200

    test_user.is_active = False
    db_session.add(test_user)
    db_session.commit()

    resp = client.get("/api/auth/me")
    assert resp.status_code == 403


def test_password_reset_invalidates_the_previously_issued_session(client, test_user, db_session):
    """A reset is the user's own "invalidate whatever else might have
    this account" signal - a cookie issued before the reset must stop
    working immediately after, even though it hasn't expired."""
    import hashlib
    import secrets
    from app.modules.auth.auth import PasswordResetToken

    _login(client, test_user)
    assert client.get("/api/auth/me").status_code == 200

    raw_token = secrets.token_urlsafe(32)
    db_session.add(PasswordResetToken(
        user_id=test_user.id, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    ))
    db_session.commit()

    reset_resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "PostResetPass123!"})
    assert reset_resp.status_code == 200

    # Same client, same (now stale) cookie still attached from the
    # login above - the reset-password call itself needed no auth and
    # never touched it.
    resp = client.get("/api/auth/me")
    assert resp.status_code == 401


def test_cors_allows_credentialed_requests_from_the_configured_dev_frontend(client):
    """The actual preflight a browser sends before a credentialed
    cross-origin request - confirms allow_credentials is genuinely on
    and the configured dev frontend origin is genuinely allowed, not
    just that CORS_ORIGINS happens to contain the right string."""
    resp = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert resp.headers.get("access-control-allow-credentials") == "true"


def test_cors_origins_and_cookie_defaults_match_the_local_dev_frontend():
    """Direct config-level pin for Requirements 1-3: the backend's own
    defaults (no .env override) must already agree with the frontend's
    default host and must not silently weaken cookie security to do
    it."""
    assert "http://localhost:3000" in settings.cors_origins_list
    assert settings.FRONTEND_URL == "http://localhost:3000"
    assert settings.COOKIE_SAMESITE == "lax"
    # Dev-only default - production is separately enforced to True by
    # Settings' own model_validator (see test below).
    assert settings.COOKIE_SECURE is False


def test_settings_is_a_true_singleton_for_the_process_lifetime():
    """Requirement 6: SECRET_KEY (and everything else) must load once
    and never regenerate mid-process - get_settings() is @lru_cache'd
    and called once at import time (see app/platform/config.py's
    module-level `settings = get_settings()`), so every caller anywhere
    in the app must be looking at the exact same Settings instance,
    not a fresh one re-read from the environment on each call."""
    from app.platform.config import get_settings
    assert get_settings() is get_settings()
    assert get_settings() is settings


def test_attempt_count_increments_on_repeated_probing_of_same_token(client, test_user, db_session):
    """attempt_count must genuinely track repeated attempts against one
    already-issued token, not only reach 1 on eventual success -
    otherwise probing an already-used or expired token repeatedly would
    leave no trace beyond the first attempt."""
    import hashlib
    import secrets
    from app.modules.auth.auth import PasswordResetToken
    from app.modules.auth.auth import User

    user = db_session.query(User).filter(User.email == "test@example.com").first()
    raw_token = secrets.token_urlsafe(32)
    token_row = PasswordResetToken(
        user_id=user.id, token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
        expires_at=datetime.utcnow() - timedelta(minutes=5),  # already expired
    )
    db_session.add(token_row)
    db_session.commit()
    token_id = token_row.id

    for _ in range(3):
        resp = client.post("/api/auth/reset-password", json={"token": raw_token, "new_password": "Whatever123!"})
        assert resp.status_code == 400

    db_session.expire_all()
    refreshed = db_session.query(PasswordResetToken).filter(PasswordResetToken.id == token_id).first()
    assert refreshed.attempt_count == 3
