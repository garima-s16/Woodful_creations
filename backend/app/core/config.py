"""
Application settings.

All values are read from environment variables (see .env.example).
No secret ever ships with a hardcoded default in production mode -
SECRET_KEY and DATABASE_URL must be supplied via the environment.
"""
from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import field_validator
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

    # --- Rate limiting ---
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 5
    RATE_LIMIT_DEFAULT_PER_MINUTE: int = 120

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

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
