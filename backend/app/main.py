"""
Woodful Creations - Main FastAPI Application
AI-powered business management system with stock inventory, estimates, and more
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import logging
from pathlib import Path

# Import routes
from app.routes import auth, inventory, chat, clients, estimates

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Lifespan context
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("🌳 Woodful Creations Starting...")
    from app.database import init_db
    await init_db()
    logger.info("✅ Database initialized")
    yield
    # Shutdown
    logger.info("🛑 Woodful Creations Shutting Down...")

# Create FastAPI app
app = FastAPI(
    title="Woodful Creations API",
    description="AI-powered business management system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["Inventory"])
app.include_router(chat.router, prefix="/api/chat", tags=["AI Chat"])
app.include_router(clients.router, prefix="/api/clients", tags=["Clients"])
app.include_router(estimates.router, prefix="/api/estimates", tags=["Estimates"])

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "🌳 Welcome to Woodful Creations",
        "version": "1.0.0",
        "docs": "/docs",
        "modules": {
            "inventory": "/api/inventory",
            "chat": "/api/chat",
            "clients": "/api/clients",
            "estimates": "/api/estimates"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "Woodful Creations API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)