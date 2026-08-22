import logging

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.middleware import SecurityHeadersMiddleware, GlobalRateLimitMiddleware
from app.core.auto_migrate import run_startup_migrations
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
    if not _migration_state["healthy"]:
        response.status_code = 503
        return {"status": "degraded", "environment": settings.ENVIRONMENT, "reason": "database migrations failed on startup"}
    return {"status": "ok", "environment": settings.ENVIRONMENT}
