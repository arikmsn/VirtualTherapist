"""
Main FastAPI application
TherapyCompanion.AI - Virtual Therapist Assistant
"""


import traceback
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.api.routes import auth, agent, messages, patients, sessions, therapist, debug, exercises, admin
from app.api.routes import formal_records, treatment_plans, deep_summaries, ui_affordances, eval as eval_routes
from app.api.routes import admin_panel
from app.core.scheduler import scheduler
from app.services.message_service import deliver_due_scheduled_messages
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
# Origins come from CORS_ORIGINS env var (comma-separated list of exact origins).
# For multiple domains set: CORS_ORIGINS="https://a.vercel.app,https://app.metapel.online"
# Alternatively use CORS_ORIGIN_REGEX for a regex pattern covering multiple origins.
_cors_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
_cors_kwargs: dict = dict(
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if settings.CORS_ORIGIN_REGEX:
    _cors_kwargs["allow_origin_regex"] = settings.CORS_ORIGIN_REGEX
app.add_middleware(CORSMiddleware, **_cors_kwargs)


# ── System error middleware — catches unhandled 500s → admin_alerts ───────────
@app.middleware("http")
async def system_error_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as exc:
        tb = traceback.format_exc()[:1000]
        msg = f"{type(exc).__name__}: {str(exc)[:200]}\n\nPath: {request.url.path}\n\n{tb}"
        try:
            from app.core.database import SessionLocal
            from app.utils.alerts import create_alert
            db = SessionLocal()
            try:
                create_alert(db, "system_error", msg)
                db.commit()
            finally:
                db.close()
        except Exception:
            pass
        logger.exception(f"Unhandled 500 at {request.url.path}: {exc!r}")
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Include routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(agent.router, prefix="/api/v1/agent", tags=["AI Agent"])
app.include_router(messages.router, prefix="/api/v1/messages", tags=["Messages"])
app.include_router(patients.router, prefix="/api/v1/patients", tags=["Patients"])
app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["Sessions"])
app.include_router(therapist.router, prefix="/api/v1/therapist", tags=["Therapist Profile"])
app.include_router(exercises.router, prefix="/api/v1/exercises", tags=["Exercises"])
app.include_router(formal_records.router, prefix="/api/v1", tags=["Formal Records"])
app.include_router(treatment_plans.router, prefix="/api/v1", tags=["Treatment Plans"])
app.include_router(deep_summaries.router, prefix="/api/v1", tags=["Deep Summaries"])
app.include_router(ui_affordances.router, prefix="/api/v1", tags=["UI Affordances"])
app.include_router(eval_routes.router, prefix="/api/v1", tags=["Evaluation"])

# Debug routes — only in development / staging (never production)
if settings.ENVIRONMENT != "production":
    app.include_router(debug.router, prefix="/api/debug", tags=["Debug"])

# Admin maintenance routes — always mounted, protected by X-Admin-Secret header.
# Set ADMIN_SECRET env var to enable; leave unset to get 503 on all admin calls.
if settings.ADMIN_SECRET:
    app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])

# Admin panel — always mounted, protected by admin JWT (is_admin=True claim).
app.include_router(admin_panel.router, prefix="/api/v1/admin-panel", tags=["Admin Panel"])


def _check_inactive_therapists():
    """Daily job: create inactive_therapist alerts for therapists idle > 30 days."""
    try:
        from datetime import timedelta
        from app.core.database import SessionLocal
        from app.models.therapist import Therapist
        from app.utils.alerts import create_alert
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(days=30)
            idle = (
                db.query(Therapist)
                .filter(
                    Therapist.is_active == True,
                    Therapist.is_blocked == False,
                    Therapist.last_login < cutoff,
                )
                .all()
            )
            for t in idle:
                create_alert(
                    db,
                    "inactive_therapist",
                    f"מטפל/ת {t.full_name} ({t.email}) לא התחבר/ה כבר 30+ יום",
                    therapist_id=t.id,
                    deduplicate_today=True,
                )
            db.commit()
            logger.info(f"[inactive_check] {len(idle)} inactive therapists checked")
        finally:
            db.close()
    except Exception as exc:
        logger.warning(f"_check_inactive_therapists failed (non-blocking): {exc!r}")


@app.on_event("startup")
async def startup_event():
    """Startup event handler"""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")

    # Auto-resolve latest Anthropic model IDs — falls back to config if API unreachable
    from app.ai.model_registry import resolve_models
    await resolve_models(settings.ANTHROPIC_API_KEY)

    scheduler.add_job(
        deliver_due_scheduled_messages,
        trigger="interval",
        seconds=30,
        id="poll_scheduled_messages",
        replace_existing=True,
        misfire_grace_time=30,  # absorb short blocking without noisy "missed by" warnings
    )

    scheduler.add_job(
        _check_inactive_therapists,
        trigger="interval",
        hours=24,
        id="check_inactive_therapists",
        replace_existing=True,
    )

    scheduler.start()
    logger.info("APScheduler started — polling for scheduled messages every 30s")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    # Log AI key status (masked)
    anthropic_key = settings.ANTHROPIC_API_KEY
    if anthropic_key and len(anthropic_key) > 8:
        masked = anthropic_key[:4] + "..." + anthropic_key[-4:]
    else:
        masked = "(not set)"
    logger.info(f"AI (Anthropic): {masked} — models: fast={settings.AI_FAST_MODEL}, standard={settings.AI_STANDARD_MODEL}, deep={settings.AI_DEEP_MODEL}")

    # Google OAuth credential status — log presence without printing secrets
    if settings.GOOGLE_CLIENT_ID:
        logger.info(f"Google OAuth: GOOGLE_CLIENT_ID is set ({settings.GOOGLE_CLIENT_ID[:12]}...)")
    else:
        logger.warning("Google OAuth: GOOGLE_CLIENT_ID is NOT set — Google Sign-In will be rejected")
    if settings.GOOGLE_CLIENT_SECRET:
        logger.info("Google OAuth: GOOGLE_CLIENT_SECRET is set")
    else:
        logger.warning("Google OAuth: GOOGLE_CLIENT_SECRET is NOT set — Google Sign-In will be rejected")

    # Auto-create tables in development (for SQLite or fresh databases)
    if settings.ENVIRONMENT == "development":
        from app.core.database import engine
        from app.models.base import Base
        from app.models import (  # noqa: F401
            Therapist, TherapistProfile, TherapistNote, Patient, Session,
            SessionSummary, Message, AuditLog, Exercise, PatientNote,
        )
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created/verified")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown event handler"""
    scheduler.shutdown(wait=False)
    logger.info(f"Shutting down {settings.APP_NAME}")


@app.get("/health")
async def health_check():
    """Health check endpoint — lightweight, no DB query."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }
