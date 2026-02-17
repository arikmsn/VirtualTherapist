"""Message management routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.models.message import MessageStatus
from app.services.message_service import MessageService
from app.services.therapist_service import TherapistService


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
    message_type: str
    created_at: str
    requires_approval: bool

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
        raise HTTPException(status_code=500, detail=str(e))


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
        raise HTTPException(status_code=500, detail=str(e))
