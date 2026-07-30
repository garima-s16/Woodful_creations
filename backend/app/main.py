"""
FastAPI Application Entry Point for Woodful Creations
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from app.core.config import settings
from app.core.database import Base, engine

# Import all models so SQLAlchemy registers their tables against Base
import app.models.user  # noqa: F401
import app.models.product  # noqa: F401
import app.models.client  # noqa: F401
import app.models.employee  # noqa: F401
import app.models.payment  # noqa: F401
import app.models.attendance  # noqa: F401
import app.models.client_project  # noqa: F401
import app.models.estimate  # noqa: F401
import app.models.candidate  # noqa: F401
import app.models.interview  # noqa: F401
import app.models.salary_slip  # noqa: F401

from app.api.routes import auth, inventory, dashboard, chat, employee, attendance
from app.api.routes import payment, client_project, estimate, candidate, interview, salary_slip
from app.api.routes import client as client_router

app = FastAPI(
    title=settings.APP_NAME,
    description="Management system for Woodful Creations",
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

Base.metadata.create_all(bind=engine)

allowed_origins = settings.ALLOWED_ORIGINS if settings.ALLOWED_ORIGINS else ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/", tags=["Health"])
async def root():
    """API root endpoint."""
    return {
        "message": "Woodful Creations API",
        "version": settings.APP_VERSION,
        "status": "running"
    }


@app.get("/api/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


# Authentication
app.include_router(auth.router)

# Inventory
app.include_router(inventory.router)

# Dashboard
app.include_router(dashboard.router)

# Chat
app.include_router(chat.router)

# HR
app.include_router(employee.router)
app.include_router(attendance.router)
app.include_router(salary_slip.router)
app.include_router(candidate.router)
app.include_router(interview.router)

# Finance
app.include_router(payment.router)

# Clients and Projects
app.include_router(client_router.router)
app.include_router(client_project.router)

# Estimates
app.include_router(estimate.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)