import logging
import secrets
import hashlib
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import create_access_token, verify_password, hash_password, get_current_user
from app.core.rate_limit import (
    rate_limit,
    check_account_rate_limit,
    check_login_backoff,
    record_login_failure,
    clear_login_failures,
)
from app.core.audit import log_action
from app.core.config import settings
from app.models.user import User
from app.models.password_reset_token import PasswordResetToken
from app.schemas.user import LoginResponse, MobileLoginResponse, UserLogin, ForgotPasswordRequest, ResetPasswordRequest
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
    )


def _authenticate(request: UserLogin, db: Session) -> User:
    identifier = request.identifier

    # Per-account fixed-window limit (independent of per-IP limit applied at
    # the route level) - stops one account being hammered from many IPs.
    check_account_rate_limit("login", identifier, settings.RATE_LIMIT_LOGIN_ACCOUNT_PER_MINUTE)
    # Exponential backoff on repeated consecutive failures for this account.
    check_login_backoff(identifier)

    user = db.query(User).filter(
        (User.email == identifier) | (User.username == identifier),
        User.is_deleted.is_(False),
    ).first()

    if not user:
        logger.info("Login failed: no account for identifier %r", identifier)
        record_login_failure(identifier)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not verify_password(request.password, user.password_hash):
        logger.info("Login failed: wrong password for user_id %s", user.id)
        record_login_failure(identifier)
        raise HTTPException(status_code=401, detail="Invalid username or password.")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account has been deactivated")

    clear_login_failures(identifier)
    return user


def _user_payload(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "role": user.role,
        "employee_id": user.employee_id,
        "is_active": user.is_active,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(rate_limit("login", settings.RATE_LIMIT_LOGIN_PER_MINUTE))])
def login(request: UserLogin, response: Response, http_request: Request, db: Session = Depends(get_db)):
    """Web login. The token is set as an HttpOnly cookie only - it is never
    present in this JSON response, so page JavaScript can never read it."""
    user = _authenticate(request, db)

    token = create_access_token({"user_id": user.id, "email": user.email, "role": user.role, "employee_id": user.employee_id})
    _set_auth_cookie(response, token)
    log_action(db, http_request, user_id=user.id, action="login", module_name="auth")

    return LoginResponse(user=_user_payload(user))


@router.post("/login/mobile", response_model=MobileLoginResponse, dependencies=[Depends(rate_limit("login", settings.RATE_LIMIT_LOGIN_PER_MINUTE))])
def login_mobile(request: UserLogin, http_request: Request, db: Session = Depends(get_db)):
    """Native app login. Returns the token directly for the app to store in
    the OS keychain (Keychain/Keystore) and send back as a Bearer header -
    no HttpOnly cookie is set here since a native HTTP client can't rely on
    browser cookie handling the same way."""
    user = _authenticate(request, db)

    token = create_access_token({"user_id": user.id, "email": user.email, "role": user.role, "employee_id": user.employee_id})
    log_action(db, http_request, user_id=user.id, action="login", module_name="auth")

    return MobileLoginResponse(token=token, user=_user_payload(user))


@router.post("/logout")
def logout(response: Response, http_request: Request, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    response.delete_cookie(key=settings.COOKIE_NAME, path="/")
    log_action(db, http_request, user_id=user.get("user_id"), action="logout", module_name="auth")
    return {"message": "Logged out"}


@router.get("/me")
def me(db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    db_user = db.query(User).filter(User.id == user.get("user_id"), User.is_deleted.is_(False)).first()
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": db_user.id,
        "email": db_user.email,
        "username": db_user.username,
        "full_name": db_user.full_name,
        "role": db_user.role,
        "employee_id": db_user.employee_id,
        "is_active": db_user.is_active,
    }


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@router.post("/forgot-password", dependencies=[
    Depends(rate_limit("password-reset-request", settings.RATE_LIMIT_PASSWORD_RESET_REQUEST_PER_HOUR, window_seconds=3600))
])
def forgot_password(data: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Always returns the same generic response, whether or not the
    account exists - the same account-enumeration protection already
    used for /login, applied here where it matters even more (a
    password-reset endpoint that confirms account existence is a
    textbook enumeration oracle)."""
    generic_response = {"message": "If an account exists for that email or username, a password reset link has been sent."}

    # Per-account limit on top of the per-IP one already applied above, so a
    # single account's inbox can't be spammed with reset emails from many IPs.
    check_account_rate_limit(
        "password-reset-request", data.identifier,
        settings.RATE_LIMIT_PASSWORD_RESET_REQUEST_ACCOUNT_PER_HOUR, window_seconds=3600,
    )

    user = db.query(User).filter(
        (User.email == data.identifier) | (User.username == data.identifier),
        User.is_deleted.is_(False), User.is_active.is_(True),
    ).first()
    if not user:
        logger.info("Password reset requested for unknown/inactive identifier %r", data.identifier)
        return generic_response

    raw_token = secrets.token_urlsafe(32)
    reset_token = PasswordResetToken(
        user_id=user.id, token_hash=_hash_token(raw_token),
        expires_at=datetime.utcnow() + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES),
    )
    db.add(reset_token)
    db.commit()

    reset_link = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"
    sent = EmailService().send_email(
        user.email, "Reset your Woodful Creations password",
        f"A password reset was requested for your account. This link expires in "
        f"{settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES} minutes and can only be used once: {reset_link}",
    )
    if not sent:
        if settings.is_production:
            # Never log the token itself in production - only that
            # delivery failed, so this can be investigated without the
            # token ever touching a log file an attacker might reach.
            logger.error("Password reset email delivery failed for user_id %s - SMTP not configured or send failed", user.id)
        else:
            # No real SMTP infrastructure in this environment - a safe,
            # explicit development mechanism, not a pretense that real
            # email delivery has been verified.
            logger.warning(
                "DEV MODE - email delivery unavailable. Reset link for user_id %s: %s", user.id, reset_link,
            )

    return generic_response


@router.post("/reset-password", dependencies=[
    Depends(rate_limit("password-reset-verify", settings.RATE_LIMIT_PASSWORD_RESET_VERIFY_PER_MINUTE))
])
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    token_hash = _hash_token(data.token)
    reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()

    # Same generic failure message whether the token is unknown, already
    # used, or expired - distinguishing these to the caller would leak
    # information about which tokens have ever existed/been consumed.
    invalid_detail = "This reset link is invalid or has expired. Please request a new one."
    if not reset_token:
        raise HTTPException(status_code=400, detail=invalid_detail)
    if reset_token.used_at is not None:
        raise HTTPException(status_code=400, detail=invalid_detail)
    if reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail=invalid_detail)

    reset_token.attempt_count += 1
    user = db.query(User).filter(User.id == reset_token.user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=400, detail=invalid_detail)

    user.password_hash = hash_password(data.new_password)
    reset_token.used_at = datetime.utcnow()
    db.add(user)
    db.add(reset_token)

    # Invalidate every other outstanding reset token for this user - an
    # old, unused reset link (e.g. from an earlier request the user
    # abandoned) must not still work after a successful reset.
    other_tokens = db.query(PasswordResetToken).filter(
        PasswordResetToken.user_id == user.id, PasswordResetToken.id != reset_token.id,
        PasswordResetToken.used_at.is_(None),
    ).all()
    for other in other_tokens:
        other.used_at = datetime.utcnow()
        db.add(other)

    db.commit()
    logger.info("Password reset completed for user_id %s", user.id)
    return {"message": "Your password has been reset. Please sign in with your new password."}
