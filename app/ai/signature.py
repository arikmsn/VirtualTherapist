"""
Therapist Signature Engine 2.0 (Phase 6).

Learns the therapist's personal writing style from approved edits and injects
a formatted style prompt into every rendering call.

Design:
  record_approval() — DB-only, called after every summary approval (non-blocking)
  rebuild_profile() — single fast-model LLM call, triggered every 5 approvals
  get_active_profile() — reads current SignatureProfile from DB
  inject_into_prompt() — returns formatted Hebrew style guidance string

Source-of-truth: only samples from approved summaries (approved_by_therapist=True)
enter raw_samples. Raw AI drafts that were never approved do not influence the profile.

Sample cap: raw_samples is capped at 20 most recent entries to avoid unbounded growth.
Activation threshold: profile is not injected until approved_sample_count >= min_samples_required (default 5).
"""

from __future__ import annotations

import difflib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from loguru import logger

from app.ai.models import FlowType
from app.ai.router import ModelRouter

if TYPE_CHECKING:
    from app.ai.provider import AIProvider
    from sqlalchemy.orm import Session as DBSession


# ── Constants ─────────────────────────────────────────────────────────────────

_MAX_SAMPLES = 20          # raw_samples array cap
_REBUILD_EVERY_N = 5       # trigger rebuild every N approvals (5, 10, 15, …)


# ── Dataclasses ───────────────────────────────────────────────────────────────

@dataclass
class SignatureSample:
    session_id: int
    ai_draft: str
    approved_text: str
    edit_distance: int       # similarity ratio 0–100 (100 = no edits = identical)
    created_at: str          # ISO8601 string

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "ai_draft": self.ai_draft,
            "approved_text": self.approved_text,
            "edit_distance": self.edit_distance,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SignatureSample":
        return cls(
            session_id=d["session_id"],
            ai_draft=d["ai_draft"],
            approved_text=d["approved_text"],
            edit_distance=d["edit_distance"],
            created_at=d["created_at"],
        )


@dataclass
class SignatureProfile:
    therapist_id: int
    is_active: bool
    approved_sample_count: int
    style_summary: str
    style_examples: list[str]
    style_version: int
    min_samples_required: int
    preferred_sentence_length: Optional[str] = None   # short|medium|long
    preferred_voice: Optional[str] = None              # active|passive|mixed
    uses_clinical_jargon: Optional[bool] = None
    last_updated_at: Optional[datetime] = None


# ── Similarity ratio ──────────────────────────────────────────────────────────

def _compute_similarity(text_a: str, text_b: str) -> int:
    """
    Compute similarity between two strings as an integer 0–100.
    100 = identical (no edits). 0 = completely different.
    Uses difflib.SequenceMatcher ratio.
    """
    if not text_a and not text_b:
        return 100
    if not text_a or not text_b:
        return 0
    ratio = difflib.SequenceMatcher(None, text_a, text_b, autojunk=False).ratio()
    return round(ratio * 100)


# ── Rebuild prompt ────────────────────────────────────────────────────────────

_REBUILD_SYSTEM = (
    "You are analyzing a therapist's editing patterns to extract their writing style. "
    "Respond in JSON only. No markdown fences, no explanation."
)


def _build_rebuild_prompt(samples: list[SignatureSample]) -> str:
    pairs = []
    for i, s in enumerate(samples, 1):
        ai_excerpt = s.ai_draft[:400]
        approved_excerpt = s.approved_text[:400]
        pairs.append(
            f"[Pair {i} — similarity {s.edit_distance}%]\n"
            f"AI wrote:\n{ai_excerpt}\n\n"
            f"Therapist approved:\n{approved_excerpt}"
        )
    sample_block = "\n\n---\n\n".join(pairs)

    return (
        f"Here are {len(samples)} pairs of AI-generated drafts and the therapist's approved versions.\n\n"
        f"{sample_block}\n\n"
        "Extract the therapist's writing style. Output ONLY valid JSON with these exact keys:\n"
        '{\n'
        '  "style_summary": "2–3 sentences in Hebrew describing their writing style",\n'
        '  "style_examples": ["excerpt 1 (max 30 words)", "excerpt 2", "excerpt 3"],\n'
        '  "preferred_sentence_length": "short" | "medium" | "long",\n'
        '  "preferred_voice": "active" | "passive" | "mixed",\n'
        '  "uses_clinical_jargon": true | false\n'
        '}'
    )


