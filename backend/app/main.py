"""
FastAPI Application Entry Point for Woodful Creations
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.database import Base, engine

from app.api.routes import auth
from app.api.routes import inventory
from app.api.routes import dashboard
from app.api.routes import client
from app.api.routes import client_project
from app.api.routes import attendance
from app.api.routes import employee
from app.api.routes import estimate
from app.api.routes import interview
from app.api.routes import payment
from app.api.routes import candidate
from app.api.routes import chat
from app.api.routes import salary_slip

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
    allow_origins=settings.ALLOWED_ORIGINS,
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

app.include_router(auth.router)
app.include_router(inventory.router)
app.include_router(dashboard.router)
app.include_router(client.router)
app.include_router(client_project.router)
app.include_router(attendance.router)
app.include_router(employee.router)
app.include_router(estimate.router)
app.include_router(interview.router)
app.include_router(payment.router)
app.include_router(candidate.router)
app.include_router(chat.router)
app.include_router(salary_slip.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)