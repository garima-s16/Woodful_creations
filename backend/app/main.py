"""
FastAPI application entry point for Woodful Creations.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import routes
from app.core.config import settings
from app.core.database import Base, engine

app = FastAPI(
    title=settings.APP_NAME,
    description="AI-powered management system for Woodful Creations",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
)

Base.metadata.create_all(bind=engine)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
async def root():
    return {"message": "Woodful Creations API", "version": settings.APP_VERSION, "status": "running"}


@app.get("/api/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}


app.include_router(routes.auth.router)
app.include_router(routes.users.router)
app.include_router(routes.inventory.router)
