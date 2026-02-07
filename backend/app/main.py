from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.database import init_db
from app.api import api_router
from app.services import scheduler_service

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    init_db()
    scheduler_service.start()
    print("🚀 Application started")

    yield

    # Shutdown
    scheduler_service.shutdown()
    print("👋 Application shutdown")


app = FastAPI(
    title=settings.app_name,
    description="Demo & Self-Review Generator API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - allow frontend URL dynamically
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    settings.frontend_url,
]
# Remove duplicates and empty strings
allowed_origins = list(set(filter(None, allowed_origins)))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(api_router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "scheduler": "running" if scheduler_service.scheduler.running else "stopped"
    }