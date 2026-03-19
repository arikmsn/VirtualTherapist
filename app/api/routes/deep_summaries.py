"""Deep Summary + Vault routes — Phase 8."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession

from app.api.deps import get_current_therapist, get_db
from app.models.therapist import Therapist
from app.services.deep_summary_service import DeepSummaryService
from app.services.therapist_service import TherapistService

router = APIRouter()


# ── Request / Response schemas ────────────────────────────────────────────────

class DeepSummaryResponse(BaseModel):
    summary_id: int
    patient_id: int
    status: str
    sessions_covered: Optional[int] = None
    summary_json: Optional[Dict[str, Any]] = None
    rendered_text: Optional[str] = None
    approved_at: Optional[datetime] = None
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    created_at: datetime


class DeepSummaryListItem(BaseModel):
    summary_id: int
    status: str
    sessions_covered: Optional[int] = None
    approved_at: Optional[datetime] = None
    created_at: datetime
    rendered_text: Optional[str] = None
    summary_json: Optional[dict] = None


class VaultEntryResponse(BaseModel):
    id: int
    entry_type: str
    content: str
    tags: List[str]
    confidence: Optional[float] = None
    source_session_ids: List[int]
    source_type: str


class VaultGroupedResponse(BaseModel):
    entries_by_type: Dict[str, List[VaultEntryResponse]]
    total_count: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _summary_response(summary) -> DeepSummaryResponse:
    return DeepSummaryResponse(
        summary_id=summary.id,
        patient_id=summary.patient_id,
        status=summary.status,
        sessions_covered=summary.sessions_covered,
        summary_json=summary.summary_json,
        rendered_text=summary.rendered_text,
        approved_at=summary.approved_at,
        model_used=summary.model_used,
        tokens_used=summary.tokens_used,
        created_at=summary.created_at,
    )


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/clients/{client_id}/deep-summary",
    response_model=DeepSummaryResponse,
    status_code=201,
)
async def generate_deep_summary(
    client_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """
    Generate a new deep longitudinal summary for a patient.

    Uses ALL approved session summaries. Runs vault entry extraction as a side effect.
    Returns the saved DeepSummary (status=draft).
    """
    therapist_service = TherapistService(db)
    summary_service = DeepSummaryService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        summary = await summary_service.generate_deep_summary(
            patient_id=client_id,
            therapist_id=current_therapist.id,
            provider=agent.provider,
        )
        db.commit()
        return _summary_response(summary)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_deep_summary client={client_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/clients/{client_id}/deep-summary",
    response_model=DeepSummaryResponse,
)
async def get_latest_deep_summary(
    client_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Return the most recent deep summary for a patient."""
    summary_service = DeepSummaryService(db)
    try:
        summary = summary_service.get_latest_deep_summary(
            patient_id=client_id,
            therapist_id=current_therapist.id,
        )
        if not summary:
            raise HTTPException(status_code=404, detail="No deep summary found for this patient")
        return _summary_response(summary)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"get_latest_deep_summary client={client_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/clients/{client_id}/deep-summary/history",
    response_model=List[DeepSummaryListItem],
)
async def get_deep_summary_history(
    client_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Return all deep summaries for a patient, newest first."""
    summary_service = DeepSummaryService(db)
    try:
        summaries = summary_service.get_deep_summary_history(
            patient_id=client_id,
            therapist_id=current_therapist.id,
        )
        return [
            DeepSummaryListItem(
                summary_id=s.id,
                status=s.status,
                sessions_covered=s.sessions_covered,
                approved_at=s.approved_at,
                created_at=s.created_at,
                rendered_text=s.rendered_text,
                summary_json=s.summary_json,
            )
            for s in summaries
        ]
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"get_deep_summary_history client={client_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/deep-summaries/{summary_id}",
    status_code=204,
)
async def delete_deep_summary(
    summary_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Hard-delete a deep summary. Returns 404 if not found or wrong owner."""
    summary_service = DeepSummaryService(db)
    try:
        summary_service.delete_deep_summary(
            summary_id=summary_id,
            therapist_id=current_therapist.id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"delete_deep_summary summary={summary_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch(
    "/deep-summaries/{summary_id}/approve",
    response_model=DeepSummaryResponse,
)
async def approve_deep_summary(
    summary_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Approve a deep summary — sets status=approved and approved_at timestamp."""
    summary_service = DeepSummaryService(db)
    try:
        summary = summary_service.approve_deep_summary(
            summary_id=summary_id,
            therapist_id=current_therapist.id,
        )
        db.commit()
        return _summary_response(summary)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"approve_deep_summary summary={summary_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Vault endpoints ───────────────────────────────────────────────────────────

@router.get(
    "/clients/{client_id}/vault",
    response_model=VaultGroupedResponse,
)
async def get_vault_entries(
    client_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Return all active vault entries for a patient, grouped by entry_type."""
    summary_service = DeepSummaryService(db)
    try:
        grouped = summary_service.get_vault_entries(
            patient_id=client_id,
            therapist_id=current_therapist.id,
        )
        entries_by_type: Dict[str, List[VaultEntryResponse]] = {}
        total = 0
        for entry_type, entries in grouped.items():
            entries_by_type[entry_type] = [
                VaultEntryResponse(
                    id=e["id"],
                    entry_type=e["entry_type"],
                    content=e["content"],
                    tags=e["tags"],
                    confidence=e["confidence"],
                    source_session_ids=e["source_session_ids"],
                    source_type=e["source_type"],
                )
                for e in entries
            ]
            total += len(entries)
        return VaultGroupedResponse(entries_by_type=entries_by_type, total_count=total)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"get_vault_entries client={client_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete(
    "/vault/{entry_id}",
    status_code=204,
)
async def delete_vault_entry(
    entry_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: DBSession = Depends(get_db),
):
    """Soft-delete a vault entry (sets is_active=False)."""
    summary_service = DeepSummaryService(db)
    try:
        summary_service.delete_vault_entry(
            entry_id=entry_id,
            therapist_id=current_therapist.id,
        )
        db.commit()
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"delete_vault_entry entry={entry_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
