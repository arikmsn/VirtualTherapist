"""Phase 9 UI Affordances — edit lifecycle, AI health, drift alerts, signature progress."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session as DBSession

from app.api.deps import get_current_therapist, get_db
from app.api.errors import AI_ERRORS_HE
from app.models.ai_log import AIGenerationLog
from app.models.session import SessionSummary, SummaryStatus
from app.models.signature import TherapistSignatureProfile
from app.models.therapist import Therapist
from app.models.treatment_plan import TreatmentPlan

router = APIRouter()


# ── Response schemas ──────────────────────────────────────────────────────────

class AIHealthResponse(BaseModel):
    client_id: int
    approved_summaries: int
    draft_summaries: int
    has_deep_summary: bool
    has_treatment_plan: bool
    has_vault_entries: bool
    avg_edit_distance: Optional[float]
    avg_completeness_score: Optional[float]
    signature_active: bool
    ai_ready: bool                  # True if at least 1 approved summary exists


class DriftAlertItem(BaseModel):
    client_id: int
    patient_name: str               # decrypted — therapist-scoped
    drift_score: float
    drift_flags: List[str]
    last_drift_check_at: Optional[datetime]
    plan_id: int


class DriftAlertsResponse(BaseModel):
    alerts: List[DriftAlertItem]
    total: int


class SignatureProgressResponse(BaseModel):
    approved_summary_count: int
    min_samples_required: int
    is_active: bool
    progress_pct: float             # 0–100, capped at 100
    style_summary: Optional[str]    # Hebrew style description (if active)


class EditStartResponse(BaseModel):
    summary_id: int
    edit_started_at: datetime


class EditSaveResponse(BaseModel):
    summary_id: int
    therapist_edit_count: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _owns_patient(db: DBSession, therapist_id: int, patient_id: int) -> bool:
    """Return True if the therapist owns this patient."""
    from app.models.patient import Patient
    patient = db.query(Patient).filter_by(id=patient_id, therapist_id=therapist_id).first()
    return patient is not None


def _get_patient_name(db: DBSession, patient_id: int) -> str:
    """Return decrypted patient name — falls back to ID string on error."""
    try:
        from app.models.patient import Patient
        from app.services.patient_service import PatientService
        patient = db.query(Patient).filter_by(id=patient_id).first()
        if not patient:
            return f"מטופל #{patient_id}"
        svc = PatientService(db)
        decrypted = svc.decrypt_patient(patient)
        return decrypted.get("full_name") or f"מטופל #{patient_id}"
    except Exception:
        return f"מטופל #{patient_id}"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get(
    "/clients/{client_id}/ai-health",
    response_model=AIHealthResponse,
)
def get_ai_health(
    client_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Pure DB aggregation — no LLM call.

    Returns counts and quality signals for the client's AI content so the
    frontend can show an "AI readiness" indicator on the patient profile.
    """
    if not _owns_patient(db, current_therapist.id, client_id):
        raise HTTPException(status_code=404, detail=AI_ERRORS_HE["client_not_found"])

    summaries = (
        db.query(SessionSummary)
        .join(SessionSummary.session)
        .filter_by(patient_id=client_id, therapist_id=current_therapist.id)
        .all()
    )

    approved = [s for s in summaries if s.approved_by_therapist]
    drafts = [s for s in summaries if not s.approved_by_therapist]

    # Average edit distance (only rows with data)
    edit_distances = [
        s.therapist_edit_distance for s in approved
        if s.therapist_edit_distance is not None
    ]
    avg_edit = sum(edit_distances) / len(edit_distances) if edit_distances else None

    # Average completeness score
    comp_scores = [
        s.completeness_score for s in approved
        if s.completeness_score is not None
    ]
    avg_comp = sum(comp_scores) / len(comp_scores) if comp_scores else None

    # Has deep summary?
    try:
        from app.models.deep_summary import DeepSummary
        has_deep = (
            db.query(DeepSummary.id)
            .filter_by(patient_id=client_id, therapist_id=current_therapist.id)
            .first() is not None
        )
    except Exception:
        has_deep = False

    # Has treatment plan?
    has_plan = (
        db.query(TreatmentPlan.id)
        .filter_by(patient_id=client_id, therapist_id=current_therapist.id)
        .first() is not None
    )

    # Has vault entries?
    try:
        from app.models.reference_vault import TherapistReferenceVault
        has_vault = (
            db.query(TherapistReferenceVault.id)
            .filter_by(client_id=client_id, therapist_id=current_therapist.id, is_active=True)
            .first() is not None
        )
    except Exception:
        has_vault = False

    # Signature active?
    sig = (
        db.query(TherapistSignatureProfile)
        .filter_by(therapist_id=current_therapist.id, is_active=True)
        .first()
    )
    sig_active = (
        sig is not None
        and sig.approved_sample_count >= sig.min_samples_required
    )

    return AIHealthResponse(
        client_id=client_id,
        approved_summaries=len(approved),
        draft_summaries=len(drafts),
        has_deep_summary=has_deep,
        has_treatment_plan=has_plan,
        has_vault_entries=has_vault,
        avg_edit_distance=avg_edit,
        avg_completeness_score=avg_comp,
        signature_active=sig_active,
        ai_ready=len(approved) > 0,
    )


