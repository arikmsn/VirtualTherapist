"""AI Agent interaction routes"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.api.deps import get_db, get_current_therapist
from app.models.therapist import Therapist
from app.services.therapist_service import TherapistService


router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    response: str
    agent_model: str


class CommandRequest(BaseModel):
    command: str
    args: str = ""


@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(
    request: ChatRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """
    Chat with the AI agent
    The agent responds in the therapist's personal style
    """

    therapist_service = TherapistService(db)

    try:
        # Get personalized agent
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)

        # Generate response
        response = await agent.generate_response(
            message=request.message,
            context=request.context
        )

        return {
            "response": response,
            "agent_model": agent.ai_provider
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/command", response_model=ChatResponse)
async def execute_command(
    request: CommandRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """
    Execute a special command like /start, /summary, etc.
    """

    therapist_service = TherapistService(db)

    try:
        # Get personalized agent
        agent = await therapist_service.get_agent_for_therapist(current_therapist.id)

        # Handle command
        response = await agent.handle_command(
            command=request.command.lstrip('/'),
            args=request.args
        )

        return {
            "response": response,
            "agent_model": agent.ai_provider
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/onboarding/start")
async def start_onboarding(
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """Start the therapist onboarding process"""

    therapist_service = TherapistService(db)

    try:
        agent = await therapist_service.start_onboarding(current_therapist.id)

        # Get initial greeting
        greeting = await agent.handle_command("start")

        return {
            "message": greeting,
            "onboarding_step": 1
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OnboardingStepRequest(BaseModel):
    step: int
    data: Dict[str, Any]


@router.post("/onboarding/complete-step")
async def complete_onboarding_step(
    request: OnboardingStepRequest,
    current_therapist: Therapist = Depends(get_current_therapist),
    db: Session = Depends(get_db)
):
    """Complete a step in the onboarding process"""

    therapist_service = TherapistService(db)

    try:
        profile = await therapist_service.complete_onboarding_step(
            therapist_id=current_therapist.id,
            step=request.step,
            data=request.data
        )

        return {
            "message": "Step completed successfully",
            "current_step": profile.onboarding_step,
            "onboarding_completed": profile.onboarding_completed
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
