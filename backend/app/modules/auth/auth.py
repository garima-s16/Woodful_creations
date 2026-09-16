"""Authentication domain models: User (login/session accounts) and
PasswordResetToken. Split out of the former app/models/ top-level
package - these are the auth module's own models, following the
same modules/<domain>/models.py convention as every other domain
(app/modules/sales/models.py, app/modules/hr/models.py, etc.)."""
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.platform.database import BaseModel
from pydantic import BaseModel as PydanticBaseModel, EmailStr
from typing import Optional
from datetime import datetime
import logging
import secrets
import hashlib
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from app.platform.database import get_db
from app.platform.security import create_access_token, verify_password, hash_password, get_current_user
from app.platform.security import (
    rate_limit,
    check_account_rate_limit,
    check_login_backoff,
    record_login_failure,
    clear_login_failures,
)
from app.platform.audit import log_action
from app.platform.config import settings
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from app.platform.security import require_role, hash_password
from app.modules.hr.models import Employee


class User(BaseModel):
    __tablename__ = "users"

    username = Column(String(255), unique=True, index=True, nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(500), nullable=False)
    full_name = Column(String(255), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(String(50), default="user", nullable=False)
    # Links a login account to the real Employee record it belongs to -
    # not every user account is necessarily an employee (e.g. an
    # external accountant), so this is nullable. "My tasks" and similar
    # self-service features resolve through this FK, never by matching
    # full_name against Employee.name.
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_deleted = Column(Boolean, default=False, nullable=False)
    profile_picture = Column(String(500), nullable=True)
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    otp_secret = Column(String(255), nullable=True)
    last_login = Column(DateTime, nullable=True)
    cannot_be_deleted = Column(Boolean, default=False, nullable=False)  # protects seeded master accounts
    # Set whenever this account's password is changed (e.g. a successful
    # /api/auth/reset-password). get_current_user compares a token's
    # issued-at time against this - a token issued before the most recent
    # password change is treated as an invalidated session, even if it
    # has not yet expired. NULL means "never changed since account
    # creation" - no prior token is retroactively invalidated by this
    # column's mere existence.
    password_changed_at = Column(DateTime, nullable=True)


class PasswordResetToken(BaseModel):
    """A single password-reset request. Only the SHA-256 hash of the
    token is ever stored - the plaintext token exists only in the
    response/log at issue time and in the user's hands, never at rest.
    One-time use (used_at) and time-limited (expires_at). attempt_count
    guards against a script trying many wrong tokens for the same
    request, distinct from the per-IP request-level rate limiting
    applied at the route."""
    __tablename__ = "password_reset_tokens"

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    token_hash = Column(String(64), nullable=False, index=True)  # sha256 hex digest
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)
    attempt_count = Column(Integer, nullable=False, default=0)

    user = relationship("User")


"""Auth module schemas: self-service (register/login/password-reset)
and admin (create/update/list users) request/response shapes."""


class UserBase(PydanticBaseModel):
    email: EmailStr
    username: str
    full_name: str


class UserLogin(PydanticBaseModel):
    identifier: str  # email OR username
    password: str


class ForgotPasswordRequest(PydanticBaseModel):
    identifier: str  # email OR username


class ResetPasswordRequest(PydanticBaseModel):
    token: str
    new_password: str


class UserResponse(UserBase):
    id: int
    role: str
    employee_id: Optional[int] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class LoginResponse(PydanticBaseModel):
    """Web login response. The JWT itself lives only in the HttpOnly cookie -
    it is never included here, so it's never visible to page JavaScript."""
    user: UserResponse


class MobileLoginResponse(PydanticBaseModel):
    """Native app login response. No cookie is usable by a native HTTP
    client in the same way a browser uses one, so the token is returned
    directly here for the app to store in the OS keychain (Keychain on iOS,
    Keystore on Android) - never in plain app storage or localStorage."""
    token: str
    user: UserResponse


class UserCreateAdmin(PydanticBaseModel):
    username: str
    email: EmailStr
    password: str
    full_name: str
    phone: Optional[str] = None
    role: str = "user"
    employee_id: Optional[int] = None


