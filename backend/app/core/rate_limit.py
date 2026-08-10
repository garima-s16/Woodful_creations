"""
Lightweight in-memory rate limiter.

This is a dependency-free sliding-window limiter suitable for a single-process
deployment. It is NOT shared across multiple worker processes/machines - for a
multi-instance production deployment, swap this for a Redis-backed limiter
(e.g. slowapi + redis) using the same interface.
"""
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request, status

_buckets: dict[str, deque] = defaultdict(deque)
_lock = Lock()


def _client_key(request: Request, bucket: str) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return f"{bucket}:{client_ip}"


def rate_limit(bucket: str, max_requests: int, window_seconds: int = 60):
    """Returns a FastAPI dependency enforcing max_requests per window_seconds
    per client IP, scoped to `bucket` (e.g. "login")."""

    def _dependency(request: Request):
        key = _client_key(request, bucket)
        now = time.monotonic()
        with _lock:
            q = _buckets[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= max_requests:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please slow down and try again shortly.",
                )
            q.append(now)

    return _dependency
