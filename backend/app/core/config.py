"""
Application Configuration Settings
"""
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    APP_NAME: str = "Woodful Creations"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    DATABASE_URL: str = "sqlite:///./woodful_creations.db"

    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000

    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SENDER_EMAIL: str = "your_email@gmail.com"
    SENDER_PASSWORD: str = "your_app_password"
    SENDER_NAME: str = "Woodful Creations"

    OPENAI_API_KEY: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379"

    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
        "http://localhost:8081",
    ]


settings = Settings()
