import logging

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.middleware import SecurityHeadersMiddleware, GlobalRateLimitMiddleware
from app.core.auto_migrate import run_startup_migrations
from app.api.routes import all_routers

# Ensure every model is registered on the shared Base before migrations run.
from app import models  # noqa: F401

logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)

# Shared with on_startup() and MigrationGateMiddleware below - defined here,
# ahead of both, since it's read/written by each.
_migration_state = {"healthy": True, "error": None}


class MigrationGateMiddleware(BaseHTTPMiddleware):
    """If startup migrations failed, block every request except /health
    with a clear 503 instead of letting requests reach routes that assume
    an up-to-date schema. /health stays reachable so a human or an
    orchestrator's health check can see *why* the backend is degraded,
    rather than the backend either crashing outright (no diagnosis
    possible beyond logs) or - the actual prior bug - silently serving
    every other endpoint as if nothing were wrong."""

    async def dispatch(self, request, call_next):
        if not _migration_state["healthy"] and request.url.path != "/health":
            return JSONResponse(
                {
                    "status": "degraded",
                    "reason": "database migrations failed on startup - see /health for details",
                },
                status_code=503,
            )
        return await call_next(request)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    # Hide interactive docs in production to avoid exposing the full API surface.
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GlobalRateLimitMiddleware)
app.add_middleware(MigrationGateMiddleware)
# CORS must be added LAST - Starlette wraps middleware in reverse
# registration order, so the last one added is the OUTERMOST layer and
# sees every response, including one that another middleware short-
# circuits (e.g. a 429 from GlobalRateLimitMiddleware, an error from
# SecurityHeadersMiddleware). If CORS were added first/innermost, a
# short-circuited response would skip it entirely and reach the
# browser with no Access-Control-Allow-Origin header - the browser
# then blocks the frontend from reading it at all, which axios reports
# as a generic "Network Error" instead of the real status code. This
# was a real, confirmed bug: a burst of parallel dashboard requests
# hitting the rate-limit floor would all appear as opaque network
# failures rather than 429s.
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count"],
)

for router in all_routers:
    app.include_router(router)


@app.on_event("startup")
def on_startup():
    print("Checking database migrations...", flush=True)
    try:
        run_startup_migrations()
        print("Database migrations checked - server is ready.", flush=True)
    except Exception as exc:
        # Deliberately NOT re-raised. Raising here would fail Starlette's
        # lifespan startup, which stops the ASGI server from binding at
        # all - the process exits before it can serve anything, including
        # /health, so the "degraded" response below could never actually
        # be seen; an operator would just see a dead port with no live
        # diagnosis beyond stdout/stderr logs. Instead: log the failure as
        # loudly as possible, mark the app unhealthy, and let it finish
        # booting - MigrationGateMiddleware above then blocks every route
        # except /health with a 503 until this is fixed and the process is
        # restarted, so the API is never actually served against a
        # known-bad schema, but the failure stays diagnosable over HTTP.
        logger.exception(
            "Automatic database migration failed. The backend will start "
            "but will refuse all API traffic except /health until this is "
            "fixed and the process is restarted - serving requests against "
            "a known out-of-date schema would fail unpredictably and mask "
            "the real problem. Check the traceback above for the specific "
            "issue."
        )
        print("Database migration check failed - API traffic will be refused (503) until this is fixed. See the error above.", flush=True)
        _migration_state["healthy"] = False
        _migration_state["error"] = str(exc)


@app.get("/health")
def health_check(response: Response):
    if not _migration_state["healthy"]:
        response.status_code = 503
        return {
            "status": "degraded",
            "environment": settings.ENVIRONMENT,
            "reason": "database migrations failed on startup",
            "error": _migration_state["error"],
        }
    return {"status": "ok", "environment": settings.ENVIRONMENT}
