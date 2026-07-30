"""
Application Configuration Settings
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List


class Settings(BaseSettings):
    """Application Settings from environment variables"""

    APP_NAME: str = "Woodful Creations"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "sqlite:///./woodful.db"

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    SECRET_KEY: str = "change-this-secret-key-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SENDER_EMAIL: str = ""
    SENDER_PASSWORD: str = ""
    SENDER_NAME: str = "Woodful Creations"

    OPENAI_API_KEY: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379"

    # Comma-separated list of allowed CORS origins.
    # For cross-platform support (web + mobile), set this to your deployed domain(s)
    # and the IP/hostname your mobile clients use to reach the API.
    # Example: "https://app.woodfulcreations.com,http://192.168.1.10:3000"
    ALLOWED_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
