"""
CompletenessChecker — standalone Phase 2 service.

Evaluates an AI-generated session summary against the active modality pack's
required / recommended field definitions.  Uses FlowType.COMPLETENESS_CHECK
(routed to AI_FAST_MODEL) so the check is cheap and fast.

Design principles:
- Never raises: returns CompletenessResult.error() on any failure
- Stateless: create a new instance per request (no mutable state)
- Stores _last_result so session_service can write a generation log row
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Optional, List, TYPE_CHECKING

from loguru import logger

from app.ai.models import FlowType
from app.ai.router import ModelRouter

if TYPE_CHECKING:
    from app.ai.provider import AIProvider
    from app.models.modality import ModalityPack


@dataclass
class CompletenessResult:
    """Structured output from a completeness evaluation."""

    score: float  # 0.0–1.0 (or -1.0 on checker error)
    required_missing: List[str] = field(default_factory=list)
    recommended_missing: List[str] = field(default_factory=list)
    modality_notes: str = ""

    @classmethod
    def full(cls) -> "CompletenessResult":
        """Perfect score — all fields present."""
        return cls(score=1.0)

    @classmethod
    def error(cls) -> "CompletenessResult":
        """Fallback when checker fails — signals unknown quality, not a failure."""
        return cls(score=-1.0, modality_notes="checker_error")

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "required_missing": self.required_missing,
            "recommended_missing": self.recommended_missing,
            "modality_notes": self.modality_notes,
        }


_PROMPT_TEMPLATE = """\
You are a clinical documentation quality evaluator.

Evaluate the session summary below against the modality pack requirements.

## MODALITY PACK: {modality_name}

### REQUIRED fields (must be present and substantive):
{required_fields}

### RECOMMENDED fields (should be present):
{recommended_fields}

## SESSION SUMMARY:
{summary_text}

## INSTRUCTIONS:
Return ONLY a valid JSON object with these exact keys:
- "score": float 0.0–1.0 (1.0 = all required AND recommended fields fully covered)
- "required_missing": list of required field names that are absent or empty
- "recommended_missing": list of recommended field names that are absent or empty
- "modality_notes": one sentence (max 150 chars) describing the most critical gap, or "" if complete

Example valid outputs:
{{"score": 0.85, "required_missing": [], "recommended_missing": ["homework_assigned"], "modality_notes": "homework section is empty"}}
{{"score": 1.0, "required_missing": [], "recommended_missing": [], "modality_notes": ""}}
{{"score": 0.5, "required_missing": ["risk_assessment"], "recommended_missing": [], "modality_notes": "risk_assessment is required for CBT but is missing"}}

Output only the JSON object, no markdown fences, no explanation.
"""


class CompletenessChecker:
    """
    Scores a session summary against the active modality pack.

    Usage:
        checker = CompletenessChecker(provider)
        result = await checker.check(summary_text, modality_pack)
        # checker._last_result contains the GenerationResult for logging
    """

    def __init__(self, provider: "AIProvider") -> None:
        self.provider = provider
        self._router = ModelRouter()
        self._last_result = None  # GenerationResult from last check call

    async def check(
        self,
        summary_text: str,
        modality_pack: Optional["ModalityPack"] = None,
    ) -> CompletenessResult:
        """
        Evaluate summary completeness.

        Returns CompletenessResult.full() when:
        - No modality pack is available
        - The pack has no required or recommended fields defined

        Returns CompletenessResult.error() on any exception (never raises).
        Stores the raw GenerationResult in self._last_result for telemetry logging.
        """
        self._last_result = None

        if not modality_pack:
            return CompletenessResult.full()

        required = modality_pack.required_summary_fields or []
        recommended = modality_pack.recommended_summary_fields or []

        if not required and not recommended:
            return CompletenessResult.full()

        prompt = _PROMPT_TEMPLATE.format(
            modality_name=modality_pack.label or modality_pack.name,
            required_fields="\n".join(f"- {f}" for f in required) or "(none defined)",
            recommended_fields="\n".join(f"- {f}" for f in recommended) or "(none defined)",
            # Cap input to keep fast model within context; 4000 chars is well within limits
            summary_text=summary_text[:4000],
        )

        try:
            model_id, route_reason = self._router.resolve(FlowType.COMPLETENESS_CHECK)
            result = await self.provider.generate(
                messages=[{"role": "user", "content": prompt}],
                model=model_id,
                flow_type=FlowType.COMPLETENESS_CHECK,
                route_reason=route_reason,
            )
            self._last_result = result

            raw = result.content.strip()
            # Strip markdown code fences if the model adds them
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]

            data = json.loads(raw)
            return CompletenessResult(
                score=float(data.get("score", 0.0)),
                required_missing=list(data.get("required_missing", [])),
                recommended_missing=list(data.get("recommended_missing", [])),
                modality_notes=str(data.get("modality_notes", "")),
            )

        except Exception as exc:
            logger.warning(f"CompletenessChecker.check failed (non-blocking): {exc!r}")
            return CompletenessResult.error()
