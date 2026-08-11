import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.middleware import SecurityHeadersMiddleware
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

# CORS: explicit origin allow-list only. Required for cookie-based auth to work
# from the browser (credentials cannot be used with a wildcard origin).
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["X-Total-Count"],
)

app.add_middleware(SecurityHeadersMiddleware)

for router in all_routers:
    app.include_router(router)


@app.on_event("startup")
def on_startup():
    try:
        run_startup_migrations()
    except Exception:
        logger.exception(
            "Automatic database migration failed. The server is starting anyway, "
            "but requests that touch an out-of-date table will error until this "
            "is resolved - check the traceback above for the specific issue."
        )


@app.get("/health")
def health_check():
    return {"status": "ok", "environment": settings.ENVIRONMENT}
