"""Authentication domain models: User (login/session accounts) and
PasswordResetToken. Split out of the former app/models/ top-level
package - these are the auth module's own models, following the
same modules/<domain>/models.py convention as every other domain
(app/modules/sales/models.py, app/modules/hr/models.py, etc.)."""
from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.platform.database.base import BaseModel


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
