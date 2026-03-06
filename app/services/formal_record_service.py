"""Formal record service — Israeli clinical documentation (Phase 5)."""

from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session

from app.ai.completeness import CompletenessChecker
from app.ai.formal_record import FormalRecordInput, FormalRecordPipeline, FormalRecordResult, RecordType
from app.ai.signature import SignatureEngine, inject_into_prompt
from app.ai.models import FlowType
from app.models.ai_log import AIGenerationLog
from app.models.formal_record import FormalRecord, RecordStatus
from app.models.session import Session as TherapySession, SessionSummary, SummaryStatus
from app.models.patient import Patient
from app.models.therapist import Therapist, TherapistProfile
from app.security.encryption import decrypt_data


class FormalRecordService:
    """
    Business logic for formal clinical records.

    Source-of-truth rule: only approved_by_therapist=True summaries are used.
    Never reads ai_draft_text or unapproved rows.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_approved_summaries(
        self,
        patient_id: int,
        therapist_id: int,
        session_ids: Optional[list[int]] = None,
    ) -> list[dict]:
        """
        Return approved summary dicts for a patient, oldest → newest.
        If session_ids is provided, restrict to those sessions only.
        SOURCE OF TRUTH: approved_by_therapist=True only.
        """
        query = (
            self.db.query(TherapySession)
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.therapist_id == therapist_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
        )
        if session_ids:
            query = query.filter(TherapySession.id.in_(session_ids))

        summaries = []
        for s in query.all():
            summary = s.summary
            if summary and summary.approved_by_therapist:
                summaries.append({
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
        return summaries

    def _build_therapist_profile_dict(self, therapist_id: int) -> dict:
        """Build a minimal therapist profile dict for record generation."""
        therapist = self.db.query(Therapist).filter(Therapist.id == therapist_id).first()
        profile = (
            self.db.query(TherapistProfile)
            .filter(TherapistProfile.therapist_id == therapist_id)
            .first()
        )
        return {
            "name": therapist.full_name if therapist else "",
            "license_type": profile.certifications if profile else "",
            "license_number": "",   # not yet modelled — therapist fills in via edit
            "modality": profile.therapeutic_approach.value if (profile and profile.therapeutic_approach) else "",
            "education": profile.education if profile else "",
        }

    def _write_generation_log(
        self,
        *,
        therapist_id: int,
        flow_type: FlowType,
        patient_id: int,
        record_id: Optional[int] = None,
        generation_result=None,
        completeness_score: Optional[float] = None,
        extra_notes: str = "",
    ) -> None:
        """Best-effort generation log. Never raises."""
        try:
            last = generation_result
            if last is None:
                return
            log_row = AIGenerationLog(
                therapist_id=therapist_id,
                flow_type=flow_type.value,
                session_id=None,
                session_summary_id=None,
                modality_pack_id=None,
                model_used=last.model_used,
                route_reason=last.route_reason,
                prompt_version="5.0",
                prompt_tokens=last.prompt_tokens,
                completion_tokens=last.completion_tokens,
                generation_ms=last.generation_ms,
                completeness_score=completeness_score,
            )
            self.db.add(log_row)
            self.db.flush()
        except Exception as exc:
            logger.warning(f"formal_record _write_generation_log failed (non-blocking): {exc}")

    # ── Core operations ───────────────────────────────────────────────────────

    async def create_formal_record(
        self,
        patient_id: int,
        therapist_id: int,
        record_type: RecordType,
        session_ids: Optional[list[int]],
        additional_context: Optional[str],
        provider,  # AIProvider
    ) -> FormalRecord:
        """
        Generate and persist a formal clinical record.

        Returns the saved FormalRecord ORM object (status=draft).
        """
        # Ownership check
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        approved_summaries = self._fetch_approved_summaries(
            patient_id=patient_id,
            therapist_id=therapist_id,
            session_ids=session_ids,
        )
        therapist_profile = self._build_therapist_profile_dict(therapist_id)

        # Signature injection (Phase 6)
        sig_engine = SignatureEngine(self.db)
        sig_profile = await sig_engine.get_active_profile(therapist_id)
        signature_prompt = inject_into_prompt(sig_profile) if sig_profile else None

        inp = FormalRecordInput(
            client_id=patient_id,
            therapist_id=therapist_id,
            record_type=record_type,
            session_ids=session_ids or [],
            approved_summaries=approved_summaries,
            therapist_profile=therapist_profile,
            additional_context=additional_context,
            therapist_signature=signature_prompt,
        )

        pipeline = FormalRecordPipeline(provider)
        result: FormalRecordResult = await pipeline.run(inp)

        # Completeness check (fast model, best-effort)
        completeness_score = None
        if provider and result.rendered_text and approved_summaries:
            checker = CompletenessChecker(provider)
            completeness = await checker.check(summary_text=result.rendered_text)
            completeness_score = completeness.score if completeness.score >= 0 else None
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.COMPLETENESS_CHECK,
                patient_id=patient_id,
                generation_result=checker._last_result,
            )

        # Persist record
        record = FormalRecord(
            patient_id=patient_id,
            therapist_id=therapist_id,
            record_type=record_type.value,
            record_json=result.record_json,
            rendered_text=result.rendered_text,
            status=RecordStatus.DRAFT.value,
            model_used=result.model_used,
            tokens_used=result.tokens_used,
        )
        self.db.add(record)
        self.db.flush()

        # Log extraction and render calls
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.FORMAL_RECORD,
            patient_id=patient_id,
            record_id=record.id,
            generation_result=pipeline._last_extraction_result,
            completeness_score=completeness_score,
        )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.FORMAL_RECORD,
            patient_id=patient_id,
            record_id=record.id,
            generation_result=pipeline._last_render_result,
        )

        logger.info(
            f"[formal_record] patient={patient_id} type={record_type.value} "
            f"approved_summaries={len(approved_summaries)} "
            f"tokens={result.tokens_used} record_id={record.id}"
        )
        return record

    def approve_formal_record(self, record_id: int, therapist_id: int) -> FormalRecord:
        """Set record status to approved. Raises ValueError if not found or wrong owner."""
        record = self.db.query(FormalRecord).filter(
            FormalRecord.id == record_id,
            FormalRecord.therapist_id == therapist_id,
        ).first()
        if not record:
            raise ValueError("Formal record not found or does not belong to this therapist")
        record.status = RecordStatus.APPROVED.value
        record.approved_at = datetime.utcnow()
        self.db.flush()
        return record

    def list_formal_records(
        self,
        patient_id: int,
        therapist_id: int,
        page: int = 1,
        per_page: int = 20,
    ) -> tuple[list[FormalRecord], int]:
        """
        Return paginated formal records for a patient.
        Returns (records, total_count).
        """
        # Ownership check
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        base_query = self.db.query(FormalRecord).filter(
            FormalRecord.patient_id == patient_id,
            FormalRecord.therapist_id == therapist_id,
        )
        total = base_query.count()
        records = (
            base_query
            .order_by(FormalRecord.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        return records, total
