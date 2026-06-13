import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    APP_NAME = "Woodful Creations"
    APP_VERSION = "2.0.0"
    DEBUG = os.getenv("DEBUG", "True") == "True"
    SECRET_KEY = os.getenv("SECRET_KEY", "woodful-secret-key-change-in-production")
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./woodful.db")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    API_HOST = os.getenv("API_HOST", "0.0.0.0")
    API_PORT = int(os.getenv("API_PORT", "8000"))
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    JWT_ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

settings = Settings()