@router.get(
    "/therapist/drift-alerts",
    response_model=DriftAlertsResponse,
)
def get_drift_alerts(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Return all active treatment plans with drift_score >= 0.3, ordered highest first.

    Used by the dashboard to surface clients who need plan revision.
    """
    threshold = 0.3
    plans = (
        db.query(TreatmentPlan)
        .filter(
            TreatmentPlan.therapist_id == current_therapist.id,
            TreatmentPlan.status == "active",
            TreatmentPlan.drift_score >= threshold,
        )
        .order_by(TreatmentPlan.drift_score.desc())
        .all()
    )

    alerts = [
        DriftAlertItem(
            client_id=p.patient_id,
            patient_name=_get_patient_name(db, p.patient_id),
            drift_score=p.drift_score,
            drift_flags=p.drift_flags or [],
            last_drift_check_at=p.last_drift_check_at,
            plan_id=p.id,
        )
        for p in plans
    ]
    return DriftAlertsResponse(alerts=alerts, total=len(alerts))


@router.get(
    "/therapist/signature-profile/progress",
    response_model=SignatureProgressResponse,
)
def get_signature_progress(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Signature Engine activation progress.

    Reports how many approved summaries exist vs. the minimum threshold,
    whether the signature is active, and the current Hebrew style description.

    NOTE: is_active is derived from the live approved-summary count, NOT from
    the stale TherapistSignatureProfile.is_active DB field.  The DB field is
    only set to True when the AI rebuild runs (requires provider != None in the
    approval path), which may lag behind the actual count.
    """
    # Fetch the signature row WITHOUT filtering on is_active — we need the
    # min_samples_required and style_summary from the row even when stale.
    sig = (
        db.query(TherapistSignatureProfile)
        .filter(TherapistSignatureProfile.therapist_id == current_therapist.id)
        .first()
    )

    # Always compute a fresh approved-summary count per therapist.
    approved_count = (
        db.query(func.count(SessionSummary.id))
        .join(SessionSummary.session)
        .filter_by(therapist_id=current_therapist.id)
        .filter(SessionSummary.approved_by_therapist == True)  # noqa: E712
        .scalar()
    ) or 0

    min_req = sig.min_samples_required if sig else 5
    pct = min(100.0, (approved_count / min_req) * 100) if min_req > 0 else 100.0
    is_active = approved_count >= min_req   # derived from live count

    return SignatureProgressResponse(
        approved_summary_count=approved_count,
        min_samples_required=min_req,
        is_active=is_active,
        progress_pct=pct,
        style_summary=sig.style_summary if sig else None,
    )


@router.patch(
    "/summaries/{summary_id}/edit-start",
    response_model=EditStartResponse,
)
def edit_start(
    summary_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Mark the moment the therapist opens the summary editor.

    Records `edit_started_at` on first call; subsequent calls are no-ops
    (idempotent) so the frontend can call freely without double-counting.
    Sets `edit_started_at` only once — re-opening the editor does not reset it.
    """
    summary = _get_owned_summary(db, summary_id, current_therapist.id)

    if summary.edit_started_at is None:
        summary.edit_started_at = _utcnow()
        db.commit()

    return EditStartResponse(
        summary_id=summary.id,
        edit_started_at=summary.edit_started_at,
    )


@router.patch(
    "/summaries/{summary_id}/edit-save",
    response_model=EditSaveResponse,
)
def edit_save(
    summary_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Increment the save counter each time the therapist saves an edit.

    Does NOT change summary status — approval is a separate action.
    Returns 409 if the summary is already approved.
    """
    summary = _get_owned_summary(db, summary_id, current_therapist.id)

    if summary.approved_by_therapist:
        raise HTTPException(
            status_code=409,
            detail=AI_ERRORS_HE["summary_already_approved"],
        )

    summary.therapist_edit_count = (summary.therapist_edit_count or 0) + 1
    db.commit()

    return EditSaveResponse(
        summary_id=summary.id,
        therapist_edit_count=summary.therapist_edit_count,
    )


# ── Internal helper ───────────────────────────────────────────────────────────

def _get_owned_summary(
    db: DBSession, summary_id: int, therapist_id: int
) -> SessionSummary:
    """Fetch summary and verify ownership. Raises 404 if not found/owned."""
    from app.models.session import Session as SessionModel
    summary = (
        db.query(SessionSummary)
        .join(SessionSummary.session)
        .filter(
            SessionSummary.id == summary_id,
            SessionModel.therapist_id == therapist_id,
        )
        .first()
    )
    if not summary:
        raise HTTPException(
            status_code=404,
            detail=AI_ERRORS_HE["summary_not_found"],
        )
    return summary
