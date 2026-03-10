"""Admin Panel API routes — protected by admin JWT."""

import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Header, Query
from jose import JWTError, jwt
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func, text
from sqlalchemy.orm import Session as DBSession

from app.api.deps import get_db
from app.core.config import settings
from app.models.admin_alert import AdminAlert
from app.models.therapist import Therapist
from app.models.ai_log import AIGenerationLog
from app.utils.alerts import create_alert

router = APIRouter()


# ── Admin JWT dependency ──────────────────────────────────────────────────────

def get_admin_therapist(
    authorization: str = Header(...),
    db: DBSession = Depends(get_db),
) -> Therapist:
    """Validate the admin JWT and return the therapist row."""
    token = authorization.removeprefix("Bearer ").strip()
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        if not payload.get("is_admin"):
            raise HTTPException(status_code=403, detail="Not an admin token")
        therapist_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid admin token")

    therapist = db.query(Therapist).filter(Therapist.id == therapist_id).first()
    if not therapist or not therapist.is_admin:
        raise HTTPException(status_code=403, detail="Forbidden")
    return therapist


# ── Helpers ───────────────────────────────────────────────────────────────────

def _infer_usage_type(model_used: str | None) -> str:
    """Derive usage_type from model name for backward-compatible rows."""
    if not model_used:
        return "text_openai"
    m = model_used.lower()
    if "whisper" in m or "transcri" in m:
        return "transcription"
    if "claude" in m:
        return "text_claude"
    return "text_openai"


# ── Response schemas ──────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_therapists: int
    active_last_30_days: int
    total_ai_calls: int
    total_tokens: int
    unread_alerts: int
    new_signups_last_7_days: int


class SignupWeek(BaseModel):
    week_label: str
    count: int


class TokenTypeCard(BaseModel):
    usage_type: str
    calls: int
    tokens: int
    cost_usd: float


class DashboardExtended(BaseModel):
    stats: DashboardStats
    signup_by_week: List[SignupWeek]
    token_by_type: List[TokenTypeCard]
    token_by_day_stacked: List[Dict[str, Any]]


class TherapistRow(BaseModel):
    id: int
    email: str
    full_name: str
    is_active: bool
    is_admin: bool
    is_blocked: bool
    last_login: Optional[datetime]
    created_at: datetime
    session_count: int
    ai_call_count: int
    active_patients: int
    intended_plan: Optional[str] = None


class AlertRow(BaseModel):
    id: int
    type: str
    message: str
    therapist_id: Optional[int]
    therapist_name: Optional[str]
    is_read: bool
    created_at: datetime


class UsageDay(BaseModel):
    date: str
    calls: int
    tokens: int
    text_claude_calls: int
    text_openai_calls: int
    transcription_calls: int
    text_claude_tokens: int
    text_openai_tokens: int
    transcription_tokens: int


class UsageTypeStats(BaseModel):
    usage_type: str
    calls: int
    tokens: int
    cost_usd: float


class UsageStats(BaseModel):
    by_day: List[UsageDay]
    by_flow: List[Dict[str, Any]]
    by_model: List[Dict[str, Any]]
    by_type: List[UsageTypeStats]
    total_calls: int
    total_tokens: int


# ── Token cost estimation ─────────────────────────────────────────────────────

# Approximate costs per 1K tokens (blended prompt+completion)
_COST_PER_1K: Dict[str, float] = {
    "text_claude": 0.003,
    "text_openai": 0.002,
    "transcription": 0.006,
}


