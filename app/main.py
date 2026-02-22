"""
Main FastAPI application
TherapyCompanion.AI - Virtual Therapist Assistant
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import auth, agent, messages, patients, sessions, therapist, debug, exercises
from app.core.scheduler import scheduler
from loguru import logger


# Configure logger
logger.add(
    settings.LOG_FILE,
    rotation="500 MB",
    retention="30 days",
    level=settings.LOG_LEVEL
)


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-powered virtual therapist assistant",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["AI Agent"])
app.include_router(messages.router, prefix="/api/v1/messages", tags=["Messages"])
app.include_router(patients.router, prefix="/api/v1/patients", tags=["Patients"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(therapist.router, prefix="/api/v1/therapist", tags=["Therapist Profile"])
app.include_router(exercises.router, prefix="/api/v1/exercises", tags=["Exercises"])

# Debug routes — only in development / staging (never production)
if settings.ENVIRONMENT != "production":
    app.include_router(debug.router, prefix="/api/debug", tags=["Debug"])


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    scheduler.start()
    logger.info("APScheduler started (scheduled message delivery active)")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"AI Provider: {settings.AI_PROVIDER}")

    # Log masked AI key status
    key_field = "ANTHROPIC_API_KEY" if settings.AI_PROVIDER == "anthropic" else "OPENAI_API_KEY"
    key_value = getattr(settings, key_field)
    if key_value and len(key_value) > 8:
        masked = key_value[:4] + "..." + key_value[-4:]
    else:
        masked = "(not set)"
    logger.info(f"AI Key ({key_field}): {masked}")

    # Auto-create tables in development (for SQLite or fresh databases)
    if settings.ENVIRONMENT == "development":
        from app.core.database import engine
        from app.models.base import Base
        from app.models import (  # noqa: F401
            Therapist, TherapistProfile, Patient, Session,
            SessionSummary, Message, AuditLog, Exercise,
        )
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    scheduler.shutdown(wait=False)
    logger.info(f"Shutting down {settings.APP_NAME}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "environment": settings.ENVIRONMENT
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG
    )
