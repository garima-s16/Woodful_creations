"""
Authentication & authorization utilities.

Auth model:
- Web clients: JWT stored in an HttpOnly, Secure, SameSite cookie. JS on the
  page can never read this token, which closes off the most common XSS
  token-theft path.
- Native mobile clients (iOS app etc.): the same JWT is also returned once in
  the login JSON body so it can be stored in the OS keychain and sent back as
  a normal `Authorization: Bearer <token>` header. Keychain storage is not
  reachable by web-style XSS, so this is safe for a native app context.

`get_current_user` accepts either source transparently.
"""
from datetime import datetime, timedelta
from typing import Optional

import jwt
from jwt.exceptions import PyJWTError
import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.utils import get_authorization_scheme_param
from sqlalchemy.orm import Session

from app.platform.configuration.config import settings
from app.platform.database.database import get_db


def _bcrypt_bytes(password: str) -> bytes:
    """bcrypt's own hard limit is 72 bytes - passlib (the library this
    replaced) truncated silently at this same limit by default rather
    than raising, so truncating here preserves that exact behavior:
    an existing user whose password was ever longer than 72 bytes
    still verifies correctly, since the same truncated bytes are what
    both the original hash and this check were/are computed from."""
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    hashed = bcrypt.hashpw(_bcrypt_bytes(password), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_bcrypt_bytes(plain_password), hashed_password.encode("utf-8"))
    except ValueError:
        # A malformed/foreign hash (never produced by hash_password
        # above) - genuinely not a match, not a crash.
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")


def verify_token(token: str) -> dict:
    """Kept for backward compatibility with existing route modules that call
    verify_token(raw_token_string) directly."""
    return decode_token(token)


class CookieOrBearer(HTTPBearer):
    """Extracts a bearer token from the HttpOnly cookie first (web flow),
    falling back to a standard Authorization header (native app flow)."""

    async def __call__(self, request: Request) -> HTTPAuthorizationCredentials:
        cookie_token = request.cookies.get(settings.COOKIE_NAME)
        if cookie_token:
            return HTTPAuthorizationCredentials(scheme="Bearer", credentials=cookie_token)

        header_value = request.headers.get("Authorization")
        scheme, credentials = get_authorization_scheme_param(header_value)
        if header_value and scheme.lower() == "bearer" and credentials:
            return HTTPAuthorizationCredentials(scheme="Bearer", credentials=credentials)

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")


# Shared dependency instance - import this instead of instantiating HTTPBearer()
# separately in every route module.
security = CookieOrBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> dict:
    """Decodes the token, then re-validates it against CURRENT account
    state on every request - not just once at login. A previously
    issued, still-unexpired token must not go on granting access based
    on stale claims baked into it at issue time:

    - the account must still exist and not be deleted/deactivated
      (an admin deactivating a user mid-session now actually takes
      effect immediately, not just at that user's next login)
    - the token must have been issued at/after the account's most
      recent password reset (see User.password_changed_at) - a reset
      is the user's own "invalidate whatever else might have this
      account" signal, and previously had no effect on tokens already
      issued
    - role and employee_id are returned from the DB row, never from
      the token's own (client-visible, if less trustworthy) claims -
      a role change or employee-link change by an admin takes effect
      on the very next request, not only after the affected user logs
      out and back in

    Imported locally to avoid a module import cycle at process start
    (app.modules.auth.models -> app.platform.database.base -> app.platform.database.database, which
    this module now also imports directly - importing the model at
    call time keeps this file's own import order simple regardless of
    how app.models ends up wired)."""
    from app.modules.auth.models import User

    payload = decode_token(credentials.credentials)
    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    user = db.query(User).filter(User.id == user_id, User.is_deleted.is_(False)).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This account has been deactivated")

    if user.password_changed_at is not None:
        issued_at = payload.get("iat")
        # A token from before this file tracked "iat", or one missing it
        # for any other reason, cannot be proven to postdate the reset -
        # treat it the same as a token that demonstrably predates it,
        # rather than assuming it in the token's favor.
        if issued_at is None or datetime.utcfromtimestamp(issued_at) < user.password_changed_at:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session")

    return {
        "user_id": user.id,
        "email": user.email,
        "username": user.username,
        "role": user.role,
        "employee_id": user.employee_id,
    }


def require_role(*allowed_roles: str):
    """Usage: Depends(require_role("master"))"""

    def _check(user: dict = Depends(get_current_user)) -> dict:
        role = user.get("role", "user")
        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"This action requires one of the following roles: {', '.join(allowed_roles)}",
            )
        return user

    return _check
