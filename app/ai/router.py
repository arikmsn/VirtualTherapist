"""
ModelRouter — resolves a (flow_type, context) pair into (model_id, route_reason).

All model IDs come from settings env vars — never hardcoded here.
This means updating the active model is a config change, not a code change.

Routing tiers
-------------
fast     → AI_FAST_MODEL     (haiku-class; extraction, classification, cheap tasks)
standard → AI_STANDARD_MODEL (sonnet-class; everyday summaries, prep, chat)
deep     → AI_DEEP_MODEL     (opus-class; cross-session synthesis, treatment plans)

Escalation rules (evaluated in priority order)
-----------------------------------------------
1. model_override — caller explicitly requests a specific model ID.
2. deep_mode      — therapist clicked "מצב עמוק"; escalates standard → deep.
3. long_history   — session_count > 15 on summary/prep flows escalates to deep.
4. low_confidence — if a previous call returned confidence < 0.65, escalate.
5. Default tier   — from ROUTING_TABLE below.
"""

from __future__ import annotations

from app.ai.models import FlowType
from app.core.config import settings


class ModelRouter:
    """
    Stateless resolver: given a flow type and optional context hints,
    returns the model ID to use and a string explaining why.
    """

    # Default tier per flow — change here if a flow needs a different default
    ROUTING_TABLE: dict[FlowType, str] = {
        FlowType.EXTRACTION:          "fast",
        FlowType.COMPLETENESS_CHECK:  "fast",
        FlowType.CHAT:                "standard",
        FlowType.SESSION_SUMMARY:     "standard",
        FlowType.SESSION_PREP:        "standard",
        FlowType.PRE_SESSION_PREP:    "standard",
        FlowType.PATIENT_INSIGHT:     "standard",
        FlowType.MESSAGE_DRAFT:       "standard",
        FlowType.DEEP_SUMMARY:        "deep",
        FlowType.TREATMENT_PLAN:      "deep",
        FlowType.TWIN_PROFILE:        "deep",
    }

    # Escalation thresholds
    LONG_HISTORY_THRESHOLD: int = 15
    LOW_CONFIDENCE_THRESHOLD: float = 0.65

    # Flows that can be escalated due to long history
    _HISTORY_ESCALATABLE: frozenset[FlowType] = frozenset({
        FlowType.SESSION_SUMMARY,
        FlowType.SESSION_PREP,
        FlowType.PATIENT_INSIGHT,
    })

    def resolve(
        self,
        flow_type: FlowType,
        *,
        deep_mode: bool = False,
        session_count: int = 0,
        prior_confidence: float | None = None,
        model_override: str | None = None,
    ) -> tuple[str, str]:
        """
        Resolve the model ID and route reason for a given flow.

        Args:
            flow_type:        The generation flow being requested.
            deep_mode:        True if the therapist explicitly requested deep mode.
            session_count:    Number of sessions for this patient (for history escalation).
            prior_confidence: Confidence score from a prior fast/standard call, if any.
            model_override:   Bypass routing and use this model ID directly.

        Returns:
            (model_id, route_reason) — both strings.
        """
        if model_override:
            return model_override, "override"

        tier = self.ROUTING_TABLE.get(flow_type, "standard")
        reasons: list[str] = [f"flow:{flow_type.value}"]

        # Escalation rule 1: deep_mode flag
        if deep_mode and tier == "standard":
            tier = "deep"
            reasons.append("deep_mode")

        # Escalation rule 2: long history
        elif (
            session_count > self.LONG_HISTORY_THRESHOLD
            and flow_type in self._HISTORY_ESCALATABLE
            and tier == "standard"
        ):
            tier = "deep"
            reasons.append(f"long_history:{session_count}")

        # Escalation rule 3: low confidence from a prior call
        elif (
            prior_confidence is not None
            and prior_confidence < self.LOW_CONFIDENCE_THRESHOLD
            and tier == "standard"
        ):
            tier = "deep"
            reasons.append(f"low_confidence:{prior_confidence:.2f}")

        model_id = self._tier_to_model(tier)
        reasons.append(f"tier:{tier}")

        return model_id, ",".join(reasons)

    def _tier_to_model(self, tier: str) -> str:
        return {
            "fast":     settings.AI_FAST_MODEL,
            "standard": settings.AI_STANDARD_MODEL,
            "deep":     settings.AI_DEEP_MODEL,
        }[tier]