def _estimate_cost(tokens: int, usage_type: str) -> float:
    rate = _COST_PER_1K.get(usage_type, 0.002)
    return round(tokens / 1000 * rate, 4)


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_model=DashboardExtended)
def admin_dashboard(
    admin: Therapist = Depends(get_admin_therapist),
    db: DBSession = Depends(get_db),
):
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    twelve_weeks_ago = datetime.utcnow() - timedelta(weeks=12)
    seven_days_ago_dt = datetime.utcnow() - timedelta(days=7)

    total_therapists = db.query(func.count(Therapist.id)).scalar() or 0
    active_last_30 = (
        db.query(func.count(Therapist.id))
        .filter(Therapist.last_login >= thirty_days_ago)
        .scalar() or 0
    )
    total_ai_calls = db.query(func.count(AIGenerationLog.id)).scalar() or 0
    total_tokens = db.query(
        func.coalesce(
            func.sum(AIGenerationLog.prompt_tokens + AIGenerationLog.completion_tokens), 0
        )
    ).scalar() or 0
    unread_alerts = (
        db.query(func.count(AdminAlert.id))
        .filter(AdminAlert.is_read == False)  # noqa: E712
        .scalar() or 0
    )
    new_signups = (
        db.query(func.count(Therapist.id))
        .filter(Therapist.created_at >= seven_days_ago)
        .scalar() or 0
    )

    stats = DashboardStats(
        total_therapists=total_therapists,
        active_last_30_days=active_last_30,
        total_ai_calls=total_ai_calls,
        total_tokens=int(total_tokens),
        unread_alerts=unread_alerts,
        new_signups_last_7_days=new_signups,
    )

    # ── Signups by week (last 12 weeks) ───────────────────────────────────
    therapists_12w = (
        db.query(Therapist)
        .filter(Therapist.created_at >= twelve_weeks_ago)
        .all()
    )
    week_map: Dict[int, int] = {}
    for t in therapists_12w:
        week_num = (datetime.utcnow() - t.created_at).days // 7
        week_num = min(week_num, 11)  # cap at 12 weeks
        week_map[week_num] = week_map.get(week_num, 0) + 1

    signup_by_week: List[SignupWeek] = []
    for w in range(11, -1, -1):
        week_start = datetime.utcnow() - timedelta(weeks=w + 1)
        label = week_start.strftime("%-d %b") if hasattr(week_start, 'strftime') else week_start.strftime("%d/%m")
        try:
            label = week_start.strftime("%-d %b")
        except ValueError:
            label = week_start.strftime("%d/%m")
        signup_by_week.append(SignupWeek(week_label=label, count=week_map.get(w, 0)))

    # ── Token breakdown by type (this month) ─────────────────────────────
    month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_logs = (
        db.query(AIGenerationLog)
        .filter(AIGenerationLog.created_at >= month_start)
        .all()
    )
    type_agg: Dict[str, Dict[str, int]] = {
        "text_claude": {"calls": 0, "tokens": 0},
        "text_openai": {"calls": 0, "tokens": 0},
        "transcription": {"calls": 0, "tokens": 0},
    }
    for log in month_logs:
        ut = log.usage_type or _infer_usage_type(log.model_used)
        if ut not in type_agg:
            ut = "text_openai"
        type_agg[ut]["calls"] += 1
        type_agg[ut]["tokens"] += (log.prompt_tokens or 0) + (log.completion_tokens or 0)

    token_by_type = [
        TokenTypeCard(
            usage_type=ut,
            calls=v["calls"],
            tokens=v["tokens"],
            cost_usd=_estimate_cost(v["tokens"], ut),
        )
        for ut, v in type_agg.items()
    ]

    # ── Stacked by type — last 7 days ─────────────────────────────────────
    recent_logs = (
        db.query(AIGenerationLog)
        .filter(AIGenerationLog.created_at >= seven_days_ago_dt)
        .all()
    )
    day_stacked: Dict[str, Dict[str, int]] = {}
    for log in recent_logs:
        day = log.created_at.strftime("%Y-%m-%d")
        ut = log.usage_type or _infer_usage_type(log.model_used)
        if day not in day_stacked:
            day_stacked[day] = {"text_claude": 0, "text_openai": 0, "transcription": 0}
        day_stacked[day][ut] = day_stacked[day].get(ut, 0) + (
            (log.prompt_tokens or 0) + (log.completion_tokens or 0)
        )
    token_by_day_stacked = [
        {"date": d, **v} for d, v in sorted(day_stacked.items())
    ]

    return DashboardExtended(
        stats=stats,
        signup_by_week=signup_by_week,
        token_by_type=token_by_type,
        token_by_day_stacked=token_by_day_stacked,
    )


