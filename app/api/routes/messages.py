"""Message management routes"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.models.message import Message, MessageStatus
from app.services.message_service import MessageService
from app.services.therapist_service import TherapistService
from loguru import logger


router = APIRouter()


class CreateMessageRequest(BaseModel):
    patient_id: int
    message_type: str
    context: Optional[Dict[str, Any]] = None


class MessageResponse(BaseModel):
    id: int
    patient_id: int
    content: str
    status: MessageStatus
    message_type: Optional[str] = None
    created_at: datetime
    requires_approval: bool
    # Messages Center v1 fields
    scheduled_send_at: Optional[datetime] = None
    channel: Optional[str] = None
    recipient_phone: Optional[str] = None
    sent_at: Optional[datetime] = None
    related_session_id: Optional[int] = None

    class Config:
        from_attributes = True


class ApproveMessageRequest(BaseModel):
    message_id: int


class RejectMessageRequest(BaseModel):
    message_id: int
    reason: Optional[str] = None


class EditMessageRequest(BaseModel):
    message_id: int
    new_content: str


@router.post("/create", response_model=MessageResponse)
async def create_draft_message(
    request: CreateMessageRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """
    Create a draft message for a patient using AI
    This message will NOT be sent until therapist approves!
    """

    message_service = MessageService(db)
    therapist_service = TherapistService(db)

    try:
        # Get personalized agent
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)

        # Create draft message
        message = await message_service.create_draft_message(
            therapist_id=current_therapist.id,
            patient_id=request.patient_id,
            message_type=request.message_type,
            agent=agent,
            context=request.context
        )

        return MessageResponse.model_validate(message)

    except Exception as e:
        logger.exception(f"create_draft_message therapist={current_therapist.id} patient={request.patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/approve")
async def approve_message(
    request: ApproveMessageRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """
    Approve a message - it can now be sent
    CRITICAL: Only therapist can approve messages!
    """

    message_service = MessageService(db)

    try:
        message = await message_service.approve_message(
            message_id=request.message_id,
            therapist_id=current_therapist.id
        )

        return {
            "message": "Message approved successfully",
            "message_id": message.id,
            "status": message.status
        }

    except Exception as e:
        logger.exception(f"approve_message msg={request.message_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reject")
async def reject_message(
    request: RejectMessageRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """Reject a message - it will not be sent"""

    message_service = MessageService(db)

    try:
        message = await message_service.reject_message(
            message_id=request.message_id,
            therapist_id=current_therapist.id,
            reason=request.reason
        )

        return {
            "message": "Message rejected",
            "message_id": message.id,
            "status": message.status
        }

    except Exception as e:
        logger.exception(f"reject_message msg={request.message_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/edit")
async def edit_message(
    request: EditMessageRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """Edit a draft message before approving"""

    message_service = MessageService(db)

    try:
        message = await message_service.edit_message(
            message_id=request.message_id,
            therapist_id=current_therapist.id,
            new_content=request.new_content
        )

        return {
            "message": "Message edited successfully",
            "message_id": message.id
        }

    except Exception as e:
        logger.exception(f"edit_message msg={request.message_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/send/{message_id}")
async def send_message(
    message_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """
    Actually send an approved message to patient
    Can only send approved messages!
    """

    message_service = MessageService(db)

    try:
        message = await message_service.send_message(message_id)

        return {
            "message": "Message sent successfully",
            "message_id": message.id,
            "sent_at": message.sent_at
        }

    except Exception as e:
        logger.exception(f"send_message msg={message_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=List[MessageResponse])
async def get_all_messages(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
    patient_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    date_from: Optional[datetime] = Query(default=None),
    date_to: Optional[datetime] = Query(default=None),
):
    """
    Return ALL messages for the current therapist across all patients.
    Optional query filters: patient_id, status, date_from, date_to.
    Used by the Message Control Center screen.
    """
    try:
        q = db.query(Message).filter(Message.therapist_id == current_therapist.id)
        if patient_id is not None:
            q = q.filter(Message.patient_id == patient_id)
        if status is not None:
            q = q.filter(Message.status == status)
        if date_from is not None:
            q = q.filter(Message.created_at >= date_from)
        if date_to is not None:
            q = q.filter(Message.created_at <= date_to)
        messages = q.order_by(Message.created_at.desc()).all()
        return [MessageResponse.model_validate(m) for m in messages]
    except Exception as e:
        logger.exception(f"get_all_messages therapist={current_therapist.id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending", response_model=List[MessageResponse])
async def get_pending_messages(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """Get all messages pending therapist approval"""

    message_service = MessageService(db)

    try:
        messages = await message_service.get_pending_messages(current_therapist.id)
        return [MessageResponse.model_validate(msg) for msg in messages]

    except Exception as e:
        logger.error(f"get_pending_messages failed for therapist {current_therapist.id}: {e!r}")
        return []


@router.get("/patient/{patient_id}", response_model=List[MessageResponse])
async def get_patient_messages(
    patient_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """Get message history for a specific patient"""

    message_service = MessageService(db)

    try:
        messages = await message_service.get_patient_message_history(
            therapist_id=current_therapist.id,
            patient_id=patient_id
        )

        return [MessageResponse.model_validate(msg) for msg in messages]

    except Exception as e:
        logger.exception(f"get_patient_messages patient={patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Messages Center v1 endpoints (Phase C) ──────────────────────────────────


class GenerateDraftRequest(BaseModel):
    """Generate a Twin-aligned draft message for the Messages Center."""
    patient_id: int
    message_type: str  # "task_reminder" | "session_reminder"
    context: Optional[Dict[str, Any]] = None  # e.g. task text, session date/time


class SendOrScheduleRequest(BaseModel):
    """Therapist confirms and sends/schedules a DRAFT message."""
    content: Optional[str] = None      # Final message text; omitted for session_reminder (template-only)
    recipient_phone: Optional[str] = None  # Override patient default phone
    send_at: Optional[datetime] = None # None = send now; future = schedule


class EditScheduledRequest(BaseModel):
    """Edit a SCHEDULED message before it fires."""
    content: Optional[str] = None
    recipient_phone: Optional[str] = None
    send_at: Optional[datetime] = None


@router.post("/generate", response_model=MessageResponse, status_code=201)
async def generate_draft_message(
    request: GenerateDraftRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Generate a Twin-aligned draft message (task reminder or session reminder).
    The therapist sees and can edit the text before sending or scheduling.
    """
    message_service = MessageService(db)
    therapist_service = TherapistService(db)

    try:
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)
        message = await message_service.generate_draft_message(
            therapist_id=current_therapist.id,
            patient_id=request.patient_id,
            message_type=request.message_type,
            agent=agent,
            context=request.context,
        )
        return MessageResponse.model_validate(message)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"generate_draft_message therapist={current_therapist.id} patient={request.patient_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{message_id}/send-or-schedule", response_model=MessageResponse)
