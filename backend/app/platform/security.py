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
from app.platform.config import settings
from app.platform.database import get_db
import time
from collections import defaultdict, deque
from threading import Lock
from fastapi import HTTPException, Request, status


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
    (app.modules.auth.auth -> app.platform.database -> app.platform.database, which
    this module now also imports directly - importing the model at
    call time keeps this file's own import order simple regardless of
    how app.models ends up wired)."""
    from app.modules.auth.auth import User

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


# --- rate_limit.py (rate limiting and login-attempt backoff) ---
"""
Rate limiting, with a pluggable backend.

Development / single instance (default):
    RATE_LIMIT_BACKEND=memory - an in-process sliding-window limiter.
    Zero extra dependency, zero extra infrastructure. This is NOT shared
    across multiple worker processes or machines.

Production / multi-instance:
    RATE_LIMIT_BACKEND=redis - a Redis-backed sliding-window limiter
    (sorted-set based, same semantics as the in-memory one), shared
    across every process/machine talking to the same Redis instance.
    Requires REDIS_URL to be set and the `redis` package installed -
    neither is required to run locally with the default backend.

Every route in this app calls rate_limit(bucket, max_requests,
window_seconds) exactly as before - this file is the only place that
needs to know which backend is active.
"""

class _InMemoryBackend:
    """The original limiter, unchanged - a dependency-free sliding
    window suitable for a single-process deployment."""

    def __init__(self):
        self._buckets: dict[str, deque] = defaultdict(deque)
        self._lock = Lock()

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            q = self._buckets[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= max_requests:
                return False
            q.append(now)
            return True


class _RedisBackend:
    """Sorted-set sliding window: each request adds the current
    timestamp as both score and member (a small unique suffix keeps
    members distinct even for requests in the same millisecond),
    trims anything older than the window, then checks the remaining
    count. Matches the in-memory backend's semantics so switching
    backends does not change rate-limit behavior, only whether it's
    shared across processes."""

    def __init__(self):
        # Imported here, not at module level - a plain local dev setup
        # using the default "memory" backend must never need the redis
        # package installed just to import this file.
        import redis
        self._client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        import uuid
        now = time.time()
        window_start = now - window_seconds
        redis_key = f"ratelimit:{key}"
        pipe = self._client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {f"{now}:{uuid.uuid4().hex}": now})
        pipe.expire(redis_key, window_seconds)
        _, current_count, _, _ = pipe.execute()
        return current_count < max_requests


_backend = None


def reset_rate_limits():
    """Test isolation. This module's
    _backend is a lazily-created, module-level singleton that
    otherwise persists for the life of the process - across every
    test in a suite, not just one. Without this, a test suite with
    more than one test hitting the same rate-limited endpoint (login,
    chat, etc.) could see a LATER test unexpectedly rejected with 429
    purely because of requests an EARLIER test already made against
    the same bucket, not because of any genuine bug in the test itself.
    Setting _backend back to None makes the next check lazily create a
    fresh instance - the exact same path _get_backend already takes on
    its very first call, so this isn't a new code path, just re-
    triggering the existing one. Intended to be called from an autouse
    pytest fixture, once per test."""
    global _backend
    _backend = None


def _get_backend():
    global _backend
    if _backend is None:
        if settings.RATE_LIMIT_BACKEND == "redis":
            _backend = _RedisBackend()
        else:
            _backend = _InMemoryBackend()
    return _backend


def _client_key(request: Request, bucket: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return f"{bucket}:{client_ip}"


def rate_limit(bucket: str, max_requests: int, window_seconds: int = 60):
    """Returns a FastAPI dependency enforcing max_requests per window_seconds
    per client IP, scoped to `bucket` (e.g. "login"). Backend (in-memory vs
    Redis) is selected via RATE_LIMIT_BACKEND - callers never need to know
    which one is active."""

    def _dependency(request: Request):
        key = _client_key(request, bucket)
        if not _get_backend().is_allowed(key, max_requests, window_seconds):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please slow down and try again shortly.",
            )

    return _dependency


def check_account_rate_limit(bucket: str, identifier: str, max_requests: int, window_seconds: int = 60) -> None:
    """Same sliding-window limiter as `rate_limit`, but keyed on an account
    identifier (email/username) instead of client IP. Called directly inside
    a route body (rather than as a Depends(...)) because the identifier only
    becomes known once the request body is parsed. Raises 429 if exceeded.

    Used alongside per-IP `rate_limit(...)` on authentication endpoints so a
    single account can't be hammered from many IPs, and a single IP can't
    hammer many accounts - both dimensions are covered independently.
    """
    key = f"{bucket}-account:{identifier.strip().lower()}"
    if not _get_backend().is_allowed(key, max_requests, window_seconds):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts for this account. Please slow down and try again shortly.",
        )


class _InMemoryAttemptBackend:
    def __init__(self):
        self._data: dict[str, tuple[int, float]] = {}
        self._lock = Lock()

    def record_failure(self, key: str) -> int:
        with self._lock:
            count, _ = self._data.get(key, (0, 0.0))
            count += 1
            self._data[key] = (count, time.time())
            return count

    def get_state(self, key: str) -> tuple[int, float]:
        with self._lock:
            return self._data.get(key, (0, 0.0))

    def clear(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)


class _RedisAttemptBackend:
    def __init__(self):
        import redis
        self._client = redis.from_url(settings.REDIS_URL, decode_responses=True)

    def _keys(self, key: str) -> tuple[str, str]:
        base = f"loginfail:{key}"
        return base, f"{base}:ts"

    def record_failure(self, key: str) -> int:
        count_key, ts_key = self._keys(key)
        pipe = self._client.pipeline()
        pipe.incr(count_key)
        pipe.expire(count_key, settings.LOGIN_BACKOFF_RESET_SECONDS)
        pipe.set(ts_key, time.time(), ex=settings.LOGIN_BACKOFF_RESET_SECONDS)
        count, _, _ = pipe.execute()
        return int(count)

    def get_state(self, key: str) -> tuple[int, float]:
        count_key, ts_key = self._keys(key)
        count = self._client.get(count_key)
        ts = self._client.get(ts_key)
        return (int(count) if count else 0, float(ts) if ts else 0.0)

    def clear(self, key: str) -> None:
        count_key, ts_key = self._keys(key)
        self._client.delete(count_key, ts_key)


_attempt_backend = None


def _get_attempt_backend():
    global _attempt_backend
    if _attempt_backend is None:
        if settings.RATE_LIMIT_BACKEND == "redis":
            _attempt_backend = _RedisAttemptBackend()
        else:
            _attempt_backend = _InMemoryAttemptBackend()
    return _attempt_backend


def check_login_backoff(identifier: str) -> None:
    """Raise 429 if this account is currently in a backoff window from
    recent consecutive failures. Call BEFORE checking credentials."""
    key = identifier.strip().lower()
    count, last_ts = _get_attempt_backend().get_state(key)
    if count < settings.LOGIN_BACKOFF_THRESHOLD:
        return
    if time.time() - last_ts > settings.LOGIN_BACKOFF_RESET_SECONDS:
        _get_attempt_backend().clear(key)
        return
    wait = min(
        settings.LOGIN_BACKOFF_BASE_SECONDS * (2 ** (count - settings.LOGIN_BACKOFF_THRESHOLD)),
        settings.LOGIN_BACKOFF_MAX_SECONDS,
    )
    elapsed = time.time() - last_ts
    if elapsed < wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many failed attempts. Please try again in {int(wait - elapsed)} seconds.",
        )


def record_login_failure(identifier: str) -> None:
    _get_attempt_backend().record_failure(identifier.strip().lower())


def clear_login_failures(identifier: str) -> None:
    _get_attempt_backend().clear(identifier.strip().lower())
