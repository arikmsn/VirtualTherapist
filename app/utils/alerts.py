"""Reusable helper for creating AdminAlert records.

Usage:
    from app.utils.alerts import create_alert
    create_alert(db, "new_signup", "...", therapist_id=42)

All calls are best-effort — they never raise.
"""

from datetime import datetime, date
from sqlalchemy.orm import Session


def create_alert(
    db: Session,
    alert_type: str,
    message: str,
    therapist_id: int | None = None,
    *,
    deduplicate_today: bool = False,
) -> None:
    """
    Insert an AdminAlert row.

    If deduplicate_today=True, skip insertion if an alert of the same type
    for the same therapist_id already exists today (UTC). Used for daily jobs
    like inactive_therapist and high_usage.
    """
    try:
        from app.models.admin_alert import AdminAlert

        if deduplicate_today:
            today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            exists = (
                db.query(AdminAlert)
                .filter(
                    AdminAlert.type == alert_type,
                    AdminAlert.therapist_id == therapist_id,
                    AdminAlert.created_at >= today_start,
                )
                .first()
            )
            if exists:
                return

        alert = AdminAlert(
            type=alert_type,
            message=message,
            therapist_id=therapist_id,
        )
        db.add(alert)
        db.flush()
    except Exception:
        pass  # never raise — alerts are always non-blocking
