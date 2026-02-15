"""Message service - handles patient messages and approval workflow"""

from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.models.message import Message, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.core.agent import TherapyAgent
from app.services.audit_service import AuditService
from app.core.config import settings
from loguru import logger


class MessageService:
    """
    Service for managing messages to patients
    CRITICAL: All messages require therapist approval before sending!
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    async def create_draft_message(
        self,
        therapist_id: int,
        patient_id: int,
        message_type: str,
        agent: TherapyAgent,
        context: Optional[dict] = None
    ) -> Message:
        """
        Create a draft message for a patient using AI
        This message is NOT sent until therapist approves!
        """

        # Verify patient belongs to therapist
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id
        ).first()

        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        # Generate message content using AI agent
        message_prompt = await self._build_message_prompt(
            patient=patient,
            message_type=message_type,
            context=context
        )

        content = await agent.generate_response(message_prompt, context=context)

        # Create draft message
        message = Message(
            therapist_id=therapist_id,
            patient_id=patient_id,
            direction=MessageDirection.TO_PATIENT,
            content=content,
            status=MessageStatus.DRAFT,
            requires_approval=settings.REQUIRE_THERAPIST_APPROVAL,
            message_type=message_type,
            generated_by_ai=True,
            ai_model=settings.AI_MODEL,
            ai_prompt_used=message_prompt
        )

        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="create",
            resource_type="message_draft",
            resource_id=message.id,
            action_details={
                "patient_id": patient_id,
                "message_type": message_type
            }
        )

        logger.info(f"Created draft message {message.id} for patient {patient_id}")
        return message

    async def _build_message_prompt(
        self,
        patient: Patient,
        message_type: str,
        context: Optional[dict] = None
    ) -> str:
        """Build the prompt for generating a patient message"""

        from app.security.encryption import decrypt_data

        # Decrypt patient name for context (will be re-encrypted)
        patient_name = decrypt_data(patient.full_name_encrypted)

        prompts = {
            "follow_up": f"""
צור הודעת מעקב קצרה למטופל/ת {patient_name}.
בדוק/י איך הלך תרגיל הבית מהפגישה האחרונה.
הודעה קצרה, 2-3 משפטים, בטון שלך האישי.
            """,
            "exercise_reminder": f"""
צור תזכורת ידידותית למטופל/ת {patient_name} להשלים את התרגיל שהוטל.
הודעה קצרה ומעודדת, בטון שלך האישי.
            """,
            "check_in": f"""
צור הודעת צ'ק-אין כללית למטופל/ת {patient_name}.
שאל/י איך הוא/היא מרגיש/ה, מה התחדש.
הודעה קצרה וחמה, בטון שלך האישי.
            """,
            "session_reminder": f"""
צור תזכורת לפגישה הבאה למטופל/ת {patient_name}.
כלול את מועד הפגישה והזכר/י נושא או תרגיל שדיברתם עליו.
            """
        }

        base_prompt = prompts.get(message_type, f"צור הודעה למטופל/ת {patient_name}.")

        # Add context if provided
        if context:
            base_prompt += f"\n\nהקשר נוסף: {context}"

        base_prompt += "\n\nחשוב: דבר בשם המטפל, לא בשם עצמך!"

        return base_prompt

    async def approve_message(self, message_id: int, therapist_id: int) -> Message:
        """
        Therapist approves a message - it can now be sent
        This is CRITICAL for ethical operation!
        """

        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.therapist_id == therapist_id
        ).first()

        if not message:
            raise ValueError("Message not found or does not belong to this therapist")

        if message.status not in [MessageStatus.DRAFT, MessageStatus.PENDING_APPROVAL]:
            raise ValueError(f"Message cannot be approved from status: {message.status}")

        message.status = MessageStatus.APPROVED
        message.approved_at = datetime.utcnow()

        self.db.commit()

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="approve",
            resource_type="message",
            resource_id=message.id,
            action_details={"content_preview": message.content[:100]}
        )

        logger.info(f"Therapist approved message {message_id}")
        return message

    async def reject_message(
        self,
        message_id: int,
        therapist_id: int,
        reason: Optional[str] = None
    ) -> Message:
        """Therapist rejects a message - it will not be sent"""

        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.therapist_id == therapist_id
        ).first()

        if not message:
            raise ValueError("Message not found")

        message.status = MessageStatus.REJECTED
        message.rejected_at = datetime.utcnow()
        message.rejection_reason = reason

        self.db.commit()

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="reject",
            resource_type="message",
            resource_id=message.id,
            action_details={"reason": reason}
        )

        logger.info(f"Therapist rejected message {message_id}")
        return message

    async def edit_message(
        self,
        message_id: int,
        therapist_id: int,
        new_content: str
    ) -> Message:
        """Therapist edits a draft message before approving"""

        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.therapist_id == therapist_id
        ).first()

        if not message:
            raise ValueError("Message not found")

        if message.status not in [MessageStatus.DRAFT, MessageStatus.PENDING_APPROVAL]:
            raise ValueError("Can only edit draft messages")

        old_content = message.content
        message.content = new_content

        self.db.commit()

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="edit",
            resource_type="message",
            resource_id=message.id,
            old_value=old_content[:100],
            new_value=new_content[:100]
        )

        logger.info(f"Therapist edited message {message_id}")
        return message

    async def send_message(self, message_id: int) -> Message:
        """
        Actually send the message to the patient
        Can only send approved messages!
        """

        message = self.db.query(Message).filter(Message.id == message_id).first()
        if not message:
            raise ValueError("Message not found")

        if message.status != MessageStatus.APPROVED:
            raise ValueError("Can only send approved messages")

        # TODO: Integrate with actual messaging service (SMS, WhatsApp, email)
        # For now, just mark as sent

        message.status = MessageStatus.SENT
        message.sent_at = datetime.utcnow()

        self.db.commit()

        # Audit log
        await self.audit_service.log_action(
            user_id=message.therapist_id,
            user_type="system",
            action="send",
            resource_type="message",
            resource_id=message.id
        )

        logger.info(f"Sent message {message_id} to patient {message.patient_id}")
        return message

    async def get_pending_messages(self, therapist_id: int) -> List[Message]:
        """Get all messages pending therapist approval"""

        messages = self.db.query(Message).filter(
            Message.therapist_id == therapist_id,
            Message.status.in_([MessageStatus.DRAFT, MessageStatus.PENDING_APPROVAL])
        ).order_by(Message.created_at.desc()).all()

        return messages

    async def get_patient_message_history(
        self,
        therapist_id: int,
        patient_id: int,
        limit: int = 50
    ) -> List[Message]:
        """Get message history for a specific patient"""

        messages = self.db.query(Message).filter(
            Message.therapist_id == therapist_id,
            Message.patient_id == patient_id
        ).order_by(Message.created_at.desc()).limit(limit).all()

        return messages
