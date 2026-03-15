"""Deep Summary + Therapist Reference Vault service — Phase 8."""

from datetime import datetime
from typing import Optional

from loguru import logger
from sqlalchemy.orm import Session, joinedload

from app.ai.deep_summary import (
    DeepSummaryInput,
    DeepSummaryPipeline,
    DeepSummaryResult,
    VaultEntry,
    VaultExtractor,
    VaultRetriever,
    _MAX_VAULT_ENTRIES,
)
from app.ai.models import FlowType
from app.ai.signature import SignatureEngine, inject_into_prompt
from app.models.ai_log import AIGenerationLog
from app.models.deep_summary import DeepSummary, DeepSummaryStatus
from app.models.patient import Patient
from app.models.reference_vault import TherapistReferenceVault
from app.models.session import Session as TherapySession
from app.models.therapist import Therapist, TherapistProfile
from app.core.ai_context import build_ai_context_for_patient


class DeepSummaryService:
    """
    Business logic for deep summaries and the therapist reference vault.

    Source-of-truth rule: only approved_by_therapist=True summaries are used.
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _fetch_approved_summaries(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> list[dict]:
        """Return ALL approved summary dicts for a patient, oldest → newest."""
        query = (
            self.db.query(TherapySession)
            .options(joinedload(TherapySession.summary))
            .filter(
                TherapySession.patient_id == patient_id,
                TherapySession.therapist_id == therapist_id,
                TherapySession.summary_id.isnot(None),
            )
            .order_by(TherapySession.session_date.asc())
        )

        summaries = []
        for s in query.all():
            summary = s.summary
            if summary and summary.approved_by_therapist:
                summaries.append({
                    "session_date": str(s.session_date),
                    "session_number": s.session_number,
                    "session_id": s.id,
                    "full_summary": summary.full_summary,
                    "topics_discussed": summary.topics_discussed,
                    "homework_assigned": summary.homework_assigned,
                    "next_session_plan": summary.next_session_plan,
                    "risk_assessment": summary.risk_assessment,
                    "mood_observed": summary.mood_observed,
                })
        return summaries

    def _build_therapist_profile_dict(self, therapist_id: int) -> dict:
        therapist = self.db.query(Therapist).filter(Therapist.id == therapist_id).first()
        profile = (
            self.db.query(TherapistProfile)
            .filter(TherapistProfile.therapist_id == therapist_id)
            .first()
        )
        return {
            "name": therapist.full_name if therapist else "",
            "modality": profile.therapeutic_approach.value if (profile and profile.therapeutic_approach) else "",
        }

    def _get_active_plan_json(self, patient_id: int, therapist_id: int) -> Optional[dict]:
        """Return the active treatment plan JSON, or None."""
        try:
            from app.models.treatment_plan import PlanStatus, TreatmentPlan

            plan = (
                self.db.query(TreatmentPlan)
                .filter(
                    TreatmentPlan.patient_id == patient_id,
                    TreatmentPlan.therapist_id == therapist_id,
                    TreatmentPlan.status == PlanStatus.ACTIVE.value,
                )
                .order_by(TreatmentPlan.version.desc())
                .first()
            )
            return plan.plan_json if plan else None
        except Exception:
            return None

    def _write_generation_log(
        self,
        *,
        therapist_id: int,
        flow_type: FlowType,
        patient_id: int,
        generation_result=None,
    ) -> None:
        """Best-effort telemetry. Never raises."""
        try:
            if generation_result is None:
                return
            log_row = AIGenerationLog(
                therapist_id=therapist_id,
                flow_type=flow_type.value,
                session_id=None,
                session_summary_id=None,
                modality_pack_id=None,
                model_used=generation_result.model_used,
                route_reason=generation_result.route_reason,
                prompt_version="8.0",
                prompt_tokens=generation_result.prompt_tokens,
                completion_tokens=generation_result.completion_tokens,
                generation_ms=generation_result.generation_ms,
            )
            self.db.add(log_row)
            self.db.flush()
        except Exception as exc:
            logger.warning(f"deep_summary _write_generation_log failed (non-blocking): {exc}")

    # ── Core operations ───────────────────────────────────────────────────────

    async def generate_deep_summary(
        self,
        patient_id: int,
        therapist_id: int,
        provider,  # AIProvider
    ) -> DeepSummary:
        """
        Generate a new deep summary and extract vault entries.

        Returns the saved DeepSummary ORM object (status=draft).
        Vault entries are extracted and stored as a side effect.
        """
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        approved_summaries = self._fetch_approved_summaries(patient_id, therapist_id)
        if not approved_summaries:
            raise ValueError(
                "No approved summaries found. "
                "Approve at least one session summary before generating a deep summary."
            )

        therapist_profile = self._build_therapist_profile_dict(therapist_id)
        modality = therapist_profile.get("modality", "")
        treatment_plan = self._get_active_plan_json(patient_id, therapist_id)

        # Retrieve existing vault entries to inject as context
        retriever = VaultRetriever(self.db)
        vault_entries = await retriever.get_relevant_entries(
            client_id=patient_id,
            therapist_id=therapist_id,
            query_tags=[],   # fetch all — no specific query tags for full deep summary
            limit=8,
        )
        vault_context: Optional[str] = None
        if vault_entries:
            parts = []
            for e in vault_entries:
                parts.append(f"[{e['entry_type']}] {e['content']}")
            vault_context = "\n".join(parts)

        # Signature injection
        sig_engine = SignatureEngine(self.db)
        sig_profile = await sig_engine.get_active_profile(therapist_id)
        signature_prompt = inject_into_prompt(sig_profile) if sig_profile else None

        # AI protocol context
        _profile_orm = (
            self.db.query(TherapistProfile)
            .filter(TherapistProfile.therapist_id == therapist_id)
            .first()
        )
        ai_ctx = build_ai_context_for_patient(_profile_orm, patient)

        inp = DeepSummaryInput(
            client_id=patient_id,
            therapist_id=therapist_id,
            modality=modality,
            approved_summaries=approved_summaries,
            treatment_plan=treatment_plan,
            therapist_signature=signature_prompt,
            ai_context=ai_ctx,
        )

        pipeline = DeepSummaryPipeline(provider)
        result: DeepSummaryResult = await pipeline.run(inp, vault_context=vault_context)

        # Telemetry — one log per extraction/synthesis/render call
        for extraction_result in pipeline._extraction_results:
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.DEEP_SUMMARY,
                patient_id=patient_id,
                generation_result=extraction_result,
            )
        if pipeline._synthesis_result is not None:
            self._write_generation_log(
                therapist_id=therapist_id,
                flow_type=FlowType.DEEP_SUMMARY,
                patient_id=patient_id,
                generation_result=pipeline._synthesis_result,
            )
        self._write_generation_log(
            therapist_id=therapist_id,
            flow_type=FlowType.DEEP_SUMMARY,
            patient_id=patient_id,
            generation_result=pipeline._render_result,
        )

        # Extract and store vault entries
        source_session_ids = [s.get("session_id") for s in approved_summaries if s.get("session_id")]
        vault_created = await self._extract_and_store_vault_entries(
            summary_json=result.summary_json,
            client_id=patient_id,
            therapist_id=therapist_id,
            source_session_ids=source_session_ids,
            provider=provider,
        )

        deep_summary = DeepSummary(
            patient_id=patient_id,
            therapist_id=therapist_id,
            summary_json=result.summary_json,
            rendered_text=result.rendered_text,
            sessions_covered=len(approved_summaries),
            status=DeepSummaryStatus.DRAFT.value,
            model_used=result.model_used,
            tokens_used=result.tokens_used,
        )
        self.db.add(deep_summary)
        self.db.flush()

        logger.info(
            f"[deep_summary] GENERATE patient={patient_id} "
            f"sessions={len(approved_summaries)} tokens={result.tokens_used} "
            f"vault_entries={vault_created} id={deep_summary.id}"
        )
        return deep_summary

    def get_latest_deep_summary(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> Optional[DeepSummary]:
        """Return the most recent deep summary for a patient, or None."""
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        return (
            self.db.query(DeepSummary)
            .filter(
                DeepSummary.patient_id == patient_id,
                DeepSummary.therapist_id == therapist_id,
            )
            .order_by(DeepSummary.created_at.desc())
            .first()
        )

    def get_deep_summary_history(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> list[DeepSummary]:
        """Return all deep summaries for a patient, newest first."""
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        return (
            self.db.query(DeepSummary)
            .filter(
                DeepSummary.patient_id == patient_id,
                DeepSummary.therapist_id == therapist_id,
            )
            .order_by(DeepSummary.created_at.desc())
            .all()
        )

    def approve_deep_summary(self, summary_id: int, therapist_id: int) -> DeepSummary:
        """Approve a deep summary. Raises ValueError if not found or wrong owner."""
        summary = self.db.query(DeepSummary).filter(
            DeepSummary.id == summary_id,
            DeepSummary.therapist_id == therapist_id,
        ).first()
        if not summary:
            raise ValueError("Deep summary not found or does not belong to this therapist")
        summary.status = DeepSummaryStatus.APPROVED.value
        summary.approved_at = datetime.utcnow()
        self.db.flush()
        return summary

    def delete_deep_summary(self, summary_id: int, therapist_id: int) -> None:
        """Hard-delete a deep summary. Raises ValueError if not found or wrong owner."""
        summary = self.db.query(DeepSummary).filter(
            DeepSummary.id == summary_id,
            DeepSummary.therapist_id == therapist_id,
        ).first()
        if not summary:
            raise ValueError("Deep summary not found or does not belong to this therapist")
        self.db.delete(summary)
        self.db.flush()

    # ── Vault operations ──────────────────────────────────────────────────────

    async def _extract_and_store_vault_entries(
        self,
        *,
        summary_json: dict,
        client_id: int,
        therapist_id: int,
        source_session_ids: list[int],
        provider,
    ) -> int:
        """
        Extract clinical insights from summary_json and store to reference vault.

        Deduplicates by content. Enforces per-client cap of _MAX_VAULT_ENTRIES.
        Returns count of entries actually stored.
        Never raises.
        """
        try:
            extractor = VaultExtractor(provider)
            entries: list[VaultEntry] = await extractor.extract_entries(
                summary_json=summary_json,
                client_id=client_id,
                therapist_id=therapist_id,
                source_session_ids=source_session_ids,
            )

            # Telemetry for vault extraction call
            if extractor._last_result:
                self._write_generation_log(
                    therapist_id=therapist_id,
                    flow_type=FlowType.VAULT_EXTRACTION,
                    patient_id=client_id,
                    generation_result=extractor._last_result,
                )

            if not entries:
                return 0

            # Check current vault count for this client (enforce cap)
            current_count = (
                self.db.query(TherapistReferenceVault)
                .filter(
                    TherapistReferenceVault.therapist_id == therapist_id,
                    TherapistReferenceVault.client_id == client_id,
                    TherapistReferenceVault.is_active == True,  # noqa: E712
                )
                .count()
            )

            # Fetch existing content for deduplication
            existing_rows = (
                self.db.query(TherapistReferenceVault.content)
                .filter(
                    TherapistReferenceVault.therapist_id == therapist_id,
                    TherapistReferenceVault.client_id == client_id,
                    TherapistReferenceVault.is_active == True,  # noqa: E712
                )
                .all()
            )
            existing_contents = {row.content for row in existing_rows}

            stored = 0
            for entry in entries:
                if current_count + stored >= _MAX_VAULT_ENTRIES:
                    logger.info(
                        f"[vault] cap reached for client={client_id} — "
                        f"skipping remaining {len(entries) - stored} entries"
                    )
                    break

                # Skip duplicates (exact content match)
                if entry.content in existing_contents:
                    continue

                vault_row = TherapistReferenceVault(
                    therapist_id=therapist_id,
                    client_id=client_id,
                    title=None,   # AI-extracted entries have no title
                    content=entry.content,
                    entry_type=entry.entry_type,
                    tags=entry.tags,
                    source_session_ids=entry.source_session_ids,
                    confidence=entry.confidence,
                    source_type="ai",
                    is_active=True,
                )
                self.db.add(vault_row)
                existing_contents.add(entry.content)
                stored += 1

            if stored:
                self.db.flush()

            logger.info(
                f"[vault] EXTRACT client={client_id} "
                f"candidates={len(entries)} stored={stored} skipped={len(entries) - stored}"
            )
            return stored

        except Exception as exc:
            logger.warning(
                f"_extract_and_store_vault_entries client={client_id} "
                f"failed (non-blocking): {exc!r}"
            )
            return 0

    def get_vault_entries(
        self,
        patient_id: int,
        therapist_id: int,
    ) -> dict[str, list[dict]]:
        """
        Return all active vault entries for a client, grouped by entry_type.

        Returns dict mapping entry_type → list of entry dicts.
        """
        patient = self.db.query(Patient).filter(
            Patient.id == patient_id,
            Patient.therapist_id == therapist_id,
        ).first()
        if not patient:
            raise ValueError("Patient not found or does not belong to this therapist")

        rows = (
            self.db.query(TherapistReferenceVault)
            .filter(
                TherapistReferenceVault.therapist_id == therapist_id,
                TherapistReferenceVault.client_id == patient_id,
                TherapistReferenceVault.is_active == True,  # noqa: E712
            )
            .order_by(TherapistReferenceVault.id.desc())
            .all()
        )

        grouped: dict[str, list[dict]] = {}
        for row in rows:
            entry_type = row.entry_type or "clinical_pattern"
            grouped.setdefault(entry_type, []).append({
                "id": row.id,
                "entry_type": entry_type,
                "content": row.content,
                "tags": row.tags or [],
                "confidence": row.confidence,
                "source_session_ids": row.source_session_ids or [],
                "source_type": row.source_type,
            })
        return grouped

    def delete_vault_entry(self, entry_id: int, therapist_id: int) -> None:
        """Soft-delete a vault entry. Raises ValueError if not found or wrong owner."""
        entry = self.db.query(TherapistReferenceVault).filter(
            TherapistReferenceVault.id == entry_id,
            TherapistReferenceVault.therapist_id == therapist_id,
        ).first()
        if not entry:
            raise ValueError("Vault entry not found or does not belong to this therapist")
        entry.is_active = False
        self.db.flush()
