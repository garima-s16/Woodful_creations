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
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

from app.core.config import settings


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


# ---------------------------------------------------------------------------
# Exponential backoff on repeated authentication failures (per account).
#
# This is deliberately NOT a permanent lockout: an attacker (or a user who
# mistyped their password) is slowed down with a growing delay, but the
# account is never permanently locked out of self-service login. The
# counter resets on a successful login or after LOGIN_BACKOFF_RESET_SECONDS
# of inactivity.
# ---------------------------------------------------------------------------

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
