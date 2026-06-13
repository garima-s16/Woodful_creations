from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

def create_app():
    app = FastAPI(
        title="Woodful Creations API",
        description="AI-powered business management system for wood and furniture business",
        version="2.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc"
    )
    return app