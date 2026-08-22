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

# Resolve .env relative to backend/ regardless of the process's current
# working directory - avoids "SECRET_KEY field required" failures when the
# app is launched from the repo root instead of from inside backend/.
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), case_sensitive=True, extra="ignore")

    # --- App ---
    APP_NAME: str = "Woodful Creations"
    APP_VERSION: str = "2.0.0"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = False

    # --- Database ---
    DATABASE_URL: str = "sqlite:///./woodful.db"
    # Family 105 Section 5 - which StorageProvider the new repository
    # layer (app/storage/) would use, if/when a route is actually
    # switched over to it. Not read by any existing route yet - every
    # current route still talks directly to SQLAlchemy via
    # DATABASE_URL above, completely unaffected by this setting.
    # "local" -> LocalJSONStorageProvider (development, no external
    # dependencies). "google_drive" -> GoogleDriveStorageProvider
    # (production target - see that module's docstring for its
    # current, honestly-unverified status).
    STORAGE_PROVIDER: str = "local"
    STORAGE_LOCAL_ROOT: str = "./storage_data"
    GOOGLE_DRIVE_CREDENTIALS_PATH: str = ""
    GOOGLE_DRIVE_ROOT_FOLDER_ID: str = ""

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
    # Family 11 - communication search scans free-text across several
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
    # shared across processes). See app/core/rate_limit.py.
    RATE_LIMIT_BACKEND: str = "memory"

    # Storage provider selection (Family 17.1) - "local" is the only
    # backend actually implemented in this build. A future cloud
    # backend (S3-compatible/Azure Blob/GCS) would be selected here via
    # environment configuration, never hardcoded into business logic.
    STORAGE_PROVIDER: str = "local"

    # Zoho/SAP integration credentials - environment variables only,
    # never stored in the database and never returned in any API
    # response. Empty by default; the adapters treat an empty value as
    # "not configured" and refuse to attempt a live call, rather than
    # send a request with a blank credential.
    ZOHO_API_KEY: str = ""
    ZOHO_API_BASE_URL: str = ""
    SAP_API_KEY: str = ""
    SAP_API_BASE_URL: str = ""
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Third-party (optional) ---
    OPENAI_API_KEY: str = ""
    EMAIL_USER: str = ""
    EMAIL_PASSWORD: str = ""
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
        return self

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
