import logging
import threading

from fastapi import FastAPI, Response, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.platform.config import settings
from app.platform.database import engine, SessionLocal
from app.platform.middleware import SecurityHeadersMiddleware, GlobalRateLimitMiddleware
from app.platform.database import run_startup_migrations
from app.platform.monitoring import capture_exception
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
_scheduler_stop_event = threading.Event()
_scheduler_thread = None


# Defect repair (F138 P9.2): arbitrary, fixed lock key for this
# scheduler's per-cycle advisory lock - deliberately distinct from
# app.platform.database._MIGRATION_LOCK_KEY (8825170392) so the two
# locks can never collide/serialize against each other despite both
# being pg_advisory_lock calls scoped to this same app.
_SCHEDULER_LOCK_KEY = 8825170393


def _automation_scheduler_loop():
    """Family 131 section 23 - "auto-generated" notifications: calls the
    exact same AutomationService.run_all/NotificationService.run_all_checks
    the notification endpoints already call on-demand, just on a timer
    instead of only when someone opens the notification panel. Not a
    second automation engine - every rule's own dedup_key (see
    NotificationService.notify) still governs whether anything new is
    actually created, so this can never duplicate a notification the
    on-demand path already created, and vice versa.

    Runs in a plain daemon thread, not asyncio - every existing DB call
    in this app already uses the same synchronous SQLAlchemy Session
    (see get_db), so a background asyncio task would either block the
    event loop or need its own separate async DB layer; a thread with
    its own SessionLocal() session matches how the rest of the app
    already talks to the database. Sleeps in short slices so shutdown
    (see the "shutdown" event below) doesn't have to wait out a full
    interval.

    Defect repair (F138 P9.2): a horizontally-scaled deployment runs
    this same daemon thread inside every instance, each on its own
    independent timer. Before this fix, every instance's cycle ran
    unconditionally, so N instances meant N concurrent
    AutomationService.run_all/NotificationService.run_all_checks calls
    hitting the database on every cycle - not a correctness bug on its
    own (NotificationService.notify's dedup_key check, and now its
    backing partial unique index - see F138 P9.1 - already make a
    duplicate notification from two concurrent callers impossible), but
    wasted, redundant work that multiplies with the fleet size for no
    benefit, and a needless source of extra DB load/lock contention
    during every scheduled cycle. Fixed the same way
    run_startup_migrations() already serializes concurrent migration
    attempts across instances (see app/platform/database.py): a
    Postgres session-level advisory lock, keyed to this scheduler
    specifically (_SCHEDULER_LOCK_KEY, distinct from the migration
    lock's key so the two never interact). Unlike the migration lock,
    this uses pg_try_advisory_lock (non-blocking) rather than
    pg_advisory_lock - an instance that doesn't get the lock this cycle
    must never sit blocked waiting for it; it should simply skip this
    cycle's work (some other instance is already doing it) and try
    again next interval. Skipped entirely for SQLite (tests/local dev),
    which has no advisory-lock concept and, like
    run_startup_migrations(), was never the multi-instance scenario
    this protects against - a single local process always runs every
    cycle."""
    from app.modules.communications.automation import AutomationService
    from app.modules.communications.services import NotificationService

    interval_seconds = max(60, settings.AUTOMATION_SCHEDULER_INTERVAL_MINUTES * 60)
    is_sqlite = settings.DATABASE_URL.startswith("sqlite")
    logger.info("Automation scheduler started (every %s minute(s)).", settings.AUTOMATION_SCHEDULER_INTERVAL_MINUTES)
    while not _scheduler_stop_event.is_set():
        db = SessionLocal()
        try:
            if is_sqlite:
                # No multi-instance concern on SQLite - always run.
                AutomationService.run_all(db, trigger_event="scheduled_job")
                NotificationService.run_all_checks(db)
            else:
                got_lock = db.execute(
                    text("SELECT pg_try_advisory_lock(:key)"), {"key": _SCHEDULER_LOCK_KEY}
                ).scalar()
                if got_lock:
                    try:
                        AutomationService.run_all(db, trigger_event="scheduled_job")
                        NotificationService.run_all_checks(db)
                    finally:
                        db.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": _SCHEDULER_LOCK_KEY})
                else:
                    # Another instance already holds the lock and is
                    # running this cycle - skip ours rather than block,
                    # matching the non-blocking contract above.
                    logger.debug("Automation scheduler cycle skipped (another instance holds the lock).")
        except Exception:
            # One bad cycle must never kill the loop - the on-demand path
            # (opening the notification panel) still works even if a
            # scheduled cycle fails, and the next cycle simply tries again.
            logger.exception("Automation scheduler cycle failed.")
        finally:
            db.close()
        _scheduler_stop_event.wait(interval_seconds)


@app.on_event("shutdown")
def stop_automation_scheduler():
    _scheduler_stop_event.set()
    if _scheduler_thread is not None:
        _scheduler_thread.join(timeout=5)


def _start_automation_scheduler():
    global _scheduler_thread
    if not settings.AUTOMATION_SCHEDULER_ENABLED:
        logger.info("Automation scheduler disabled (AUTOMATION_SCHEDULER_ENABLED=false).")
        return
    _scheduler_stop_event.clear()
    _scheduler_thread = threading.Thread(target=_automation_scheduler_loop, name="automation-scheduler", daemon=True)
    _scheduler_thread.start()


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
    # Only start the background notification scheduler once migrations
    # have actually succeeded - starting it earlier (registered as its
    # own startup handler) would race it against an unmigrated schema,
    # exactly what the migration-failure branch above exists to prevent.
    _start_automation_scheduler()


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
