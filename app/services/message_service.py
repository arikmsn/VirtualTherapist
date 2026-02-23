"""Message service - handles patient messages and approval workflow"""

from typing import Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.models.message import Message, MessageStatus, MessageDirection
from app.models.patient import Patient
from app.models.therapist import Therapist
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

    # ── Messages Center v1 methods (Phase C) ─────────────────────────────────

    async def generate_draft_message(
        self,
        therapist_id: int,
        patient_id: int,
        message_type: str,  # "task_reminder" | "session_reminder"
        agent: TherapyAgent,
        context: Optional[dict] = None,
    ) -> Message:
        """
        Generate a Twin-aligned draft message for the Messages Center.

        - "session_reminder": template-based (no AI call), uses patient name +
          session date/time from context.
        - "task_reminder": AI-generated using therapist Twin controls
          (tone_warmth, directiveness, prohibitions, custom_rules).

        The draft is always in status=DRAFT. The therapist sees and edits it
        before confirming via send_or_schedule_message().
        """
        from app.security.encryption import decrypt_data

        # Verify patient belongs to therapist
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        # Get therapist for name
        therapist = self.db.query(Therapist).filter(Therapist.id == therapist_id).first()

        patient_name = decrypt_data(patient.full_name_encrypted)
        therapist_name = therapist.full_name if therapist else ""
        therapist_phone = therapist.phone or "" if therapist else ""

        if message_type == "session_reminder":
            # Template-only — no free-text stored or sent.
            # deliver_message() uses the approved WhatsApp Content Template exclusively.
            content = ""
            ai_prompt = None

        elif message_type == "task_reminder":
            # AI-generated, Twin-aligned
            task = (context or {}).get("task", "")
            profile = getattr(
                self.db.query(Therapist).filter(Therapist.id == therapist_id).first(),
                "profile", None
            )
            tone_warmth = (profile.tone_warmth or 3) if profile else 3
            directiveness = (profile.directiveness or 3) if profile else 3
            prohibitions = (profile.prohibitions or []) if profile else []
            custom_rules = (profile.custom_rules or "") if profile else ""

            prohibitions_text = (
                "\n".join(f"- {p}" for p in prohibitions) if prohibitions else "אין"
            )

            ai_prompt = f"""צור הודעת תזכורת קצרה לוואטסאפ עבור המטופל/ת {patient_name}.

משימה: {task or "השלמת משימת הבית מהפגישה האחרונה"}

הנחיות סגנון:
- חמימות: {tone_warmth}/5 (1=פורמלי, 5=חמים)
- הכוונה: {directiveness}/5 (1=חקרני, 5=מכוון)

מגבלות (חובה לכבד):
{prohibitions_text}

כללים נוספים: {custom_rules or "אין"}

הוראות קשיחות (תמיד):
- אל תציין אבחנות, הערכות קליניות, או המלצות תרופתיות.
- אל תספק תמיכת משבר — אם המטופל/ת במשבר, הפנה/י לטיפולי חירום.
- 2-3 משפטים בלבד, מתאים לוואטסאפ.
- כתוב בעברית בלבד.
- חתום: {therapist_name}"""

            content = await agent.generate_response(ai_prompt, context=context)

        else:
            raise ValueError(f"Unknown message_type: '{message_type}'. Use 'task_reminder' or 'session_reminder'.")

        message = Message(
            therapist_id=therapist_id,
            patient_id=patient_id,
            direction=MessageDirection.TO_PATIENT,
            content=content,
            status=MessageStatus.DRAFT,
            requires_approval=True,
            message_type=message_type,
            generated_by_ai=(message_type == "task_reminder"),
            ai_model=settings.AI_MODEL if message_type == "task_reminder" else None,
            ai_prompt_used=ai_prompt,
            channel="whatsapp",
            related_session_id=(context or {}).get("session_id") if message_type == "session_reminder" else None,
        )

        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate_draft",
            resource_type="message",
            resource_id=message.id,
            action_details={"patient_id": patient_id, "message_type": message_type},
        )

        logger.info(f"Generated draft message {message.id} (type={message_type}) for patient {patient_id}")
        return message

    async def send_or_schedule_message(
        self,
        message_id: int,
        therapist_id: int,
        final_content: str,
        recipient_phone: Optional[str] = None,
        send_at: Optional[datetime] = None,
    ) -> Message:
        """
        Therapist confirms a draft message — either sends now or schedules.

        - Saves final_content and recipient_phone.
        - If send_at is None/past → deliver immediately → status=SENT.
        - If send_at is future  → status=SCHEDULED, register APScheduler job.
        """
        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.therapist_id == therapist_id,
        ).first()
        if not message:
            raise ValueError("Message not found or does not belong to this therapist")
        if message.status != MessageStatus.DRAFT:
            raise ValueError(f"Can only confirm DRAFT messages (current status: {message.status})")

        # Persist final content and recipient
        # session_reminder uses a fixed WhatsApp template — content is never editable
        if message.message_type != "session_reminder":
            message.content = final_content
        if recipient_phone:
            from app.utils.phone import normalize_phone
            message.recipient_phone = normalize_phone(recipient_phone)
        message.approved_at = datetime.now(timezone.utc)

        # Normalize send_at: attach UTC tzinfo if it arrives naive
        if send_at is not None and send_at.tzinfo is None:
            send_at = send_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        logger.info(
            "send_or_schedule_message: msg=%d send_at=%s now=%s decision=%s",
            message_id,
            send_at.isoformat() if send_at else "None",
            now.isoformat(),
            "immediate" if (send_at is None or send_at <= now) else f"schedule_at={send_at.isoformat()}",
        )
        if send_at is None or send_at <= now:
            # Send immediately
            self.db.commit()
            return await self.deliver_message(message_id)
        else:
            # Schedule for later
            message.status = MessageStatus.SCHEDULED
            message.scheduled_send_at = send_at
            self.db.commit()
            self.db.refresh(message)

            # Register APScheduler one-shot job
            from app.core.scheduler import scheduler
            scheduler.add_job(
                _deliver_message_job,
                trigger="date",
                run_date=send_at,
                args=[message_id],
                id=f"msg_{message_id}",
                replace_existing=True,
            )
            logger.info(f"Message {message_id} scheduled for {send_at}")

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="schedule" if send_at and send_at > now else "send",
            resource_type="message",
            resource_id=message_id,
            action_details={"send_at": str(send_at), "recipient_phone": recipient_phone},
        )
        return message

    async def cancel_message(self, message_id: int, therapist_id: int) -> Message:
        """Cancel a SCHEDULED message. Removes the APScheduler job."""
        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.therapist_id == therapist_id,
        ).first()
        if not message:
            raise ValueError("Message not found or does not belong to this therapist")
        if message.status != MessageStatus.SCHEDULED:
            raise ValueError(f"Can only cancel SCHEDULED messages (current status: {message.status})")

        message.status = MessageStatus.CANCELLED
        self.db.commit()
        self.db.refresh(message)

        # Remove the APScheduler job
        from app.core.scheduler import scheduler
        try:
            scheduler.remove_job(f"msg_{message_id}")
        except Exception:
            pass  # Job may have already fired or doesn't exist

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="cancel",
            resource_type="message",
            resource_id=message_id,
        )
        logger.info(f"Cancelled scheduled message {message_id}")
        return message

    async def edit_scheduled_message(
        self,
        message_id: int,
        therapist_id: int,
        content: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        send_at: Optional[datetime] = None,
    ) -> Message:
        """Edit a SCHEDULED message's content, recipient, or send time."""
        message = self.db.query(Message).filter(
            Message.id == message_id,
            Message.therapist_id == therapist_id,
        ).first()
        if not message:
            raise ValueError("Message not found")
        if message.status != MessageStatus.SCHEDULED:
            raise ValueError(f"Can only edit SCHEDULED messages (current status: {message.status})")

        # session_reminder content is template-only and cannot be edited
        if content is not None and message.message_type != "session_reminder":
            message.content = content
        if recipient_phone is not None:
            if recipient_phone:
                from app.utils.phone import normalize_phone
                message.recipient_phone = normalize_phone(recipient_phone)
            else:
                message.recipient_phone = recipient_phone
        if send_at is not None:
            message.scheduled_send_at = send_at
            # Reschedule APScheduler job
            from app.core.scheduler import scheduler
            scheduler.reschedule_job(f"msg_{message_id}", trigger="date", run_date=send_at)

        self.db.commit()
        self.db.refresh(message)
        return message

    async def deliver_message(self, message_id: int) -> Message:
        """
        Actually deliver a message via its channel.
        Called immediately (send now) or by APScheduler (scheduled delivery).
        """
        message = self.db.query(Message).filter(Message.id == message_id).first()
        if not message:
            logger.error(f"deliver_message: message {message_id} not found")
            return

        # Resolve recipient phone
        to_phone = message.recipient_phone
        if not to_phone:
            # Fall back to patient's phone
            from app.security.encryption import decrypt_data
            patient = self.db.query(Patient).filter(Patient.id == message.patient_id).first()
            if patient and patient.phone_encrypted:
                to_phone = decrypt_data(patient.phone_encrypted)

        if not to_phone:
            logger.error(f"No phone for message {message_id} — marking FAILED")
            message.status = MessageStatus.FAILED
            self.db.commit()
            return message

        # Send via whatsapp_service (routes to Green API or Twilio based on WHATSAPP_PROVIDER)
        from app.services.whatsapp_service import send_whatsapp_message

        if message.message_type == "session_reminder":
            # Use Content Template (Twilio) or plain-text fallback (Green API).
            # Template HX6ab2d8bbf149e9d05598bbecb4522eb6 has 4 variables:
            #   {{1}} patient_name, {{2}} therapist_name, {{3}} date, {{4}} time
            from app.security.encryption import decrypt_data as _decrypt
            from app.models.session import Session as TherapySession
            _TEMPLATE_SID = "HX6ab2d8bbf149e9d05598bbecb4522eb6"

            _patient = self.db.query(Patient).filter(Patient.id == message.patient_id).first()
            _patient_name = _decrypt(_patient.full_name_encrypted) if (_patient and _patient.full_name_encrypted) else "המטופל"

            _therapist = self.db.query(Therapist).filter(Therapist.id == message.therapist_id).first()
            _therapist_name = _therapist.full_name if _therapist else ""

            _session_date = "לא צוין"
            _session_time = "לא צוינה"

            # Try the linked session first; fall back to the most recent session for this patient
            _sess = None
            if message.related_session_id:
                _sess = self.db.query(TherapySession).filter(
                    TherapySession.id == message.related_session_id
                ).first()

            if _sess is None:
                _sess = (
                    self.db.query(TherapySession)
                    .filter(
                        TherapySession.patient_id == message.patient_id,
                        TherapySession.therapist_id == message.therapist_id,
                    )
                    .order_by(TherapySession.session_date.desc())
                    .first()
                )

            if _sess:
                if _sess.start_time:
                    _session_date = _sess.start_time.strftime("%d/%m/%Y")
                    _session_time = _sess.start_time.strftime("%H:%M")
                elif _sess.session_date:
                    _session_date = _sess.session_date.strftime("%d/%m/%Y")

            result = await send_whatsapp_message(
                to_phone,
                message.content,
                content_sid=_TEMPLATE_SID,
                content_variables={
                    "1": _patient_name,
                    "2": _therapist_name,
                    "3": _session_date,
                    "4": _session_time,
                },
            )
        else:
            result = await send_whatsapp_message(to_phone, message.content)

        if result["status"] == "sent":
            message.status = MessageStatus.SENT
            message.sent_at = datetime.utcnow()
            logger.info(f"Message {message_id} sent OK (provider_id={result['provider_id']})")
        else:
            message.status = MessageStatus.FAILED
            error_str = result.get("error", "")
            if "63016" in error_str:
                failure_reason = "outside 24h window - template required"
                message.rejection_reason = failure_reason
                logger.error(
                    f"Message {message_id} rejected (63016 — outside 24h WhatsApp window). "
                    f"patient_id={message.patient_id} phone={to_phone}. Use a Content Template."
                )
            else:
                logger.error(f"Message {message_id} delivery failed: {error_str}")

        self.db.commit()
        self.db.refresh(message)

        await self.audit_service.log_action(
            user_id=message.therapist_id,
            user_type="system",
            action="deliver",
            resource_type="message",
            resource_id=message_id,
            action_details={"status": result["status"], "error": result.get("error", "")},
        )
        return message


def _deliver_message_job(message_id: int) -> None:
    """
    Synchronous APScheduler job entry point.
    Runs in the scheduler thread — creates its own DB session and event loop slice.
    """
    import asyncio
    from app.core.database import SessionLocal

    db = SessionLocal()
    try:
        service = MessageService(db)
        asyncio.run(service.deliver_message(message_id))
    finally:
        db.close()