@router.get("/therapists", response_model=List[TherapistRow])
def list_therapists(
    admin: Therapist = Depends(get_admin_therapist),
    db: DBSession = Depends(get_db),
    intended_plan: Optional[str] = Query(None, description="Filter by intended_plan value (e.g. 'pro')"),
):
    query = db.query(Therapist)
    if intended_plan is not None:
        query = query.filter(Therapist.intended_plan == intended_plan)
    therapists = query.order_by(Therapist.created_at.desc()).all()
    result = []
    for t in therapists:
        try:
            from app.models.session import Session as TherapySession
            session_count = (
                db.query(func.count(TherapySession.id))
                .filter(TherapySession.therapist_id == t.id)
                .scalar() or 0
            )
        except Exception:
            session_count = 0

        try:
            from app.models.patient import Patient, PatientStatus
            active_patients = (
                db.query(func.count(Patient.id))
                .filter(
                    Patient.therapist_id == t.id,
                    Patient.status == PatientStatus.ACTIVE.value,
                )
                .scalar() or 0
            )
        except Exception:
            active_patients = 0

        ai_count = (
            db.query(func.count(AIGenerationLog.id))
            .filter(AIGenerationLog.therapist_id == t.id)
            .scalar() or 0
        )
        result.append(TherapistRow(
            id=t.id,
            email=t.email,
            full_name=t.full_name,
            is_active=bool(t.is_active),
            is_admin=bool(t.is_admin),
            is_blocked=bool(t.is_blocked),
            last_login=t.last_login,
            created_at=t.created_at,
            session_count=session_count,
            ai_call_count=ai_count,
            active_patients=active_patients,
            intended_plan=t.intended_plan,
        ))
    return result


class BlockRequest(BaseModel):
    is_blocked: bool


