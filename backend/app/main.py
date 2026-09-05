import logging

from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.platform.configuration.config import settings
from app.platform.database.database import engine
from app.platform.middleware.middleware import SecurityHeadersMiddleware, GlobalRateLimitMiddleware
from app.platform.database.auto_migrate import run_startup_migrations
from app.platform.monitoring.monitoring import capture_exception
from app.api.routes import all_routers

# Ensure every model is registered on the shared Base before migrations run.
from app import models  # noqa: F401

logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)
logger = logging.getLogger(__name__)

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
# CORS must be added LAST - Starlette wraps middleware in reverse
# registration order, so the last one added is the OUTERMOST layer and
# sees every response, including one that another middleware short-
# circuits.
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


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    capture_exception(exc, method=request.method, path=request.url.path)
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred. Please try again."})


_migration_state = {"healthy": True, "error": None}


@app.on_event("startup")
def on_startup():
    print("Checking database migrations...", flush=True)
    try:
        run_startup_migrations()
        print("Database migrations checked - server is ready.", flush=True)
    except Exception as exc:
        logger.exception(
            "Automatic database migration failed. Refusing to start the server - "
            "serving requests against a known out-of-date schema would fail "
            "unpredictably and mask the real problem. Check the traceback above "
            "for the specific issue, fix it, and restart."
        )
        print("Database migration check failed - server will NOT start. See the error above.", flush=True)
        _migration_state["healthy"] = False
        _migration_state["error"] = str(exc)
        raise


@app.get("/health")
def health_check(response: Response):
    """Readiness check: (a) did startup migrations succeed, and (b) is the
    database actually reachable right now via a lightweight query. Startup
    success alone does NOT mean the DB is still reachable later (network
    blip, DB restart, connection pool exhaustion) - so this re-checks live,
    on every call, rather than only trusting the one-time startup flag."""
    if not _migration_state["healthy"]:
        response.status_code = 503
        return {"status": "degraded", "environment": settings.ENVIRONMENT, "reason": "database migrations failed on startup"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check failed: database is not reachable.")
        response.status_code = 503
        # No exception detail in the response - that could leak connection
        # info (host, driver internals) to an unauthenticated caller.
        return {"status": "degraded", "environment": settings.ENVIRONMENT, "reason": "database not reachable"}

    return {"status": "ok", "environment": settings.ENVIRONMENT}
