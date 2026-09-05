"""Tests for the password recovery flow - the previously-identified
gap (no forgot-password/reset-password existed at all). Covers
account-enumeration safety, token expiry/one-time-use, and the
other-tokens-invalidated-on-success behavior."""
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
    from app.modules.auth.models import PasswordResetToken
    from app.modules.auth.models import User
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
    from app.modules.auth.models import PasswordResetToken
    from app.modules.auth.models import User

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
    from app.modules.auth.models import PasswordResetToken
    from app.modules.auth.models import User

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
    from app.modules.auth.models import PasswordResetToken
    from app.modules.auth.models import User

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
    from app.modules.auth.models import PasswordResetToken
    from app.modules.auth.models import User

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


def test_attempt_count_increments_on_repeated_probing_of_same_token(client, test_user, db_session):
    """attempt_count must genuinely track repeated attempts against one
    already-issued token, not only reach 1 on eventual success -
    otherwise probing an already-used or expired token repeatedly would
    leave no trace beyond the first attempt."""
    import hashlib
    import secrets
    from app.modules.auth.models import PasswordResetToken
    from app.modules.auth.models import User

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