async def send_or_schedule_message(
    message_id: int,
    request: SendOrScheduleRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """
    Therapist confirms a draft: sends now (send_at=null/past) or schedules
    for a future date/time. The final edited content is saved before sending.
    """
    message_service = MessageService(db)

    try:
        message = await message_service.send_or_schedule_message(
            message_id=message_id,
            therapist_id=current_therapist.id,
            final_content=request.content or "",
            recipient_phone=request.recipient_phone,
            send_at=request.send_at,
        )
        return MessageResponse.model_validate(message)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"send_or_schedule_message msg={message_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{message_id}/cancel", response_model=MessageResponse)
async def cancel_message(
    message_id: int,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Cancel a SCHEDULED message. Removes the pending delivery job."""
    message_service = MessageService(db)

    try:
        message = await message_service.cancel_message(
            message_id=message_id,
            therapist_id=current_therapist.id,
        )
        return MessageResponse.model_validate(message)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"cancel_message msg={message_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{message_id}", response_model=MessageResponse)
async def edit_scheduled_message(
    message_id: int,
    request: EditScheduledRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db),
):
    """Edit the content, recipient, or send time of a SCHEDULED message."""
    message_service = MessageService(db)

    try:
        message = await message_service.edit_scheduled_message(
            message_id=message_id,
            therapist_id=current_therapist.id,
            content=request.content,
            recipient_phone=request.recipient_phone,
            send_at=request.send_at,
        )
        return MessageResponse.model_validate(message)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.exception(f"edit_scheduled_message msg={message_id} failed: {e!r}")
        raise HTTPException(status_code=500, detail=str(e))
