"""
Application settings.

All values are read from environment variables (see .env.example).
No secret ever ships with a hardcoded default in production mode -
SECRET_KEY and DATABASE_URL must be supplied via the environment.
"""
from functools import lru_cache
from typing import List

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

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
    CORS_ORIGINS: List[str] = ["http://localhost:3000"]

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
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "xlsx", "docx", "jpg", "png", "jpeg"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def split_cors_origins(cls, v):
        # Accept either a plain comma-separated string (CORS_ORIGINS=a,b,c)
        # or a JSON array (CORS_ORIGINS=["a","b","c"]) - comma-separated is
        # what most people type into a .env file by hand.
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                return v  # let pydantic's normal JSON parsing handle it
            return [origin.strip() for origin in stripped.split(",") if origin.strip()]
        return v

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
