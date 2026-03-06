"""Data classes and enums for the AI provider layer."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class FlowType(str, Enum):
    """
    Every distinct AI generation flow in the system.

    The ModelRouter maps each flow to a model tier (fast / standard / deep).
    Add new flows here as new features are built; update router.ROUTING_TABLE
    alongside.
    """
    # Lightweight extraction / classification tasks
    EXTRACTION = "extraction"
    COMPLETENESS_CHECK = "completeness_check"

    # Standard-tier flows (everyday therapist interactions)
    CHAT = "chat"
    SESSION_SUMMARY = "session_summary"
    SESSION_PREP = "session_prep"
    PRE_SESSION_PREP = "pre_session_prep"   # Phase 4: structured two-call prep pipeline
    PATIENT_INSIGHT = "patient_insight"
    MESSAGE_DRAFT = "message_draft"

    # Deep-tier flows (cross-session synthesis, longitudinal reasoning)
    DEEP_SUMMARY = "deep_summary"
    TREATMENT_PLAN = "treatment_plan"
    TWIN_PROFILE = "twin_profile"
    FORMAL_RECORD = "formal_record"  # Phase 5: Israeli formal clinical documentation


@dataclass
class GenerationResult:
    """
    Returned by every AIProvider.generate() call.

    Callers use this to:
    - Extract the generated text (content)
    - Write a row to ai_generation_log (model_used, tokens, generation_ms, etc.)
    - Store ai_draft_text on the new SessionSummary before persisting
    """
    content: str
    model_used: str
    provider: str           # "anthropic" | "openai"
    flow_type: FlowType
    prompt_tokens: int = 0
    completion_tokens: int = 0
    generation_ms: int = 0
    route_reason: str = ""  # propagated from ModelRouter.resolve()
