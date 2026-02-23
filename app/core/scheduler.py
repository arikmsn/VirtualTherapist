"""
APScheduler instance for periodic scheduled-message delivery.

Architecture
------------
A single interval job (poll_scheduled_messages) runs every 30 seconds and
calls deliver_due_scheduled_messages(), which queries the DB for every
Message whose status='scheduled' AND scheduled_send_at <= now_utc and
delivers them via the normal deliver_message() path.

This keeps the DB as the **single source of truth** — no per-message
APScheduler jobs are registered, no SQLAlchemy jobstore is required, and
no asyncio.run() hacks are needed.  Cancelling a scheduled message is just
setting status='cancelled' in the DB; the poller will skip it.

The polling job is registered in app/main.py startup_event().
"""

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(
    job_defaults={
        "coalesce": True,      # merge missed executions into one
        "max_instances": 1,    # never run the same job concurrently
    },
    timezone="UTC",
)
