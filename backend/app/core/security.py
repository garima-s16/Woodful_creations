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

from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.security.utils import get_authorization_scheme_param

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": datetime.utcnow()})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
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


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    return decode_token(credentials.credentials)


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