# ── inject_into_prompt output ─────────────────────────────────────────────────

def inject_into_prompt(profile: SignatureProfile) -> str:
    """
    Return a formatted Hebrew style guidance string to prepend to any
    rendering system prompt. Returns "" if profile is not active.
    """
    if not profile.is_active:
        return ""

    length_he = {
        "short": "קצרים",
        "medium": "בינוניים",
        "long": "ארוכים",
    }.get(profile.preferred_sentence_length or "medium", "בינוניים")

    voice_he = {
        "active": "גוף פעיל",
        "passive": "גוף סביל",
        "mixed": "שילוב גוף פעיל וסביל",
    }.get(profile.preferred_voice or "mixed", "שילוב")

    jargon_he = "עם" if profile.uses_clinical_jargon else "ללא"

    examples_block = "\n".join(
        f'- "{ex}"' for ex in (profile.style_examples or [])[:3]
    )

    lines = [
        f"סגנון הכתיבה המועדף של המטפל (למד מ-{profile.approved_sample_count} עריכות מאושרות):",
        profile.style_summary or "",
    ]
    if examples_block:
        lines.append("\nדוגמאות לסגנון:")
        lines.append(examples_block)
    lines.append(
        f"\nהנחיות: השתמש במשפטים {length_he}, {voice_he}, "
        f"{jargon_he} ז'רגון קליני."
    )
    return "\n".join(lines)


# ── SignatureEngine ───────────────────────────────────────────────────────────

