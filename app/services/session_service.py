"""Session service - handles therapy sessions and summary generation"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import date, datetime, timedelta
from sqlalchemy.orm import Session
from app.models.session import Session as TherapySession, SessionSummary, SessionType, SummaryStatus
from app.models.patient import Patient
from app.models.exercise import Exercise
from app.models.ai_log import AIGenerationLog
from app.core.agent import (
    TherapyAgent,
    PatientInsightResult,
    SessionPrepBriefResult,
    DeepSummaryResult,
    TreatmentPlanResult,
    TreatmentGoal,
)
from app.ai.models import FlowType
from app.ai.completeness import CompletenessChecker
from app.ai.summary_pipeline import SummaryInput, SummaryPipeline, compute_edit_distance
from app.ai.prep import PrepInput, PrepMode, PrepPipeline, PrepResult
from app.ai.signature import SignatureEngine, inject_into_prompt
from app.services.audit_service import AuditService
from app.security.encryption import decrypt_data
from loguru import logger


# Twilio Content Template SID for appointment reminders.
# Template variables: 1=patient name, 2=therapist name, 3=session date, 4=session time
APPOINTMENT_TEMPLATE_SID = "HX6975c9f8284208ae4b202035dac62c85"


async def send_appointment_reminder(session_id: int) -> None:
    """
    Send a WhatsApp appointment reminder for the given session using the approved
    Content Template.  Opens its own DB session so it is safe to call from
    APScheduler jobs or asyncio.create_task — independent of the request lifecycle.

    Best-effort: logs errors but never raises, so callers are never blocked.
    """
    # Deferred imports to avoid circular dependencies and heavy startup cost
    from app.core.database import SessionLocal
    from app.core.config import settings
    from app.models.therapist import Therapist
    from app.services.whatsapp_service import send_whatsapp_message

    db = SessionLocal()
    try:
        session = db.query(TherapySession).filter(TherapySession.id == session_id).first()
        if not session:
            logger.warning(f"[appt_reminder] session {session_id} not found — skip")
            return

        patient = db.query(Patient).filter(Patient.id == session.patient_id).first()
        therapist = db.query(Therapist).filter(Therapist.id == session.therapist_id).first()

        if not patient or not therapist:
            logger.warning(f"[appt_reminder] session {session_id}: patient/therapist missing — skip")
            return

        # Respect patient consent
        if not patient.allow_ai_contact:
            logger.info(f"[appt_reminder] session {session_id}: patient opted out of AI contact — skip")
            return

        if not patient.phone_encrypted:
            logger.info(f"[appt_reminder] session {session_id}: patient has no phone — skip")
            return

        patient_phone = decrypt_data(patient.phone_encrypted)
        patient_name = (
            decrypt_data(patient.full_name_encrypted)
            if patient.full_name_encrypted else "מטופל"
        )

        # Format date/time for the template — DD.MM.YY, 24h time
        session_date_str = session.session_date.strftime("%d.%m.%y")
        session_time_str = session.start_time.strftime("%H:%M") if session.start_time else "לא צוינה"

        result = await send_whatsapp_message(
            patient_phone,
            "",
            content_sid=APPOINTMENT_TEMPLATE_SID,
            content_variables={
                "1": patient_name,
                "2": therapist.full_name,
                "3": session_date_str,
                "4": session_time_str,
            },
        )

        if result["status"] == "sent":
            logger.info(
                f"[appt_reminder] session {session_id}: reminder sent to {patient_phone} "
                f"(provider_id={result['provider_id']})"
            )
            # Persist the reminder as a Message record so it appears in the Messages screen
            try:
                from app.models.message import Message, MessageStatus, MessageDirection
                content_text = (
                    f"שלום {patient_name}, זוהי תזכורת לפגישתך עם {therapist.full_name} "
                    f"בתאריך {session_date_str} בשעה {session_time_str}."
                )
                msg_record = Message(
                    therapist_id=therapist.id,
                    patient_id=patient.id,
                    direction=MessageDirection.TO_PATIENT,
                    content=content_text,
                    status=MessageStatus.SENT,
                    requires_approval=False,
                    generated_by_ai=False,
                    sent_at=datetime.utcnow(),
                    message_type="appointment_reminder",
                    related_session_id=session_id,
                    channel="whatsapp",
                    recipient_phone=patient_phone,
                )
                db.add(msg_record)
                db.commit()
                logger.info(f"[appt_reminder] session {session_id}: message record saved (id={msg_record.id})")
            except Exception as save_exc:
                logger.error(f"[appt_reminder] session {session_id}: failed to save message record — {save_exc}")
                db.rollback()
        else:
            logger.error(f"[appt_reminder] session {session_id}: send failed — {result['error']}")

    except Exception as exc:
        logger.error(f"[appt_reminder] session {session_id}: unexpected error — {exc}")
    finally:
        db.close()


class SessionService:
    """Service for managing therapy sessions and generating summaries"""

    def __init__(self, db: Session):
        self.db = db
        self.audit_service = AuditService(db)

    def _write_generation_log(
        self,
        *,
        therapist_id: int,
        flow_type: FlowType,
        agent: TherapyAgent,
        session_id: Optional[int] = None,
        session_summary_id: Optional[int] = None,
        modality_pack_id: Optional[int] = None,
        generation_result=None,  # Optional[GenerationResult]; defaults to agent._last_result
    ) -> None:
        """
        Best-effort: write a row to ai_generation_log.
        Pass generation_result explicitly to log a result other than agent._last_result
        (e.g. from the CompletenessChecker).
        Never raises — a logging failure must not block the main flow.
        """
        try:
            last = generation_result if generation_result is not None else agent._last_result
            if last is None:
                return
            log_row = AIGenerationLog(
                therapist_id=therapist_id,
                flow_type=flow_type.value,
                session_id=session_id,
                session_summary_id=session_summary_id,
                modality_pack_id=modality_pack_id,
                model_used=last.model_used,
                route_reason=last.route_reason,
                prompt_version="1.0",
                prompt_tokens=last.prompt_tokens,
                completion_tokens=last.completion_tokens,
                generation_ms=last.generation_ms,
            )
            self.db.add(log_row)
            self.db.flush()
        except Exception as exc:
            logger.warning(f"_write_generation_log failed (non-blocking): {exc}")

    async def create_session(
        self,
        therapist_id: int,
        patient_id: int,
        session_date: date,
        session_type: SessionType = SessionType.INDIVIDUAL,
        duration_minutes: Optional[int] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        notify_patient: bool = False,
    ) -> TherapySession:
        """Create a new therapy session record"""

        # Verify patient belongs to therapist
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id
        ).first()

        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        # Get session number
        session_count = self.db.query(TherapySession).filter(
            TherapySession.patient_id == patient_id
        ).count()

        session = TherapySession(
            therapist_id=therapist_id,
            patient_id=patient_id,
            session_date=session_date,
            start_time=start_time,
            end_time=end_time,
            session_type=session_type,
            duration_minutes=duration_minutes,
            session_number=session_count + 1
        )

        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="create",
            resource_type="session",
            resource_id=session.id,
            action_details={
                "patient_id": patient_id,
                "session_date": str(session_date),
                "session_number": session.session_number
            }
        )

        logger.info(f"Created session {session.id} for patient {patient_id}")

        # ── Appointment reminders — only when therapist opted in ──────────────
        if notify_patient:
            # 1. Immediate confirmation (best-effort, does not block the response)
            asyncio.create_task(send_appointment_reminder(session.id))

            # 2. 24h-before reminder — only when a future start_time is provided
            if session.start_time:
                remind_at = session.start_time - timedelta(hours=24)
                if remind_at > datetime.now():
                    from app.core.scheduler import scheduler
                    scheduler.add_job(
                        send_appointment_reminder,
                        trigger="date",
                        run_date=remind_at,
                        args=[session.id],
                        id=f"appt_reminder_{session.id}",
                        replace_existing=True,
                    )
                    logger.info(
                        f"Scheduled 24h appointment reminder for session {session.id} at {remind_at}"
                    )

        return session

    async def _assemble_summary_input(
        self,
        session: TherapySession,
        raw_content: str,
        agent: TherapyAgent,
    ) -> SummaryInput:
        """
        Build a SummaryInput from session data and DB context.

        - last_approved_summary: only from rows where approved_by_therapist = True
        - open_tasks: exercises not yet completed for this patient
        """
        from sqlalchemy import desc
        from app.security.encryption import decrypt_data as _decrypt

        # Patient display name (best-effort — never raise)
        patient = self.db.query(Patient).filter(Patient.id == session.patient_id).first()
        client_name = "מטופל"
        if patient and patient.full_name_encrypted:
            try:
                client_name = _decrypt(patient.full_name_encrypted)
            except Exception:
                pass

        # Most recent approved summary for this patient (excluding the current session)
        last_approved_row = (
            self.db.query(SessionSummary)
            .join(TherapySession, TherapySession.summary_id == SessionSummary.id)
            .filter(
                TherapySession.patient_id == session.patient_id,
                TherapySession.id != session.id,
                SessionSummary.approved_by_therapist == True,  # noqa: E712
            )
            .order_by(desc(TherapySession.session_date))
            .first()
        )
        last_approved_text = last_approved_row.full_summary if last_approved_row else None

        # Open (incomplete) homework / exercises for this patient
        open_exercises = (
            self.db.query(Exercise)
            .filter(
                Exercise.patient_id == session.patient_id,
                Exercise.completed == False,  # noqa: E712
            )
            .all()
        )
        open_tasks = [e.description or "" for e in open_exercises if e.description]

        # Signature injection (Phase 6): prepend style guidance to rendering system prompt
        therapist_id = session.therapist_id
        sig_engine = SignatureEngine(self.db)
        sig_profile = await sig_engine.get_active_profile(therapist_id)
        signature_prompt = inject_into_prompt(sig_profile) if sig_profile else None

        return SummaryInput(
            raw_content=raw_content,
            client_name=client_name,
            session_number=session.session_number or 1,
            session_date=session.session_date,
            last_approved_summary=last_approved_text,
            open_tasks=open_tasks,
            modality_pack=agent.modality_pack,
            therapist_signature=signature_prompt,
        )

    async def generate_summary_from_audio(
        self,
        session_id: int,
        audio_bytes: bytes,
        filename: str,
        agent: TherapyAgent,
        therapist_id: int,
        language: str | None = None,
    ) -> SessionSummary:
        """
        PRD Golden Path: Record → Transcribe → Summarise → Review → Approve.

        1. Transcribe audio via AudioService (Whisper ASR).
        2. Feed transcript to agent.generate_session_summary (structured JSON).
        3. Store transcript *and* summary separately (PRD audit requirement).
        """
        from app.services.audio_service import AudioService

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        # Step 1 — ASR transcription
        audio_service = AudioService()
        logger.info(f"Transcribing audio for session {session_id}")
        transcript = await audio_service.transcribe_upload(
            file_bytes=audio_bytes,
            filename=filename,
            language=language,
        )

        # Step 2 — Summary 2.0: two-call pipeline (extraction → rendering)
        summary_input = await self._assemble_summary_input(
            session=session,
            raw_content=transcript,
            agent=agent,
        )
        pipeline = SummaryPipeline(agent)
        clinical_json_dict, rendered_text = await pipeline.run(summary_input)

        modality_pack = agent.modality_pack
        modality_pack_id = modality_pack.id if modality_pack else None
        ai_model = (
            pipeline._last_render_result.model_used if pipeline._last_render_result else None
        )
        ai_confidence = int(clinical_json_dict.get("confidence", 0.0) * 100)
        new_homework_val = clinical_json_dict.get("new_homework")
        homework_list = (
            [new_homework_val]
            if isinstance(new_homework_val, str) and new_homework_val
            else (new_homework_val if isinstance(new_homework_val, list) else [])
        )
        risk_notes = (clinical_json_dict.get("risk_assessment") or {}).get("notes")

        # Step 3 — Persist transcript + summary + AI metadata
        summary = SessionSummary(
            full_summary=rendered_text,
            topics_discussed=clinical_json_dict.get("key_themes", []),
            interventions_used=clinical_json_dict.get("interventions_used", []),
            patient_progress=clinical_json_dict.get("client_response", ""),
            homework_assigned=homework_list,
            next_session_plan=clinical_json_dict.get("next_session_focus"),
            mood_observed=clinical_json_dict.get("mood_observed"),
            risk_assessment=risk_notes,
            clinical_json=clinical_json_dict,
            transcript=transcript,
            generated_from="audio",
            therapist_edited=False,
            approved_by_therapist=False,
            ai_draft_text=rendered_text,   # rendered prose = what therapist sees and edits
            ai_model=ai_model,
            ai_prompt_version="2.0",
            ai_confidence=ai_confidence,
            modality_pack_id=modality_pack_id,
        )

        self.db.add(summary)
        self.db.flush()

        session.has_recording = True
        session.summary_id = summary.id
        self.db.flush()

        # Step 4 — Completeness check (fast model, best-effort)
        if agent.provider:
            checker = CompletenessChecker(agent.provider)
            completeness = await checker.check(
                summary_text=rendered_text,
                modality_pack=modality_pack,
            )
            summary.completeness_score = completeness.score if completeness.score >= 0 else None
            summary.completeness_data = completeness.to_dict()
            self.db.flush()
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.COMPLETENESS_CHECK,
                agent=agent,
                session_id=session.id,
                session_summary_id=summary.id,
                modality_pack_id=modality_pack_id,
                generation_result=checker._last_result,
            )

        # Log extraction call and render call separately
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.SESSION_SUMMARY,
            agent=agent,
            session_id=session.id,
            session_summary_id=summary.id,
            modality_pack_id=modality_pack_id,
            generation_result=pipeline._last_extraction_result,
        )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.SESSION_SUMMARY,
            agent=agent,
            session_id=session.id,
            session_summary_id=summary.id,
            modality_pack_id=modality_pack_id,
            generation_result=pipeline._last_render_result,
        )

        self.db.commit()
        self.db.refresh(summary)

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="session_summary",
            resource_id=summary.id,
            action_details={"session_id": session_id, "generated_from": "audio"},
        )

        logger.info(f"Generated summary from audio for session {session_id}")
        return summary

    async def generate_summary_from_text(
        self,
        session_id: int,
        therapist_notes: str,
        agent: TherapyAgent,
        therapist_id: int,
    ) -> SessionSummary:
        """
        Generate session summary from therapist's text notes.
        Uses AI agent to produce a structured JSON summary.
        """

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        # Summary 2.0: two-call pipeline (extraction → rendering)
        summary_input = await self._assemble_summary_input(
            session=session,
            raw_content=therapist_notes,
            agent=agent,
        )
        pipeline = SummaryPipeline(agent)
        clinical_json_dict, rendered_text = await pipeline.run(summary_input)

        modality_pack = agent.modality_pack
        modality_pack_id = modality_pack.id if modality_pack else None
        ai_model = (
            pipeline._last_render_result.model_used if pipeline._last_render_result else None
        )
        ai_confidence = int(clinical_json_dict.get("confidence", 0.0) * 100)
        new_homework_val = clinical_json_dict.get("new_homework")
        homework_list = (
            [new_homework_val]
            if isinstance(new_homework_val, str) and new_homework_val
            else (new_homework_val if isinstance(new_homework_val, list) else [])
        )
        risk_notes = (clinical_json_dict.get("risk_assessment") or {}).get("notes")

        summary = SessionSummary(
            full_summary=rendered_text,
            topics_discussed=clinical_json_dict.get("key_themes", []),
            interventions_used=clinical_json_dict.get("interventions_used", []),
            patient_progress=clinical_json_dict.get("client_response", ""),
            homework_assigned=homework_list,
            next_session_plan=clinical_json_dict.get("next_session_focus"),
            mood_observed=clinical_json_dict.get("mood_observed"),
            risk_assessment=risk_notes,
            clinical_json=clinical_json_dict,
            generated_from="text",
            therapist_edited=False,
            approved_by_therapist=False,
            ai_draft_text=rendered_text,   # rendered prose = what therapist sees and edits
            ai_model=ai_model,
            ai_prompt_version="2.0",
            ai_confidence=ai_confidence,
            modality_pack_id=modality_pack_id,
        )

        self.db.add(summary)
        self.db.flush()

        session.summary_id = summary.id
        self.db.flush()

        # Completeness check (fast model, best-effort)
        if agent.provider:
            checker = CompletenessChecker(agent.provider)
            completeness = await checker.check(
                summary_text=rendered_text,
                modality_pack=modality_pack,
            )
            summary.completeness_score = completeness.score if completeness.score >= 0 else None
            summary.completeness_data = completeness.to_dict()
            self.db.flush()
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.COMPLETENESS_CHECK,
                agent=agent,
                session_id=session.id,
                session_summary_id=summary.id,
                modality_pack_id=modality_pack_id,
                generation_result=checker._last_result,
            )

        # Log extraction and render calls separately
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.SESSION_SUMMARY,
            agent=agent,
            session_id=session.id,
            session_summary_id=summary.id,
            modality_pack_id=modality_pack_id,
            generation_result=pipeline._last_extraction_result,
        )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.SESSION_SUMMARY,
            agent=agent,
            session_id=session.id,
            session_summary_id=summary.id,
            modality_pack_id=modality_pack_id,
            generation_result=pipeline._last_render_result,
        )

        self.db.commit()
        self.db.refresh(summary)

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="session_summary",
            resource_id=summary.id,
            action_details={"session_id": session_id, "generated_from": "text"},
        )

        logger.info(f"Generated structured summary for session {session_id}")
        return summary

    async def get_summary(self, session_id: int, therapist_id: int) -> Optional[SessionSummary]:
        """Get the summary for a session, verifying therapist ownership."""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        return session.summary

    async def approve_summary(self, session_id: int, therapist_id: int) -> SessionSummary:
        """Therapist approves the generated summary"""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id
        ).first()

        if not session or not session.summary:
            raise ValueError("Session or summary not found")

        summary = session.summary
        summary.approved_by_therapist = True

        # Compute edit distance: how much did the therapist change the AI draft?
        # ai_draft_text = rendered prose at generation time; full_summary = current (possibly edited) text
        if summary.ai_draft_text and summary.full_summary:
            try:
                summary.therapist_edit_distance = compute_edit_distance(
                    summary.ai_draft_text, summary.full_summary
                )
            except Exception:
                pass  # non-blocking — best effort

        self.db.commit()

        # Signature learning hook (Phase 6) — fire-and-forget, non-blocking
        if summary.ai_draft_text:
            try:
                import asyncio
                sig_engine = SignatureEngine(self.db)
                asyncio.create_task(
                    sig_engine.record_approval(
                        therapist_id=therapist_id,
                        session_id=session.id,
                        ai_draft=summary.ai_draft_text,
                        approved_text=summary.full_summary or "",
                        provider=None,   # no provider in approval path; rebuild deferred
                    )
                )
            except RuntimeError:
                # No running event loop (e.g. in tests) — call synchronously
                pass

        # Audit log
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="approve",
            resource_type="session_summary",
            resource_id=summary.id
        )

        logger.info(f"Therapist approved summary {summary.id}")
        return summary

    async def edit_summary(
        self,
        session_id: int,
        therapist_id: int,
        edited_content: Dict[str, Any]
    ) -> SessionSummary:
        """Therapist edits the generated summary"""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id
        ).first()

        if not session or not session.summary:
            raise ValueError("Session or summary not found")

        summary = session.summary

        # Update fields
        for field, value in edited_content.items():
            if hasattr(summary, field):
                setattr(summary, field, value)

        summary.therapist_edited = True

        self.db.commit()

        logger.info(f"Therapist edited summary {summary.id}")
        return summary

    async def get_session(
        self,
        session_id: int,
        therapist_id: int,
    ) -> Optional[TherapySession]:
        """Get a single session by ID (verify ownership)"""

        return self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

    async def get_patient_sessions(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> List[TherapySession]:
        """Get all sessions for a patient (verify ownership)"""

        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()

        if not patient:
            raise ValueError("Patient not found")

        return (
            self.db.query(TherapySession)
            .filter(TherapySession.patient_id == patient_id)
            .order_by(TherapySession.session_date.desc())
            .all()
        )

    async def get_therapist_sessions(
        self,
        therapist_id: int,
        limit: int = 50,
    ) -> List[TherapySession]:
        """Get recent sessions for a therapist"""

        return (
            self.db.query(TherapySession)
            .filter(TherapySession.therapist_id == therapist_id)
            .order_by(TherapySession.session_date.desc())
            .limit(limit)
            .all()
        )

    async def get_sessions_by_date(
        self,
        therapist_id: int,
        target_date: date,
    ) -> List[Dict[str, Any]]:
        """Get sessions for a therapist on a specific date, with patient names."""

        sessions = (
            self.db.query(TherapySession)
            .filter(
                TherapySession.therapist_id == therapist_id,
                TherapySession.session_date == target_date,
            )
            .order_by(TherapySession.start_time.asc().nullslast())
            .all()
        )

        results = []
        for s in sessions:
            patient = self.db.query(Patient).filter(Patient.id == s.patient_id).first()
            if patient:
                try:
                    patient_name = decrypt_data(patient.full_name_encrypted)
                except Exception:
                    patient_name = patient.full_name_encrypted
            else:
                patient_name = f"מטופל #{s.patient_id}"

            # Convert session_type enum to its string value for JSON serialisation
            session_type_value = (
                s.session_type.value if s.session_type else None
            )

            results.append({
                "id": s.id,
                "patient_id": s.patient_id,
                "patient_name": patient_name,
                "session_date": s.session_date,
                "start_time": s.start_time,
                "end_time": s.end_time,
                "session_type": session_type_value,
                "session_number": s.session_number,
                "has_summary": s.summary_id is not None,
            })

        return results

    async def update_session(
        self,
        session_id: int,
        therapist_id: int,
        update_data: Dict[str, Any],
    ) -> TherapySession:
        """Update session details"""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

        if not session:
            raise ValueError("Session not found")

        protected = {"id", "created_at", "therapist_id", "patient_id"}
        for field, value in update_data.items():
            if field not in protected and hasattr(session, field):
                setattr(session, field, value)

        self.db.commit()
        self.db.refresh(session)

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="update",
            resource_type="session",
            resource_id=session.id,
            action_details=update_data,
        )

        logger.info(f"Updated session {session_id}")
        return session

    async def update_summary(
        self,
        session_id: int,
        therapist_id: int,
        updates: Dict[str, Any],
    ) -> SessionSummary:
        """Update (edit/approve) an existing session summary."""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

        if not session or not session.summary:
            raise ValueError("Session or summary not found")

        summary = session.summary

        # Allowed editable fields
        editable = {
            "full_summary", "topics_discussed", "interventions_used",
            "patient_progress", "homework_assigned", "next_session_plan",
            "mood_observed", "risk_assessment",
        }

        content_changed = False
        for field, value in updates.items():
            if field in editable and hasattr(summary, field):
                setattr(summary, field, value)
                content_changed = True

        if content_changed:
            summary.therapist_edited = True

        # Handle status change
        if "status" in updates:
            new_status = updates["status"]
            if new_status == "approved" or new_status == SummaryStatus.APPROVED:
                summary.status = SummaryStatus.APPROVED
                summary.approved_by_therapist = True
            elif new_status == "draft" or new_status == SummaryStatus.DRAFT:
                summary.status = SummaryStatus.DRAFT
                summary.approved_by_therapist = False

        self.db.commit()
        self.db.refresh(summary)

        action = "approve" if summary.status == SummaryStatus.APPROVED else "edit"
        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action=action,
            resource_type="session_summary",
            resource_id=summary.id,
            action_details={"session_id": session_id},
        )

        logger.info(f"Updated summary {summary.id} (status={summary.status})")
        return summary

    async def get_patient_summaries(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> List[Dict[str, Any]]:
        """Get all summaries for a patient's sessions, with session metadata."""

        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()

        if not patient:
            raise ValueError("Patient not found")

        sessions = (
            self.db.query(TherapySession)
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.desc())
            .all()
        )

        results = []
        for s in sessions:
            summary = s.summary
            if summary:
                results.append({
                    "session_id": s.id,
                    "session_date": s.session_date,
                    "session_number": s.session_number,
                    "summary": summary,
                })

        return results

    async def generate_patient_insight(
        self,
        patient_id: int,
        therapist_id: int,
        agent: TherapyAgent,
    ) -> PatientInsightResult:
        """Generate a cross-session AI insight report for a patient."""

        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()

        if not patient:
            raise ValueError("Patient not found")

        # Fetch only approved summaries, ordered chronologically
        sessions = (
            self.db.query(TherapySession)
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
            .all()
        )

        approved_summaries = []
        for s in sessions:
            summary = s.summary
            if summary and summary.status == SummaryStatus.APPROVED:
                approved_summaries.append({
                    "session_date": s.session_date,
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,
                    "topics_discussed": summary.topics_discussed,
                    "patient_progress": summary.patient_progress,
                    "risk_assessment": summary.risk_assessment,
                })

        if not approved_summaries:
            raise ValueError("אין סיכומים מאושרים עבור מטופל זה. יש לאשר לפחות סיכום אחד.")

        result = await agent.generate_patient_insight_summary(
            patient_name=patient.full_name_encrypted,  # display name
            summaries_timeline=approved_summaries,
        )

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="patient_insight",
            resource_id=patient_id,
            action_details={"approved_summaries_count": len(approved_summaries)},
        )

        logger.info(f"Generated insight summary for patient {patient_id} ({len(approved_summaries)} summaries)")
        return result

    async def generate_prep_brief(
        self,
        session_id: int,
        therapist_id: int,
        agent: TherapyAgent,
        max_summaries: int = 5,
    ) -> SessionPrepBriefResult:
        """Generate a concise AI prep brief for an upcoming session."""

        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()

        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        patient = self.db.query(Patient).filter(Patient.id == session.patient_id).first()
        if not patient:
            raise ValueError("Patient not found")

        # Fetch approved summaries for this patient, most recent last, limited
        patient_sessions = (
            self.db.query(TherapySession)
            .filter(
                TherapySession.patient_id == session.patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
            .all()
        )

        approved = []
        for s in patient_sessions:
            summary = s.summary
            if summary and summary.status == SummaryStatus.APPROVED:
                # Meeting prep must use the therapist-edited summary (full_summary),
                # not the original AI draft. full_summary is edited in-place.
                approved.append({
                    "session_date": s.session_date,
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,   # therapist-edited text
                    "topics_discussed": summary.topics_discussed,
                    "patient_progress": summary.patient_progress,
                    "homework_assigned": summary.homework_assigned,
                    "next_session_plan": summary.next_session_plan,
                    "risk_assessment": summary.risk_assessment,
                })

        # Keep only the last N approved summaries (graceful: proceed even with 0)
        recent = approved[-max_summaries:]

        # Fetch all open (incomplete) exercises for this patient
        open_exercises = (
            self.db.query(Exercise)
            .filter(
                Exercise.patient_id == session.patient_id,
                Exercise.therapist_id == therapist_id,
                Exercise.completed.is_(False),
            )
            .order_by(Exercise.created_at.asc())
            .all()
        )
        open_tasks = [
            {
                "description": ex.description,
                "created_at": str(ex.created_at)[:10] if ex.created_at else None,
            }
            for ex in open_exercises
        ]

        result = await agent.generate_session_prep_brief(
            patient_name=patient.full_name_encrypted,
            session_date=str(session.session_date),
            session_number=session.session_number,
            summaries_timeline=recent,
            open_tasks=open_tasks,
        )

        logger.info(f"Generated prep brief for session {session_id} ({len(recent)} summaries)")
        return result

    # ── Pre-Session Prep 2.0 (Phase 4) ───────────────────────────────────────

    _PREP_CACHE_SECONDS = 600  # 10 minutes

    async def generate_prep_v2(
        self,
        session_id: int,
        therapist_id: int,
        mode: PrepMode,
        agent: "TherapyAgent",
    ) -> dict:
        """
        Generate a structured pre-session prep brief using the Phase 4 two-call pipeline.

        SOURCE OF TRUTH RULE: only summaries where approved_by_therapist=True are used.
        Returns a dict suitable for the PrepResponse schema.

        Cache: if the same mode was generated in the last 10 minutes, returns the
        cached result from sessions.prep_json without an LLM call.
        """
        session = self.db.query(TherapySession).filter(
            TherapySession.id == session_id,
            TherapySession.therapist_id == therapist_id,
        ).first()
        if not session:
            raise ValueError("Session not found or does not belong to this therapist")

        patient = self.db.query(Patient).filter(Patient.id == session.patient_id).first()
        if not patient:
            raise ValueError("Patient not found")

        # Cache check — same mode, generated within last 10 minutes
        if (
            session.prep_json is not None
            and session.prep_mode == mode.value
            and session.prep_generated_at is not None
        ):
            age_seconds = (datetime.utcnow() - session.prep_generated_at).total_seconds()
            if age_seconds < self._PREP_CACHE_SECONDS:
                logger.info(
                    f"[prep_v2] session={session_id} mode={mode.value} — cache hit "
                    f"(age={age_seconds:.0f}s)"
                )
                return self._prep_cache_response(session)

        # Fetch ALL approved summaries for this patient, oldest → newest
        # SOURCE OF TRUTH: approved_by_therapist=True ONLY — never ai_draft_text
        patient_sessions_q = (
            self.db.query(TherapySession)
            .filter(
                TherapySession.patient_id == session.patient_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
            .all()
        )
        approved_summaries = []
        for s in patient_sessions_q:
            summary = s.summary
            if summary and summary.approved_by_therapist:
                approved_summaries.append({
                    "session_date": str(s.session_date),
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,
                    "topics_discussed": summary.topics_discussed,
                    "homework_assigned": summary.homework_assigned,
                    "next_session_plan": summary.next_session_plan,
                    "risk_assessment": summary.risk_assessment,
                    "mood_observed": summary.mood_observed,
                    "clinical_json": summary.clinical_json,
                })

        # Resolve modality info from the agent's modality pack
        modality_name = "generic_integrative"
        modality_prompt_module = None
        if agent.modality_pack:
            modality_name = agent.modality_pack.name
            modality_prompt_module = agent.modality_pack.prompt_module

        # Signature injection (Phase 6)
        sig_engine = SignatureEngine(self.db)
        sig_profile = await sig_engine.get_active_profile(therapist_id)
        signature_prompt = inject_into_prompt(sig_profile) if sig_profile else None

        prep_inp = PrepInput(
            client_id=session.patient_id,
            session_id=session_id,
            therapist_id=therapist_id,
            mode=mode,
            modality=modality_name,
            approved_summaries=approved_summaries,
            modality_prompt_module=modality_prompt_module,
            therapist_signature=signature_prompt,
        )

        pipeline = PrepPipeline(agent)
        result: PrepResult = await pipeline.run(prep_inp)

        # Completeness check on rendered text (fast model, best-effort)
        modality_pack = agent.modality_pack if hasattr(agent, "modality_pack") else None
        if agent.provider and result.rendered_text != "" and approved_summaries:
            checker = CompletenessChecker(agent.provider)
            completeness = await checker.check(
                summary_text=result.rendered_text,
                modality_pack=modality_pack,
            )
            result.completeness_score = completeness.score if completeness.score >= 0 else 0.0
            result.completeness_data = completeness.to_dict()
            # Log completeness check
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.COMPLETENESS_CHECK,
                agent=agent,
                session_id=session_id,
                modality_pack_id=modality_pack.id if modality_pack else None,
                generation_result=checker._last_result,
            )

        # Persist to session record
        session.prep_json = result.prep_json
        session.prep_mode = mode.value
        session.prep_completeness_score = result.completeness_score
        session.prep_completeness_data = result.completeness_data
        session.prep_generated_at = datetime.utcnow()
        self.db.flush()

        # Log extraction and rendering calls
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.PRE_SESSION_PREP,
            agent=agent,
            session_id=session_id,
            modality_pack_id=modality_pack.id if modality_pack else None,
            generation_result=pipeline._last_extraction_result,
        )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.PRE_SESSION_PREP,
            agent=agent,
            session_id=session_id,
            modality_pack_id=modality_pack.id if modality_pack else None,
            generation_result=pipeline._last_render_result,
        )

        logger.info(
            f"[prep_v2] session={session_id} mode={mode.value} "
            f"approved_summaries={len(approved_summaries)} "
            f"tokens={result.tokens_used} completeness={result.completeness_score:.2f}"
        )

        return {
            "rendered_text": result.rendered_text,
            "prep_json": result.prep_json,
            "mode": mode.value,
            "completeness_score": result.completeness_score,
            "sessions_analyzed": len(approved_summaries),
            "generated_at": session.prep_generated_at.isoformat(),
        }

    def _prep_cache_response(self, session: "TherapySession") -> dict:
        """Build a response dict from cached session.prep_json."""
        prep_json = session.prep_json or {}
        return {
            "rendered_text": None,   # cached — caller may need to regenerate for text
            "prep_json": prep_json,
            "mode": session.prep_mode,
            "completeness_score": session.prep_completeness_score,
            "sessions_analyzed": prep_json.get("sessions_analyzed", 0),
            "generated_at": session.prep_generated_at.isoformat() if session.prep_generated_at else None,
        }

    def _build_patient_summary_context(
        self,
        patient_id: int,
        therapist_id: int,
    ):
        """
        Shared helper: return (patient, approved_summaries, all_tasks, metrics).
        Used by both generate_deep_summary and generate_treatment_plan_preview.
        """
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found")

        all_sessions = (
            self.db.query(TherapySession)
            .filter(TherapySession.patient_id == patient_id)
            .order_by(TherapySession.session_date.asc())
            .all()
        )

        approved_summaries = []
        for s in all_sessions:
            summary = s.summary
            if summary and summary.status == SummaryStatus.APPROVED:
                approved_summaries.append({
                    "session_date": s.session_date,
                    "session_number": s.session_number,
                    "full_summary": summary.full_summary,
                    "topics_discussed": summary.topics_discussed,
                    "patient_progress": summary.patient_progress,
                    "homework_assigned": summary.homework_assigned,
                    "risk_assessment": summary.risk_assessment,
                })

        exercises = (
            self.db.query(Exercise)
            .filter(
                Exercise.patient_id == patient_id,
                Exercise.therapist_id == therapist_id,
            )
            .order_by(Exercise.created_at.asc())
            .all()
        )
        all_tasks = [
            {
                "description": ex.description,
                "completed": ex.completed,
                "created_at": str(ex.created_at)[:10] if ex.created_at else None,
                "completed_at": str(ex.completed_at)[:10] if ex.completed_at else None,
                "session_summary_id": ex.session_summary_id,
            }
            for ex in exercises
        ]

        # Basic session metrics
        session_dates = [s.session_date for s in all_sessions if s.session_date]
        long_gaps = []
        for i in range(1, len(session_dates)):
            gap = (session_dates[i] - session_dates[i - 1]).days
            if gap > 30:
                long_gaps.append({
                    "from": str(session_dates[i - 1]),
                    "to": str(session_dates[i]),
                    "days": gap,
                })
        metrics = {
            "total_sessions": len(all_sessions),
            "first_session_date": str(session_dates[0]) if session_dates else None,
            "last_session_date": str(session_dates[-1]) if session_dates else None,
            "long_gaps": long_gaps,
        }

        return patient, approved_summaries, all_tasks, metrics

    async def generate_deep_summary(
        self,
        patient_id: int,
        therapist_id: int,
        agent: TherapyAgent,
    ) -> DeepSummaryResult:
        """Generate a comprehensive deep treatment summary from all approved data."""

        patient, approved_summaries, all_tasks, metrics = self._build_patient_summary_context(
            patient_id, therapist_id
        )

        if not approved_summaries:
            raise ValueError("אין סיכומים מאושרים עבור מטופל זה. יש לאשר לפחות סיכום אחד.")

        therapist_locale = (agent.profile.language if agent.profile else None) or "he"

        result = await agent.generate_deep_summary(
            patient_name=patient.full_name_encrypted,
            approved_summaries=approved_summaries,
            all_tasks=all_tasks,
            metrics=metrics,
            therapist_locale=therapist_locale,
        )

        # ── Sanity checks: trim AI over-reach relative to actual data ─────────
        approved_count = len(approved_summaries)
        task_count = len(all_tasks)

        # Cap timeline_highlights when very little data exists
        max_highlights = max(1, min(approved_count * 2, 6))
        if len(result.timeline_highlights) > max_highlights:
            logger.warning(
                f"deep_summary patient={patient_id}: AI returned "
                f"{len(result.timeline_highlights)} timeline items for "
                f"{approved_count} approved summaries — trimming to {max_highlights}"
            )
            result.timeline_highlights = result.timeline_highlights[:max_highlights]

        # If no tasks exist but goals_and_tasks looks task-specific, log for visibility
        if task_count == 0 and result.goals_and_tasks:
            logger.info(
                f"deep_summary patient={patient_id}: no tasks in DB — "
                f"goals_and_tasks should only reflect session focus areas"
            )

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="patient_deep_summary",
            resource_id=patient_id,
            action_details={
                "approved_summaries_count": len(approved_summaries),
                "total_sessions": metrics["total_sessions"],
            },
        )

        logger.info(
            f"Generated deep summary for patient {patient_id} "
            f"({len(approved_summaries)} approved summaries)"
        )
        return result

    async def generate_treatment_plan_preview(
        self,
        patient_id: int,
        therapist_id: int,
        agent: TherapyAgent,
    ) -> TreatmentPlanResult:
        """Generate a treatment plan preview (goals, focus areas, interventions) from approved data."""

        patient, approved_summaries, all_tasks, _ = self._build_patient_summary_context(
            patient_id, therapist_id
        )

        therapist_locale = (agent.profile.language if agent.profile else None) or "he"

        result = await agent.generate_treatment_plan_preview(
            patient_name=patient.full_name_encrypted,
            approved_summaries=approved_summaries,
            all_tasks=all_tasks,
            therapist_locale=therapist_locale,
        )

        await self.audit_service.log_action(
            user_id=therapist_id,
            user_type="therapist",
            action="generate",
            resource_type="patient_treatment_plan_preview",
            resource_id=patient_id,
            action_details={"approved_summaries_count": len(approved_summaries)},
        )

        logger.info(f"Generated treatment plan preview for patient {patient_id}")
        return result
