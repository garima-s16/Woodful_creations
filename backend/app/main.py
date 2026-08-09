"""
FastAPI application entry point for Woodful Creations.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine
from app.models import sales_order  # register new tables with Base

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


from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.api.routes.inventory import router as inventory_router
from app.api.routes.sales import router as sales_router
from app.api.routes.reports import router as reports_router
from app.api.routes.dashboard import router as dashboard_router

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(inventory_router)
app.include_router(sales_router)
app.include_router(reports_router)
app.include_router(dashboard_router)
