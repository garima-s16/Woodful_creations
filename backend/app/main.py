"""
FastAPI Application Entry Point for Woodful Creations
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os

from app.core.config import settings
from app.core.database import Base, engine
from app.api import routes

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered management system for Woodful Creations",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/", tags=["Health"])
async def root():
    """API Root endpoint"""
    return {
        "message": "Woodful Creations API",
        "version": settings.APP_VERSION,
        "status": "running"
    }

@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

app.include_router(routes.auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(routes.users.router, prefix="/api/users", tags=["Users"])
app.include_router(routes.inventory.router, prefix="/api/inventory", tags=["Inventory"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)