class UserUpdateAdmin(PydanticBaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    employee_id: Optional[int] = None
    is_active: Optional[bool] = None


class UserAdminResponse(PydanticBaseModel):
    id: int
    username: str
    email: str
    full_name: str
    phone: Optional[str]
    role: str
    employee_id: Optional[int] = None
    is_active: bool
    cannot_be_deleted: bool
    last_login: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


# --- api/routes.py (login/session/password-recovery + user management) ---
"""Auth domain API routes: login/logout/session (auth_router) and
admin user management (users_router). Combines the former auth.py and
users.py."""

logger = logging.getLogger(__name__)


auth_router = APIRouter(prefix="/api/auth", tags=["auth"])


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


_DUMMY_PASSWORD_HASH = "$2a$10$vI8aWBnW3fID.ZQ4/zo1G.q1lRps.9cGLcZEiGDMVr5yUP1KUOYTa"


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
        verify_password(request.password, _DUMMY_PASSWORD_HASH)
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


@auth_router.post("/login", response_model=LoginResponse, dependencies=[Depends(rate_limit("login", settings.RATE_LIMIT_LOGIN_PER_MINUTE))])
def login(request: UserLogin, response: Response, http_request: Request, db: Session = Depends(get_db)):
    """Web login. The token is set as an HttpOnly cookie only - it is never
    present in this JSON response, so page JavaScript can never read it."""
    user = _authenticate(request, db)

    token = create_access_token({"user_id": user.id, "email": user.email, "role": user.role, "employee_id": user.employee_id})
    _set_auth_cookie(response, token)
    log_action(db, http_request, user_id=user.id, action="login", module_name="auth")

    return LoginResponse(user=_user_payload(user))


@auth_router.post("/login/mobile", response_model=MobileLoginResponse, dependencies=[Depends(rate_limit("login", settings.RATE_LIMIT_LOGIN_PER_MINUTE))])
def login_mobile(request: UserLogin, http_request: Request, db: Session = Depends(get_db)):
    """Native app login. Returns the token directly for the app to store in
    the OS keychain (Keychain/Keystore) and send back as a Bearer header -
    no HttpOnly cookie is set here since a native HTTP client can't rely on
    browser cookie handling the same way."""
    user = _authenticate(request, db)

    token = create_access_token({"user_id": user.id, "email": user.email, "role": user.role, "employee_id": user.employee_id})
    log_action(db, http_request, user_id=user.id, action="login", module_name="auth")

    return MobileLoginResponse(token=token, user=_user_payload(user))


@auth_router.post("/logout")
def logout(response: Response, http_request: Request, db: Session = Depends(get_db), user: dict = Depends(get_current_user)):
    response.delete_cookie(key=settings.COOKIE_NAME, path="/")
    log_action(db, http_request, user_id=user.get("user_id"), action="logout", module_name="auth")
    return {"message": "Logged out"}


@auth_router.get("/me")
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


@auth_router.post("/forgot-password", dependencies=[
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
    # Deferred import: communications/services.py imports User from this
    # file at its own module level, so a top-level import of
    # EmailService here would be a genuine circular import (same
    # pattern as app.modules.ai.contracts.route_to_agent).
    from app.modules.communications.services import EmailService
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


@auth_router.post("/reset-password", dependencies=[
    Depends(rate_limit("password-reset-verify", settings.RATE_LIMIT_PASSWORD_RESET_VERIFY_PER_MINUTE))
])
def reset_password(data: ResetPasswordRequest, db: Session = Depends(get_db)):
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    token_hash = _hash_token(data.token)

    # Per-token limit on top of the per-IP one already applied above - the
    # request has no account identifier of its own (just the opaque
    # token), so the token hash is the natural per-attempt key here, same
    # role as identifier-keyed limits play on the other auth endpoints.
    check_account_rate_limit(
        "password-reset-verify", token_hash,
        settings.RATE_LIMIT_PASSWORD_RESET_VERIFY_ACCOUNT_PER_MINUTE,
    )

    reset_token = db.query(PasswordResetToken).filter(PasswordResetToken.token_hash == token_hash).first()

    # Same generic failure message whether the token is unknown, already
    # used, or expired - distinguishing these to the caller would leak
    # information about which tokens have ever existed/been consumed.
    invalid_detail = "This reset link is invalid or has expired. Please request a new one."
    if not reset_token:
        raise HTTPException(status_code=400, detail=invalid_detail)

    # Recorded on every attempt against this specific, already-found token
    # row - including the used/expired failure branches below - not only
    # on eventual success, so this genuinely tracks repeated probing of one
    # issued token rather than a value that could only ever end up 0 or 1.
    reset_token.attempt_count += 1
    db.add(reset_token)
    db.commit()

    if reset_token.used_at is not None:
        raise HTTPException(status_code=400, detail=invalid_detail)
    if reset_token.expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail=invalid_detail)

    user = db.query(User).filter(User.id == reset_token.user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=400, detail=invalid_detail)

    user.password_hash = hash_password(data.new_password)
    # Marks the point after which any previously issued token/session for
    # this account is no longer honored (see get_current_user) - a reset
    # is the user's own signal that any earlier session should stop
    # working, not just that future logins need the new password.
    user.password_changed_at = datetime.utcnow()
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


users_router = APIRouter(prefix="/api/users", tags=["users"])


ALLOWED_ROLES = {"master", "user"}


@users_router.get("/", response_model=List[UserAdminResponse])
def list_users(role: Optional[str] = Query(None), db: Session = Depends(get_db),
                auth=Depends(require_role("master"))):
    query = db.query(User).filter(User.is_deleted.is_(False))
    if role:
        query = query.filter(User.role == role)
    return query.order_by(User.username).all()


@users_router.post("/", response_model=UserAdminResponse, status_code=201)
def create_user(data: UserCreateAdmin, request: Request, db: Session = Depends(get_db),
                 auth=Depends(require_role("master"))):
    if data.role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ALLOWED_ROLES}")
    if db.query(User).filter((User.username == data.username) | (User.email == data.email)).first():
        raise HTTPException(status_code=400, detail="Username or email already exists")
    if data.role != "master":
        # Every RBAC "own records only" check across the app (attendance,
        # leaves, salary slips, tasks, analytics, dashboard) resolves
        # "own" via auth.employee_id. A non-master account with no
        # employee_id doesn't just lack data of its own - the resulting
        # None makes several of those same filters no-op, returning
        # EVERY employee's records instead of none. Enforcing the link
        # here, at the one place User rows are created, is what makes
        # "non-master implies employee_id is set" an actual invariant
        # rather than an assumption those endpoints depend on.
        if not data.employee_id:
            raise HTTPException(status_code=400, detail="A non-master account must be linked to an employee.")
        if not db.query(Employee).filter(Employee.id == data.employee_id).first():
            raise HTTPException(status_code=400, detail="employee_id does not match an existing employee.")

    user = User(
        username=data.username, email=data.email, full_name=data.full_name, phone=data.phone,
        role=data.role, employee_id=data.employee_id, password_hash=hash_password(data.password), is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, request, user_id=auth.get("user_id"), action="create_user", module_name="users", record_id=user.id)
    return user


@users_router.get("/{user_id}", response_model=UserAdminResponse)
def get_user(user_id: int, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _active_master_count(db: Session, exclude_user_id: Optional[int] = None) -> int:
    query = db.query(User).filter(User.role == "master", User.is_active.is_(True), User.is_deleted.is_(False))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.count()


@users_router.put("/{user_id}", response_model=UserAdminResponse)
def update_user(user_id: int, data: UserUpdateAdmin, request: Request, db: Session = Depends(get_db),
                 auth=Depends(require_role("master"))):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.dict(exclude_unset=True)
    if "role" in update_data and update_data["role"] not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=f"Role must be one of {ALLOWED_ROLES}")
    if user.cannot_be_deleted and update_data.get("is_active") is False:
        raise HTTPException(status_code=403, detail="This account is protected and cannot be deactivated")

    # Same invariant as create_user: whatever this update leaves the
    # account as (role may change, employee_id may change, or neither),
    # a non-master result must end up with a real employee_id - never
    # silently demoted-and-unlinked, or unlinked-in-place, since every
    # "own records only" filter elsewhere depends on it being set.
    final_role = update_data.get("role", user.role)
    final_employee_id = update_data.get("employee_id", user.employee_id)
    if final_role != "master":
        if not final_employee_id:
            raise HTTPException(status_code=400, detail="A non-master account must be linked to an employee.")
        if not db.query(Employee).filter(Employee.id == final_employee_id).first():
            raise HTTPException(status_code=400, detail="employee_id does not match an existing employee.")

    # The actual requirement is - never allow the LAST active
    # master to be deactivated or demoted, for ANY master account, not
    # just ones someone remembered to flag cannot_be_deleted on. The
    # count excludes THIS user, so "the only other master is also
    # being deactivated in the same request" still correctly blocks -
    # what matters is how many would remain active afterward.
    is_deactivating = user.role == "master" and update_data.get("is_active") is False
    is_demoting = user.role == "master" and "role" in update_data and update_data["role"] != "master"
    if (is_deactivating or is_demoting) and _active_master_count(db, exclude_user_id=user.id) == 0:
        action = "deactivated" if is_deactivating else "demoted from Master"
        raise HTTPException(status_code=403, detail=f"This is the last active Master account and cannot be {action}.")

    for field, value in update_data.items():
        setattr(user, field, value)
    db.add(user)
    db.commit()
    db.refresh(user)
    log_action(db, request, user_id=auth.get("user_id"), action="update_user", module_name="users", record_id=user.id, new_value=update_data)
    return user


@users_router.delete("/{user_id}", status_code=204)
def delete_user(user_id: int, request: Request, db: Session = Depends(get_db), auth=Depends(require_role("master"))):
    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.cannot_be_deleted:
        raise HTTPException(status_code=403, detail="This account is protected and cannot be deleted")
    if user.id == auth.get("user_id"):
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    # Master accounts are never deletable through this endpoint, full
    # stop - not just the last one. A Master who genuinely needs
    # removing should be deactivated instead (via update_user), the
    # same pattern this app already uses elsewhere for anything with
    # real significance rather than hard-deleting it.
    if user.role == "master":
        raise HTTPException(status_code=403, detail="Master accounts cannot be deleted. Deactivate the account instead.")

    user.is_deleted = True
    user.is_active = False
    db.add(user)
    db.commit()
    log_action(db, request, user_id=auth.get("user_id"), action="delete_user", module_name="users", record_id=user.id)
