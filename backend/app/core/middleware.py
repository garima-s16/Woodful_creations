"""Security response headers, applied to every response."""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.rate_limit import _get_backend


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if settings.is_production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        # API responses are JSON, so a strict CSP that blocks everything but
        # same-origin is safe here; the React app is served separately.
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
        return response


class GlobalRateLimitMiddleware(BaseHTTPMiddleware):
    """A loose, default per-IP floor under every request, using
    RATE_LIMIT_DEFAULT_PER_MINUTE - so no endpoint in the application
    is left with zero rate limiting, not just the handful (login,
    password reset, chat, exports) that already have their own
    tighter, purpose-specific limit via the rate_limit() dependency.
    Those still apply independently on top of this - this is a floor,
    not a replacement."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)
        client_ip = request.client.host if request.client else "unknown"
        key = f"global:{client_ip}"
        if not _get_backend().is_allowed(key, settings.RATE_LIMIT_DEFAULT_PER_MINUTE, 60):
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests. Please slow down and try again shortly."},
            )
        return await call_next(request)
