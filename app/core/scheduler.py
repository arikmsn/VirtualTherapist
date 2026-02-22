"""
APScheduler instance for scheduled message delivery.

Uses the AsyncIOScheduler (integrates with FastAPI's async loop) backed by a
SQLAlchemy jobstore so scheduled jobs persist across server restarts.

Usage:
    from app.core.scheduler import scheduler

    # Start/stop are wired in app/main.py startup/shutdown events.
    # To schedule a one-shot job:
    scheduler.add_job(
        deliver_scheduled_message,
        trigger="date",
        run_date=send_at,
        args=[message_id],
        id=f"msg_{message_id}",
        replace_existing=True,
    )
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from app.core.config import settings

_jobstore = SQLAlchemyJobStore(url=settings.DATABASE_URL)

scheduler = AsyncIOScheduler(
    jobstores={"default": _jobstore},
    job_defaults={
        "coalesce": True,       # Merge missed executions into one
        "max_instances": 1,     # Never run the same job concurrently
        "misfire_grace_time": 3600,  # Still send if up to 1 hr late (server was down)
    },
    timezone="Asia/Jerusalem",
)
