"""
Woodful Creations - Backend Application
Main entry point for FastAPI application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import routers (to be created)
# from app.routes import stock, clients, estimates, attendance, interviews, payments, auth, chat

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    logger.info("Starting Woodful Creations Backend...")
    yield
    logger.info("Shutting down Woodful Creations Backend...")

# Initialize FastAPI application
app = FastAPI(
    title="Woodful Creations API",
    description="Complete business management system for Woodful Creations",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure trusted hosts
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1"]
)

# Include routers
# app.include_router(stock.router, prefix="/api/stock", tags=["Stock"])
# app.include_router(clients.router, prefix="/api/clients", tags=["Clients"])
# app.include_router(estimates.router, prefix="/api/estimates", tags=["Estimates"])
# app.include_router(attendance.router, prefix="/api/attendance", tags=["Attendance"])
# app.include_router(interviews.router, prefix="/api/interviews", tags=["Interviews"])
# app.include_router(payments.router, prefix="/api/payments", tags=["Payments"])
# app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
# app.include_router(chat.router, prefix="/api/chat", tags=["Chat"])

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Woodful Creations API",
        "version": "1.0.0",
        "status": "running"
    }

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "Woodful Creations Backend"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )
