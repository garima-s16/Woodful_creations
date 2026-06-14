"""
Application Configuration Settings
"""
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application Settings from environment variables"""
    
    APP_NAME: str = "Woodful Creations"
    APP_VERSION: str = "2.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    DATABASE_URL: str = "postgresql://woodful_user:password@localhost:5432/woodful_creations"
    
    SERVER_HOST: str = "0.0.0.0"
    SERVER_PORT: int = 8000
    
    SECRET_KEY: str = "your_secret_key_change_in_production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SENDER_EMAIL: str = "your_email@gmail.com"
    SENDER_PASSWORD: str = "your_app_password"
    SENDER_NAME: str = "Woodful Creations"
    
    OPENAI_API_KEY: Optional[str] = None
    REDIS_URL: str = "redis://localhost:6379"
    
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://localhost:8000"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()