@router.patch("/therapists/{therapist_id}/block", response_model=TherapistRow)
def block_therapist(
    therapist_id: int,
    body: BlockRequest,
    admin: Therapist = Depends(get_admin_therapist),
    db: DBSession = Depends(get_db),
):
    if therapist_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot block yourself")

    t = db.query(Therapist).filter(Therapist.id == therapist_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Therapist not found")

    t.is_blocked = body.is_blocked
    db.commit()
    db.refresh(t)

    # Log alert
    try:
        action = "הושהה" if body.is_blocked else "שוחרר מהשהיה"
        alert_type = "blocked_therapist" if body.is_blocked else "unblocked"
        create_alert(
            db,
            alert_type,
            f"מטפל/ת {t.full_name} ({t.email}) {action} על ידי אדמין",
            therapist_id=t.id,
        )
        db.commit()
    except Exception:
        pass

    try:
        from app.models.session import Session as TherapySession
        session_count = db.query(func.count(TherapySession.id)).filter(TherapySession.therapist_id == t.id).scalar() or 0
    except Exception:
        session_count = 0

    try:
        from app.models.patient import Patient, PatientStatus
        active_patients = (
            db.query(func.count(Patient.id))
            .filter(Patient.therapist_id == t.id, Patient.status == PatientStatus.ACTIVE.value)
            .scalar() or 0
        )
    except Exception:
        active_patients = 0

    ai_count = db.query(func.count(AIGenerationLog.id)).filter(AIGenerationLog.therapist_id == t.id).scalar() or 0

    return TherapistRow(
        id=t.id, email=t.email, full_name=t.full_name,
        is_active=bool(t.is_active), is_admin=bool(t.is_admin), is_blocked=bool(t.is_blocked),
        last_login=t.last_login, created_at=t.created_at,
        session_count=session_count, ai_call_count=ai_count, active_patients=active_patients,
        intended_plan=t.intended_plan,
    )


@router.get("/usage", response_model=UsageStats)
def admin_usage(
    days: int = 30,
    admin: Therapist = Depends(get_admin_therapist),
    db: DBSession = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(days=days)
    logs = (
        db.query(AIGenerationLog)
        .filter(AIGenerationLog.created_at >= since)
        .order_by(AIGenerationLog.created_at.asc())
        .all()
    )

    # By day with usage_type split
    day_map: Dict[str, Dict] = {}
    for log in logs:
        day = log.created_at.strftime("%Y-%m-%d")
        ut = log.usage_type or _infer_usage_type(log.model_used)
        tokens = (log.prompt_tokens or 0) + (log.completion_tokens or 0)
        if day not in day_map:
            day_map[day] = {
                "date": day, "calls": 0, "tokens": 0,
                "text_claude_calls": 0, "text_openai_calls": 0, "transcription_calls": 0,
                "text_claude_tokens": 0, "text_openai_tokens": 0, "transcription_tokens": 0,
            }
        day_map[day]["calls"] += 1
        day_map[day]["tokens"] += tokens
        day_map[day][f"{ut}_calls"] = day_map[day].get(f"{ut}_calls", 0) + 1
        day_map[day][f"{ut}_tokens"] = day_map[day].get(f"{ut}_tokens", 0) + tokens

    by_day = [UsageDay(**v) for v in sorted(day_map.values(), key=lambda x: x["date"])]

    # By flow_type
    flow_map: Dict[str, int] = {}
    for log in logs:
        ft = log.flow_type or "unknown"
        flow_map[ft] = flow_map.get(ft, 0) + 1
    by_flow = [{"flow_type": k, "count": v} for k, v in sorted(flow_map.items(), key=lambda x: -x[1])]

    # By model
    model_map: Dict[str, int] = {}
    for log in logs:
        m = log.model_used or "unknown"
        model_map[m] = model_map.get(m, 0) + 1
    by_model = [{"model": k, "count": v} for k, v in sorted(model_map.items(), key=lambda x: -x[1])]

    # By usage_type
    type_agg: Dict[str, Dict[str, int]] = {
        "text_claude": {"calls": 0, "tokens": 0},
        "text_openai": {"calls": 0, "tokens": 0},
        "transcription": {"calls": 0, "tokens": 0},
    }
    for log in logs:
        ut = log.usage_type or _infer_usage_type(log.model_used)
        if ut not in type_agg:
            ut = "text_openai"
        type_agg[ut]["calls"] += 1
        type_agg[ut]["tokens"] += (log.prompt_tokens or 0) + (log.completion_tokens or 0)

    by_type = [
        UsageTypeStats(
            usage_type=ut,
            calls=v["calls"],
            tokens=v["tokens"],
            cost_usd=_estimate_cost(v["tokens"], ut),
        )
        for ut, v in type_agg.items()
    ]

    return UsageStats(
        by_day=by_day,
        by_flow=by_flow,
        by_model=by_model,
        by_type=by_type,
        total_calls=len(logs),
        total_tokens=sum((log.prompt_tokens or 0) + (log.completion_tokens or 0) for log in logs),
    )


@router.get("/alerts", response_model=List[AlertRow])
def list_alerts(
    unread_only: bool = False,
    admin: Therapist = Depends(get_admin_therapist),
    db: DBSession = Depends(get_db),
):
    q = db.query(AdminAlert).order_by(AdminAlert.created_at.desc())
    if unread_only:
        q = q.filter(AdminAlert.is_read == False)  # noqa: E712
    alerts = q.limit(200).all()

    result = []
    for a in alerts:
        therapist_name = None
        if a.therapist_id:
            t = db.query(Therapist).filter(Therapist.id == a.therapist_id).first()
            if t:
                therapist_name = t.full_name
        result.append(AlertRow(
            id=a.id,
            type=a.type,
            message=a.message,
            therapist_id=a.therapist_id,
            therapist_name=therapist_name,
            is_read=bool(a.is_read),
            created_at=a.created_at,
        ))
    return result


@router.patch("/alerts/{alert_id}/read")
def mark_alert_read(
    alert_id: int,
    admin: Therapist = Depends(get_admin_therapist),
    db: DBSession = Depends(get_db),
):
    alert = db.query(AdminAlert).filter(AdminAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.is_read = True
    db.commit()
    return {"ok": True}


@router.patch("/alerts/read-all")
def mark_all_alerts_read(
    admin: Therapist = Depends(get_admin_therapist),
    db: DBSession = Depends(get_db),
):
    db.query(AdminAlert).filter(AdminAlert.is_read == False).update({"is_read": True})  # noqa: E712
    db.commit()
    return {"ok": True}


# ── Delete therapist ──────────────────────────────────────────────────────────

@router.delete("/therapists/{therapist_id}")
def delete_therapist(
    therapist_id: int,
    admin: Therapist = Depends(get_admin_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Permanently delete a therapist and ALL associated data.
    Also attempts to remove the user from Supabase Auth (best-effort).
    """
    if therapist_id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    t = db.query(Therapist).filter(Therapist.id == therapist_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Therapist not found")

    supabase_uid = t.supabase_user_id  # may be None
    therapist_email = t.email

    try:
        from sqlalchemy import text
        tid = therapist_id
        deleted: Dict[str, int] = {}

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

        # Null sessions.summary_id before deleting session_summaries (FK safety)
        summary_ids = [
            r[0]
            for r in db.execute(
                text("SELECT summary_id FROM sessions WHERE therapist_id = :tid AND summary_id IS NOT NULL"),
                {"tid": tid},
            ).fetchall()
        ]
        if summary_ids:
            db.execute(text("UPDATE sessions SET summary_id = NULL WHERE therapist_id = :tid"), {"tid": tid})

        if summary_ids:
            id_list = ", ".join(str(i) for i in summary_ids)
            n = db.execute(text(f"DELETE FROM session_summaries WHERE id IN ({id_list})")).rowcount
            if n:
                deleted["session_summaries"] = n

        _del("exercises",            "therapist_id = :tid", {"tid": tid})
        _del("sessions",             "therapist_id = :tid", {"tid": tid})
        _del("messages",             "therapist_id = :tid", {"tid": tid})
        _del("patient_notes",        "therapist_id = :tid", {"tid": tid})
        _del("therapist_notes",      "therapist_id = :tid", {"tid": tid})
        _del("patients",             "therapist_id = :tid", {"tid": tid})
        _del("therapist_profiles",   "therapist_id = :tid", {"tid": tid})
        _del("admin_alerts",         "therapist_id = :tid", {"tid": tid})
        _del("therapists",           "id = :tid",           {"tid": tid})

        db.commit()
        logger.info(f"[admin_delete] therapist_id={tid} email={therapist_email} deleted={deleted}")

    except Exception as exc:
        db.rollback()
        logger.exception(f"[admin_delete] failed for therapist_id={therapist_id}: {exc!r}")
        raise HTTPException(status_code=500, detail=f"מחיקה נכשלה: {exc}")

    # ── Best-effort: remove from Supabase Auth ────────────────────────────
    supabase_error: Optional[str] = None
    if supabase_uid:
        try:
            from app.core.config import settings as _s
            import httpx
            if _s.SUPABASE_URL and _s.SUPABASE_SERVICE_ROLE_KEY:
                resp = httpx.delete(
                    f"{_s.SUPABASE_URL}/auth/v1/admin/users/{supabase_uid}",
                    headers={
                        "apikey": _s.SUPABASE_SERVICE_ROLE_KEY,
                        "Authorization": f"Bearer {_s.SUPABASE_SERVICE_ROLE_KEY}",
                    },
                    timeout=10,
                )
                if resp.status_code not in (200, 204):
                    supabase_error = f"Supabase: {resp.status_code} {resp.text[:200]}"
                    logger.warning(f"[admin_delete] Supabase deleteUser failed: {supabase_error}")
        except Exception as exc:
            supabase_error = str(exc)
            logger.warning(f"[admin_delete] Supabase deleteUser error: {exc!r}")

    return {
        "deleted": True,
        "therapist_id": therapist_id,
        "email": therapist_email,
        "supabase_user_removed": supabase_uid is not None and supabase_error is None,
        "supabase_error": supabase_error,
    }


# ── Temporary password ────────────────────────────────────────────────────────

_WORD_POOL = [
    "Blue", "Red", "Sky", "Sun", "Oak", "Mint", "Coral", "Gold", "Pine", "Wave",
    "Star", "Rain", "Snow", "Leaf", "Rock", "Sand", "Mist", "Dawn", "Glow", "Jade",
]


def _generate_temp_password() -> str:
    import random
    word1 = secrets.choice(_WORD_POOL)
    word2 = secrets.choice(_WORD_POOL)
    num = secrets.randbelow(9000) + 1000  # 4-digit number
    return f"{word1}-{word2}-{num}"


async def _send_temp_password_email(to_email: str, full_name: str, temp_pw: str) -> None:
    """Send temp password via SendGrid. Raises on failure."""
    from app.core.config import settings as _s
    if not _s.SENDGRID_API_KEY:
        raise RuntimeError("SENDGRID_API_KEY is not configured")

    import sendgrid
    from sendgrid.helpers.mail import Mail

    html_body = f"""
<div dir="rtl" style="font-family: Arial, sans-serif; max-width: 480px; margin: 0 auto; color: #1F2937;">
  <h2 style="color: #4F46E5;">מטפל אונליין</h2>
  <p>שלום {full_name},</p>
  <p>קיבלת סיסמה זמנית לכניסה למערכת <strong>מטפל אונליין</strong>.</p>
  <div style="background: #F3F4F6; border-radius: 8px; padding: 16px; margin: 20px 0; text-align: center;">
    <p style="margin: 0 0 8px 0; font-size: 13px; color: #6B7280;">הסיסמה הזמנית שלך:</p>
    <p style="margin: 0; font-size: 24px; font-weight: bold; font-family: monospace; letter-spacing: 2px; color: #1F2937;">
      {temp_pw}
    </p>
  </div>
  <p>
    <a href="https://app.metapel.online" style="display: inline-block; background: #4F46E5; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none;">
      כניסה למערכת
    </a>
  </p>
  <p style="font-size: 13px; color: #6B7280;">מומלץ לשנות את הסיסמה לאחר הכניסה.</p>
  <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 20px 0;" />
  <p style="font-size: 11px; color: #9CA3AF;">הודעה זו נשלחה על ידי מנהל המערכת של מטפל אונליין.</p>
</div>
"""

    message = Mail(
        from_email=(_s.SENDGRID_FROM_EMAIL, "מטפל אונליין"),
        to_emails=to_email,
        subject="סיסמה זמנית - מטפל אונליין",
        html_content=html_body,
    )

    sg = sendgrid.SendGridAPIClient(api_key=_s.SENDGRID_API_KEY)
    response = sg.send(message)
    if response.status_code not in (200, 202):
        raise RuntimeError(f"SendGrid returned {response.status_code}: {response.body}")


@router.post("/therapists/{therapist_id}/temporary-password")
async def send_temporary_password(
    therapist_id: int,
    admin: Therapist = Depends(get_admin_therapist),
    db: DBSession = Depends(get_db),
):
    """Generate a temporary password, update the DB, and email it to the therapist."""
    import secrets as _secrets
    from app.security.auth import get_password_hash

    t = db.query(Therapist).filter(Therapist.id == therapist_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Therapist not found")

    temp_pw = _generate_temp_password()

    # Update hashed password and flag for forced change
    t.hashed_password = get_password_hash(temp_pw)
    t.must_change_password = True
    db.commit()

    # Send email
    try:
        await _send_temp_password_email(t.email, t.full_name, temp_pw)
    except Exception as exc:
        logger.warning(f"[temp_password] email failed for therapist_id={therapist_id}: {exc!r}")
        raise HTTPException(
            status_code=500,
            detail=f"הסיסמה עודכנה אך שליחת האימייל נכשלה: {exc}",
        )

    logger.info(f"[temp_password] sent to therapist_id={therapist_id} email={t.email}")
    create_alert(
        db,
        "temp_password_sent",
        f"סיסמה זמנית נשלחה ל-{t.full_name} ({t.email}) על ידי אדמין",
        therapist_id=therapist_id,
    )
    db.commit()

    return {"success": True, "email_sent_to": t.email}
