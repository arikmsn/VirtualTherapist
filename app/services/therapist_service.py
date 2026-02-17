"""Therapist service - handles therapist profile management and onboarding"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.therapist import Therapist, TherapistProfile, TherapeuticApproach
from app.core.agent import TherapyAgent
from app.services.audit_service import AuditService
from loguru import logger


class TherapistService:
    """Service for managing therapist profiles and personalization"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    async def create_therapist(
        self,
        email: str,
        password: str,
        full_name: str,
        phone: Optional[str] = None
    ) -> Therapist:
        """Create a new therapist account"""
        from app.security.auth import get_password_hash

        # Check if therapist already exists
        existing = self.db.query(Therapist).filter(Therapist.email == email).first()
        if existing:
            raise ValueError("Therapist with this email already exists")

        # Create therapist
        therapist = Therapist(
            email=email,
            hashed_password=get_password_hash(password),
            full_name=full_name,
            phone=phone
        )

        self.db.add(therapist)
        self.db.commit()
        self.db.refresh(therapist)

        # Create default profile
        profile = TherapistProfile(
            therapist_id=therapist.id,
            therapeutic_approach=TherapeuticApproach.CBT,  # Default
            onboarding_completed=False,
            onboarding_step=0
        )

        self.db.add(profile)
        self.db.commit()

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist.id,
            user_type="therapist",
            user_email=email,
            action="create",
            resource_type="therapist",
            resource_id=therapist.id,
            action_details={"full_name": full_name}
        )

        logger.info(f"Created new therapist: {email}")
        return therapist

    async def update_profile(
        self,
        therapist_id: int,
        profile_data: Dict[str, Any]
    ) -> TherapistProfile:
        """Update therapist profile with personalization data"""

        profile = self.db.query(TherapistProfile).filter(
            TherapistProfile.therapist_id == therapist_id
        ).first()

        if not profile:
            raise ValueError("Therapist profile not found")

        # Update fields
        for field, value in profile_data.items():
            if hasattr(profile, field):
                setattr(profile, field, value)

        self.db.commit()
        self.db.refresh(profile)

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="update",
            resource_type="therapist_profile",
            resource_id=profile.id,
            action_details=profile_data
        )

        logger.info(f"Updated profile for therapist ID: {therapist_id}")
        return profile

    async def start_onboarding(self, therapist_id: int) -> TherapyAgent:
        """
        Start the onboarding process for a new therapist
        Returns an AI agent ready for onboarding conversation
        """

        therapist = self.db.query(Therapist).filter(Therapist.id == therapist_id).first()
        if not therapist:
            raise ValueError("Therapist not found")

        profile = therapist.profile
        profile.onboarding_step = 1

        self.db.commit()

        # Create agent for onboarding
        agent = TherapyAgent(therapist_profile=profile)

        logger.info(f"Started onboarding for therapist: {therapist.email}")
        return agent

    async def complete_onboarding_step(
        self,
        therapist_id: int,
        step: int,
        data: Dict[str, Any]
    ) -> TherapistProfile:
        """Complete a step in the onboarding process"""

        profile = self.db.query(TherapistProfile).filter(
            TherapistProfile.therapist_id == therapist_id
        ).first()

        if not profile:
            raise ValueError("Profile not found")

        # Update based on step
        if step == 1:  # Therapeutic approach
            profile.therapeutic_approach = TherapeuticApproach(data.get("approach", "CBT"))
            profile.approach_description = data.get("description")

        elif step == 2:  # Writing style
            profile.tone = data.get("tone")
            profile.message_length_preference = data.get("message_length")
            profile.common_terminology = data.get("terminology", [])

        elif step == 3:  # Summary preferences
            profile.summary_template = data.get("template")
            profile.summary_sections = data.get(
                "sections",
                ["topics", "interventions", "progress", "next_steps"],
            )

        elif step == 4:  # Communication preferences
            profile.follow_up_frequency = data.get("follow_up_frequency")
            profile.preferred_exercises = data.get("preferred_exercises", [])

        elif step == 5:  # Examples for AI learning
            profile.example_summaries = data.get("example_summaries", [])
            profile.example_messages = data.get("example_messages", [])

        profile.onboarding_step = step

        # Check if onboarding is complete (all 5 steps)
        if step >= 5:
            profile.onboarding_completed = True

        self.db.commit()
        self.db.refresh(profile)

        logger.info(f"Completed onboarding step {step} for therapist ID: {therapist_id}")
        return profile

    async def get_agent_for_therapist(self, therapist_id: int) -> TherapyAgent:
        """Get a personalized AI agent for a specific therapist"""

        therapist = self.db.query(Therapist).filter(Therapist.id == therapist_id).first()
        if not therapist:
            raise ValueError("Therapist not found")

        if not therapist.profile.onboarding_completed:
            logger.warning(f"Therapist {therapist.email} has not completed onboarding")

        # Create personalized agent
        agent = TherapyAgent(therapist_profile=therapist.profile)

        return agent

    def get_therapist_by_email(self, email: str) -> Optional[Therapist]:
        """Get therapist by email"""
        return self.db.query(Therapist).filter(Therapist.email == email).first()

    def get_therapist_by_id(self, therapist_id: int) -> Optional[Therapist]:
        """Get therapist by ID"""
        return self.db.query(Therapist).filter(Therapist.id == therapist_id).first()
