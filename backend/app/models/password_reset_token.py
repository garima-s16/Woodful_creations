from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


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
