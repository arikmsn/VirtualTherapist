"""
Internal admin/maintenance endpoints.

Mounted at /api/admin — always available (not gated by ENVIRONMENT).
ALL endpoints require the X-Admin-Secret header to match the ADMIN_SECRET
env var.  If ADMIN_SECRET is not configured the endpoints return 503.

These are for maintainer use only (not exposed in public docs).
"""

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

def _admin_auth(x_admin_secret: str = Header(...)):
    if not settings.ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin endpoints are not configured on this server (ADMIN_SECRET not set)",
        )
    if x_admin_secret != settings.ADMIN_SECRET:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid admin secret",
        )


# ---------------------------------------------------------------------------
# GET /api/admin/therapist?email=...  — check account state
# ---------------------------------------------------------------------------

@router.get("/therapist", dependencies=[Depends(_admin_auth)])
async def check_therapist(email: str, db: Session = Depends(get_db)):
    """Return full DB state for a therapist by email."""
    row = db.execute(
        text("SELECT id, full_name, auth_provider, google_sub FROM therapists WHERE email = :email"),
        {"email": email},
    ).fetchone()

    if not row:
        return {"exists": False, "email": email}

    tid = row[0]
    profile = db.execute(
        text(
            "SELECT onboarding_completed, onboarding_step "
            "FROM therapist_profiles WHERE therapist_id = :tid"
        ),
        {"tid": tid},
    ).fetchone()

    patient_count = db.execute(
        text("SELECT COUNT(*) FROM patients WHERE therapist_id = :tid"), {"tid": tid}
    ).scalar()

    return {
        "exists": True,
        "email": email,
        "id": tid,
        "full_name": row[1],
        "auth_provider": row[2],
        "google_sub": bool(row[3]),  # don't echo the actual sub
        "profile": {
            "onboarding_completed": bool(profile[0]) if profile else None,
            "onboarding_step": profile[1] if profile else None,
        } if profile else None,
        "patient_count": patient_count,
    }


# ---------------------------------------------------------------------------
# POST /api/admin/therapist/delete?email=...  — delete account
# ---------------------------------------------------------------------------

@router.post("/therapist/delete", dependencies=[Depends(_admin_auth)])
async def delete_therapist(email: str, db: Session = Depends(get_db)):
    """
    Delete a therapist and all related data by email.
    Uses the same FK-safe deletion order as scripts/delete_therapist.py.
    """
    tid = db.execute(
        text("SELECT id FROM therapists WHERE email = :email"), {"email": email}
    ).scalar()

    if tid is None:
        return {"deleted": False, "email": email, "reason": "not found"}

    deleted: dict[str, int] = {}

    def _del(table: str, where: str, params: dict) -> int:
        try:
            n = db.execute(text(f"DELETE FROM {table} WHERE {where}"), params).rowcount
            if n:
                deleted[table] = n
            return n
        except Exception as exc:
            msg = str(exc).lower()
            if "no such table" in msg or "does not exist" in msg or "relation" in msg:
                return 0
            raise

    # 1. exercises (not in ORM cascade)
    _del("exercises", "therapist_id = :tid", {"tid": tid})

    # 2. null sessions.summary_id before deleting session_summaries
    summary_ids = [
        r[0]
        for r in db.execute(
            text("SELECT summary_id FROM sessions WHERE therapist_id = :tid AND summary_id IS NOT NULL"),
            {"tid": tid},
        ).fetchall()
    ]
    if summary_ids:
        db.execute(
            text("UPDATE sessions SET summary_id = NULL WHERE therapist_id = :tid"),
            {"tid": tid},
        )

    # 3. session_summaries (orphaned after sessions are updated)
    if summary_ids:
        id_list = ", ".join(str(i) for i in summary_ids)
        n = db.execute(text(f"DELETE FROM session_summaries WHERE id IN ({id_list})")).rowcount
        if n:
            deleted["session_summaries"] = n

    # 4-9. remaining tables in FK-safe order
    _del("sessions",          "therapist_id = :tid", {"tid": tid})
    _del("messages",          "therapist_id = :tid", {"tid": tid})
    _del("patient_notes",     "therapist_id = :tid", {"tid": tid})
    _del("therapist_notes",   "therapist_id = :tid", {"tid": tid})
    _del("patients",          "therapist_id = :tid", {"tid": tid})
    _del("therapist_profiles","therapist_id = :tid", {"tid": tid})
    _del("therapists",        "id = :tid",           {"tid": tid})

    db.commit()

    return {
        "deleted": True,
        "email": email,
        "id": tid,
        "rows_deleted": deleted,
    }
