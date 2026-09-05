"""
Application settings.

All values are read from environment variables (see .env.example).
No secret ever ships with a hardcoded default in production mode -
SECRET_KEY and DATABASE_URL must be supplied via the environment.
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolve the env file relative to backend/ regardless of the process's
# current working directory - avoids "SECRET_KEY field required" failures
# when the app is launched from the repo root instead of from inside
# backend/.
#
# local.env takes priority over .env if both exist - Neon
# connectivity work added Neon's DATABASE_URL to local.env specifically,
# and before this fix it was silently never read at all (env_file only
# ever pointed at a literal ".env" filename). Checked explicitly by file
# existence here, rather than relying on a particular pydantic-settings
# version's own multi-file-priority behavior, so this is unambiguous on
# inspection regardless of which version is installed.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_LOCAL_ENV_FILE = _PROJECT_ROOT / "local.env"
_DEFAULT_ENV_FILE = _PROJECT_ROOT / ".env"
_ENV_FILE = _LOCAL_ENV_FILE if _LOCAL_ENV_FILE.exists() else _DEFAULT_ENV_FILE


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), case_sensitive=True, extra="ignore")

    # --- App ---
    APP_NAME: str = "Woodful Creations"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./woodful.db"
    STORAGE_LOCAL_ROOT: str = "./storage_data"
    GOOGLE_DRIVE_CREDENTIALS_PATH: str = ""
    GOOGLE_DRIVE_ROOT_FOLDER_ID: str = ""
    # Explicit opt-in for the file/document storage
    # backend (app/platform/storage/storage.py), separate from just checking
    # whether GOOGLE_DRIVE_CREDENTIALS_PATH happens to be set. Setting
    # STORAGE_PROVIDER=drive without this also being true is refused
    # clearly at startup, rather than silently guessing intent from a
    # credentials path alone.
    GOOGLE_DRIVE_ENABLED: bool = False

    # Gemini AI gateway - server-side only,
    # never exposed to the frontend. GEMINI_ENABLED is an explicit
    # opt-in, matching the same pattern as GOOGLE_DRIVE_ENABLED -
    # setting only the API key does not silently turn this on.
    GEMINI_ENABLED: bool = False
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"
    # A bounded wait for a single Gemini call. Chosen to
    # be comfortably under typical HTTP/proxy request timeouts (so a
    # slow provider response doesn't itself trigger a confusing
    # gateway-timeout error upstream of Woodful) while still short
    # enough that a hanging provider can't make a chat message feel
    # broken to the user for an extended period.
    GEMINI_TIMEOUT_SECONDS: int = 15

    # --- Auth / JWT ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # short-lived access token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    COOKIE_NAME: str = "access_token"
    COOKIE_SECURE: bool = False         # set True in production (docker-compose does this) - only sent over HTTPS
    COOKIE_SAMESITE: str = "lax"        # "strict" if web+API share exact site, "lax" is safer default

    # --- CORS ---
    # Comma-separated list of exact origins allowed to call this API.
    # Never use "*" in production, especially alongside cookies.
    # Stored as a plain string, not List[str] - pydantic-settings tries to
    # JSON-decode env values for list-typed fields before any validator
    # runs, which crashes on a plain comma-separated string like
    # "http://a,http://b" with "error parsing value ... from source
    # EnvSettingsSource". Splitting it ourselves via the property below
    # avoids that entirely.
    CORS_ORIGINS: str = "http://localhost:3000"
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Rate limiting ---
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5  # per IP
    RATE_LIMIT_LOGIN_ACCOUNT_PER_MINUTE: int = 8  # per account (identifier), independent of IP
    RATE_LIMIT_PASSWORD_RESET_REQUEST_PER_HOUR: int = 3  # per IP - forgot-password requests
    RATE_LIMIT_PASSWORD_RESET_REQUEST_ACCOUNT_PER_HOUR: int = 3  # per account/email
    RATE_LIMIT_PASSWORD_RESET_VERIFY_PER_MINUTE: int = 5  # per IP - reset-password attempts
    RATE_LIMIT_PASSWORD_RESET_VERIFY_ACCOUNT_PER_MINUTE: int = 5  # per account/email

    # Exponential backoff for repeated authentication failures (per-account).
    # Not a permanent lockout: the delay grows with consecutive failures and
    # resets on a successful login or after the window elapses.
    LOGIN_BACKOFF_THRESHOLD: int = 4          # consecutive failures before backoff kicks in
    LOGIN_BACKOFF_BASE_SECONDS: int = 2       # delay after the threshold-th failure
    LOGIN_BACKOFF_MAX_SECONDS: int = 300      # cap (5 minutes)
    LOGIN_BACKOFF_RESET_SECONDS: int = 3600   # failure counter forgotten after 1h of inactivity
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120
    RATE_LIMIT_CHAT_PER_MINUTE: int = 20  # per IP - each message re-queries the database
    RATE_LIMIT_EXPORT_PER_MINUTE: int = 15  # per IP - applies to every /api/reports/*.xlsx and *.pdf endpoint
    # Communication search scans free-text across several
    # tables (task comments, order comments, client activities,
    # notifications), and AI insight/draft generation does multiple
    # queries per call - both expensive enough per-request to rate-limit
    # like chat/export above, not left uncapped.
    RATE_LIMIT_COMMUNICATION_SEARCH_PER_MINUTE: int = 20  # per IP
    RATE_LIMIT_COMMUNICATION_AI_PER_MINUTE: int = 10  # per IP - summarize/draft
    RATE_LIMIT_BULK_NOTIFICATION_PER_MINUTE: int = 10  # per IP - mark-all-read and similar bulk ops
    # "memory" (default - single process, zero extra dependency at runtime)
    # or "redis" (required for a multi-instance/multi-worker production
    # deployment, where the in-memory limiter's buckets would not be
    # shared across processes). See app/platform/security/rate_limit.py.
    RATE_LIMIT_BACKEND: str = "memory"

    # Storage provider selection - "local" is the only
    # backend actually implemented in this build. A future cloud
    # backend (S3-compatible/Azure Blob/GCS) would be selected here via
    # environment configuration, never hardcoded into business logic.
    STORAGE_PROVIDER: str = "local"

    REDIS_URL: str = "redis://localhost:6379/0"

    # The reverse proxy/load balancer IP(s) or CIDR(s) uvicorn should trust to
    # supply X-Forwarded-For - see docker-entrypoint.sh, which passes this to
    # uvicorn's --forwarded-allow-ips. Without this, every per-IP rate
    # limiter (app/platform/security/rate_limit.py, app/platform/middleware/middleware.py)
    # would see only the proxy's own IP for every request once deployed
    # behind any reverse proxy/load balancer/ingress - collapsing all real
    # clients into a single shared bucket rather than limiting each one
    # independently. Defaults to uvicorn's own default (loopback only),
    # which is correct for local development and any deployment with no
    # proxy in front. Set to the real proxy's IP/CIDR in production, or to
    # "*" only if the proxy's address is genuinely not known in advance
    # (e.g. a managed load balancer with rotating IPs) and the platform
    # itself already restricts inbound traffic to that proxy.
    FORWARDED_ALLOW_IPS: str = "127.0.0.1"

    # Production error/monitoring boundary - see app/platform/monitoring/monitoring.py.
    # "none" (default) means unhandled exceptions are still logged locally
    # (same as always) but nothing is sent anywhere external - this is a
    # safe, fully-functional default requiring zero extra infrastructure,
    # matching the same explicit-opt-in pattern as GEMINI_ENABLED/
    # GOOGLE_DRIVE_ENABLED. "sentry" sends them to a configured Sentry
    # project instead, in addition to the local log. The provider is
    # intentionally swappable - business/platform code only ever calls
    # capture_exception()/capture_message(), never a provider SDK directly.
    MONITORING_PROVIDER: str = "none"
    MONITORING_DSN: str = ""

    # --- Third-party (optional) ---
    SENDER_EMAIL: str = ""
    SENDER_PASSWORD: str = ""
    SENDER_NAME: str = "Woodful Creations"
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587

    # --- Uploads ---
    MAX_UPLOAD_SIZE: int = 52428800  # 50MB
    UPLOAD_DIRECTORY: str = "./uploads"
    # Same reasoning as CORS_ORIGINS above - plain string, split via property.
    ALLOWED_EXTENSIONS: str = "pdf,xlsx,docx,jpg,png,jpeg"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    @property
    def allowed_extensions_list(self) -> List[str]:
        return [ext.strip() for ext in self.ALLOWED_EXTENSIONS.split(",") if ext.strip()]

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_be_strong(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be set to a random string of at least 32 characters. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(48))\""
            )
        placeholder_markers = ("change", "secret-key", "your-", "woodful-secret")
        if any(marker in v.lower() for marker in placeholder_markers):
            raise ValueError("SECRET_KEY looks like a placeholder value - generate a real random secret.")
        return v

    @field_validator("ENVIRONMENT")
    @classmethod
    def environment_must_be_known(cls, v: str) -> str:
        allowed = {"development", "staging", "production"}
        if v not in allowed:
            raise ValueError(f"ENVIRONMENT must be one of {allowed}")
        return v

    @model_validator(mode="after")
    def debug_must_be_off_in_production(self):
        if self.ENVIRONMENT == "production" and self.DEBUG:
            raise ValueError(
                "DEBUG=True is not allowed when ENVIRONMENT=production - it would expose full "
                "stack tracebacks (file paths, code, and potentially secrets) in HTTP error "
                "responses. Set DEBUG=False for any production deployment."
            )
        if self.ENVIRONMENT == "production" and not self.COOKIE_SECURE:
            raise ValueError(
                "COOKIE_SECURE=False is not allowed when ENVIRONMENT=production - the auth "
                "cookie would be sent over plain HTTP, exposing session tokens to network "
                "interception. Set COOKIE_SECURE=True for any production deployment (the app "
                "must be served over HTTPS for this to work correctly)."
            )
        if self.ENVIRONMENT == "production" and self.DATABASE_URL.startswith("sqlite"):
            raise ValueError(
                "DATABASE_URL is SQLite (or was not set, and defaulted to SQLite) while "
                "ENVIRONMENT=production. Production must use PostgreSQL (Neon) - set "
                "DATABASE_URL to the real production connection string. Refusing to start "
                "rather than silently run production against a local SQLite file."
            )

        # "*" is never valid, in any environment - combined with
        # allow_credentials=True (always on, see app/main.py) a wildcard
        # origin is rejected outright by browsers anyway, but a
        # deployment shouldn't be allowed to reach that broken state.
        if "*" in self.cors_origins_list:
            raise ValueError(
                "CORS_ORIGINS contains '*' - wildcard origins are never allowed, especially "
                "alongside credentials (which this app always sends). List exact origins instead."
            )
        if self.ENVIRONMENT == "production":
            localhost_origins = [
                o for o in self.cors_origins_list
                if "localhost" in o or "127.0.0.1" in o
            ]
            if localhost_origins:
                raise ValueError(
                    f"CORS_ORIGINS includes localhost-style origin(s) {localhost_origins} while "
                    "ENVIRONMENT=production. This is either a leftover default or a "
                    "misconfiguration - set CORS_ORIGINS to the real production frontend "
                    "origin(s) explicitly. Refusing to start rather than silently allow (or "
                    "silently fail to allow) the wrong origin in production."
                )
            if not self.cors_origins_list:
                raise ValueError(
                    "CORS_ORIGINS is empty while ENVIRONMENT=production - the production "
                    "frontend would be unable to call this API. Set it explicitly."
                )

        # A multi-worker/multi-instance production deployment with the
        # in-memory rate limiter means each process tracks its own
        # buckets - the effective limit becomes (configured limit) x
        # (number of instances), silently far weaker than configured.
        if self.ENVIRONMENT == "production" and self.RATE_LIMIT_BACKEND != "redis":
            raise ValueError(
                "RATE_LIMIT_BACKEND is not 'redis' while ENVIRONMENT=production. A production "
                "deployment must use the shared Redis-backed rate limiter (RATE_LIMIT_BACKEND=redis "
                "with REDIS_URL set) - the in-memory backend is not shared across worker "
                "processes/instances and would silently under-enforce every configured limit."
            )

        # Gemini and Drive are each explicit opt-ins (GEMINI_ENABLED /
        # GOOGLE_DRIVE_ENABLED) precisely so a deployment can never appear
        # to have a capability enabled while missing what it needs to
        # actually work - catch the half-configured state at startup,
        # not the first time a request tries to use it.
        if self.GEMINI_ENABLED and not self.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_ENABLED=True but GEMINI_API_KEY is not set. Either set a real API key "
                "or set GEMINI_ENABLED=False - refusing to start in a half-configured state."
            )
        if self.GOOGLE_DRIVE_ENABLED and not (self.GOOGLE_DRIVE_CREDENTIALS_PATH and self.GOOGLE_DRIVE_ROOT_FOLDER_ID):
            raise ValueError(
                "GOOGLE_DRIVE_ENABLED=True but GOOGLE_DRIVE_CREDENTIALS_PATH and/or "
                "GOOGLE_DRIVE_ROOT_FOLDER_ID is not set. Either set both or set "
                "GOOGLE_DRIVE_ENABLED=False - refusing to start in a half-configured state."
            )
        if self.STORAGE_PROVIDER.lower() == "drive" and not self.GOOGLE_DRIVE_ENABLED:
            raise ValueError(
                "STORAGE_PROVIDER=drive but GOOGLE_DRIVE_ENABLED is not set - refusing to "
                "guess intent. Set GOOGLE_DRIVE_ENABLED=True explicitly if Drive storage is "
                "genuinely intended."
            )
        if self.MONITORING_PROVIDER.lower() not in ("none", "sentry"):
            raise ValueError(
                f"MONITORING_PROVIDER={self.MONITORING_PROVIDER!r} is not supported - use "
                "'none' or 'sentry'."
            )
        if self.MONITORING_PROVIDER.lower() == "sentry" and not self.MONITORING_DSN:
            raise ValueError(
                "MONITORING_PROVIDER=sentry but MONITORING_DSN is not set - refusing to start "
                "in a half-configured state where errors would silently never be reported "
                "anywhere. Either set MONITORING_DSN or set MONITORING_PROVIDER=none."
            )
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