class SignatureEngine:
    """
    Manages the therapist signature profile lifecycle:
    record → store → rebuild (every 5 approvals) → inject.

    Usage:
        engine = SignatureEngine(db)
        await engine.record_approval(therapist_id, session_id, ai_draft, approved_text, provider)
        profile = await engine.get_active_profile(therapist_id)
        if profile:
            prompt_prefix = inject_into_prompt(profile)
    """

    def __init__(self, db: "DBSession") -> None:
        self.db = db
        self._router = ModelRouter()

    def _get_or_create_profile(self, therapist_id: int):
        """Get existing profile row or create a new one."""
        from app.models.signature import TherapistSignatureProfile
        profile = (
            self.db.query(TherapistSignatureProfile)
            .filter(TherapistSignatureProfile.therapist_id == therapist_id)
            .first()
        )
        if not profile:
            profile = TherapistSignatureProfile(
                therapist_id=therapist_id,
                approved_sample_count=0,
                approved_summary_count=0,
                raw_samples=[],
                is_active=False,
                style_version=1,
                min_samples_required=5,
            )
            self.db.add(profile)
            self.db.flush()
        return profile

    async def record_approval(
        self,
        therapist_id: int,
        session_id: int,
        ai_draft: str,
        approved_text: str,
        provider: Optional["AIProvider"] = None,
    ) -> None:
        """
        Record a new sample from an approved summary.
        Triggers rebuild_profile() when the threshold or 5-multiple is hit.
        Non-blocking: exceptions are caught and logged.
        """
        try:
            profile = self._get_or_create_profile(therapist_id)

            similarity = _compute_similarity(ai_draft, approved_text)
            sample = SignatureSample(
                session_id=session_id,
                ai_draft=ai_draft[:2000],        # truncate to avoid huge raw_samples
                approved_text=approved_text[:2000],
                edit_distance=similarity,
                created_at=datetime.utcnow().isoformat(),
            )

            # Maintain capped list (keep most recent _MAX_SAMPLES)
            current = list(profile.raw_samples or [])
            current.append(sample.to_dict())
            if len(current) > _MAX_SAMPLES:
                current = current[-_MAX_SAMPLES:]
            profile.raw_samples = current
            profile.approved_sample_count = len(current)
            self.db.flush()

            # Trigger rebuild if threshold first reached OR at every N-multiple
            count = profile.approved_sample_count
            min_req = profile.min_samples_required
            should_rebuild = (
                provider is not None
                and count >= min_req
                and (count == min_req or count % _REBUILD_EVERY_N == 0)
            )
            if should_rebuild:
                await self.rebuild_profile(therapist_id, provider)

        except Exception as exc:
            logger.warning(f"SignatureEngine.record_approval failed (non-blocking): {exc!r}")

    async def rebuild_profile(self, therapist_id: int, provider: "AIProvider") -> None:
        """
        Run a single fast-model LLM call to extract style from raw_samples.
        Updates profile fields in-place. Activates profile when count >= threshold.
        Never raises.
        """
        try:
            profile = self._get_or_create_profile(therapist_id)
            samples_raw = list(profile.raw_samples or [])
            if not samples_raw:
                return

            samples = [SignatureSample.from_dict(d) for d in samples_raw]
            prompt = _build_rebuild_prompt(samples)

            model_id, route_reason = self._router.resolve(FlowType.COMPLETENESS_CHECK)
            result = await provider.generate(
                messages=[
                    {"role": "system", "content": _REBUILD_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                model=model_id,
                flow_type=FlowType.COMPLETENESS_CHECK,
                route_reason=route_reason,
            )

            # Parse LLM response
            raw = result.content.strip()
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            raw = raw.strip()

            data = json.loads(raw)

            # Update profile
            profile.style_summary = str(data.get("style_summary", ""))
            profile.style_examples = list(data.get("style_examples", []))[:3]
            profile.preferred_sentence_length = str(data.get("preferred_sentence_length", "medium"))
            profile.preferred_voice = str(data.get("preferred_voice", "mixed"))
            profile.uses_clinical_jargon = bool(data.get("uses_clinical_jargon", False))
            profile.last_updated_at = datetime.utcnow()
            profile.style_version = (profile.style_version or 1) + 1
            # Activate if enough samples
            if profile.approved_sample_count >= profile.min_samples_required:
                profile.is_active = True
            self.db.flush()

            logger.info(
                f"[signature] therapist={therapist_id} rebuilt profile "
                f"v{profile.style_version} from {len(samples)} samples"
            )

        except Exception as exc:
            logger.warning(f"SignatureEngine.rebuild_profile failed (non-blocking): {exc!r}")

    async def get_active_profile(self, therapist_id: int) -> Optional[SignatureProfile]:
        """
        Return a SignatureProfile if one exists and is_active=True.
        Returns None if no profile or not yet activated.
        """
        from app.models.signature import TherapistSignatureProfile
        row = (
            self.db.query(TherapistSignatureProfile)
            .filter(
                TherapistSignatureProfile.therapist_id == therapist_id,
                TherapistSignatureProfile.is_active == True,  # noqa: E712
            )
            .first()
        )
        if not row:
            return None
        # Must have style_summary to be usable
        if not row.style_summary:
            return None

        return SignatureProfile(
            therapist_id=therapist_id,
            is_active=True,
            approved_sample_count=row.approved_sample_count or 0,
            style_summary=row.style_summary or "",
            style_examples=list(row.style_examples or []),
            style_version=row.style_version or 1,
            min_samples_required=row.min_samples_required or 5,
            preferred_sentence_length=row.preferred_sentence_length,
            preferred_voice=row.preferred_voice,
            uses_clinical_jargon=row.uses_clinical_jargon,
            last_updated_at=row.last_updated_at,
        )

    def reset_profile(self, therapist_id: int) -> None:
        """
        Clear raw_samples, set is_active=False, reset counters.
        Therapist can start fresh if they don't like the learned style.
        """
        from app.models.signature import TherapistSignatureProfile
        row = (
            self.db.query(TherapistSignatureProfile)
            .filter(TherapistSignatureProfile.therapist_id == therapist_id)
            .first()
        )
        if row:
            row.raw_samples = []
            row.approved_sample_count = 0
            row.is_active = False
            row.style_summary = None
            row.style_examples = None
            row.preferred_sentence_length = None
            row.preferred_voice = None
            row.uses_clinical_jargon = None
            row.last_updated_at = None
            self.db.flush()
            logger.info(f"[signature] therapist={therapist_id} profile reset")
