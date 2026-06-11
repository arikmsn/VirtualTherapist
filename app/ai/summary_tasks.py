"""
Task-based orchestration layer for session-summary AI work (Phase 10).

Four distinct summary TASKS — not prompt variations of one flow:

  source_save            — NO AI. Preserve therapist/source text as-is.
  ai_summary_generate    — AI generates a structured draft (existing two-call pipeline).
  source_summary_suggest — AI returns ADVISORY suggestions only; never a rewrite.
  ai_summary_revise      — AI applies ONE instruction to an existing draft; single-shot.

This module is intentionally pure: config + prompt builders + strict parsing.
It has NO database or FastAPI imports, so it is unit-testable in isolation.
DB reads/writes, persistence, and AIGenerationLog rows live in SessionService,
which reads TASK_REGISTRY to decide behavior.

Model selection reuses the existing FlowType + ModelRouter mechanism. Each task
declares its FlowType; ModelRouter maps that to a model tier. source_save has
flow_type=None because it never calls a model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

from loguru import logger
from pydantic import BaseModel

from app.ai.models import FlowType
from app.ai.summary_models import ReviseResult, SourceSaveResult, SuggestResult

if TYPE_CHECKING:
    from app.models.modality import ModalityPack


# ── Task type ─────────────────────────────────────────────────────────────────

class SummaryTaskType(str, Enum):
    SOURCE_SAVE = "source_save"
    AI_SUMMARY_GENERATE = "ai_summary_generate"
    SOURCE_SUMMARY_SUGGEST = "source_summary_suggest"
    AI_SUMMARY_REVISE = "ai_summary_revise"


# ── Task config + registry ────────────────────────────────────────────────────

@dataclass(frozen=True)
class SummaryTaskConfig:
    """
    Declarative per-task configuration. The single place to retune a task's
    model profile, token/timeout budget, and failure policy without touching
    control flow. Handlers READ this; it never executes anything itself.
    """
    task_type: SummaryTaskType
    calls_ai: bool
    flow_type: Optional[FlowType]                 # None when calls_ai is False
    response_model: Optional[type[BaseModel]]
    max_tokens: int
    timeout_s: float
    temperature: float
    persists_summary: bool                        # suggest = False; others True
    safety_notes: str
    fallback_policy: str                          # "scaffold" | "passthrough_original" | "none"


TASK_REGISTRY: dict[SummaryTaskType, SummaryTaskConfig] = {
    SummaryTaskType.SOURCE_SAVE: SummaryTaskConfig(
        task_type=SummaryTaskType.SOURCE_SAVE,
        calls_ai=False,
        flow_type=None,
        response_model=SourceSaveResult,
        max_tokens=0,
        timeout_s=0.0,
        temperature=0.0,
        persists_summary=True,
        safety_notes="No AI call. Preserve source text verbatim; keep provenance.",
        fallback_policy="none",
    ),
    SummaryTaskType.AI_SUMMARY_GENERATE: SummaryTaskConfig(
        task_type=SummaryTaskType.AI_SUMMARY_GENERATE,
        calls_ai=True,
        flow_type=FlowType.SESSION_SUMMARY,
        response_model=None,  # uses existing CLINICAL_JSON_SCHEMA + _parse_clinical_json
        max_tokens=2000,
        timeout_s=90.0,
        temperature=0.7,
        persists_summary=True,
        safety_notes="Structured draft; preserve source; never auto-approve.",
        fallback_policy="scaffold",
    ),
    SummaryTaskType.SOURCE_SUMMARY_SUGGEST: SummaryTaskConfig(
        task_type=SummaryTaskType.SOURCE_SUMMARY_SUGGEST,
        calls_ai=True,
        flow_type=FlowType.SUMMARY_SUGGEST,
        response_model=SuggestResult,
        max_tokens=1200,
        timeout_s=45.0,
        temperature=0.3,
        persists_summary=False,
        safety_notes="Advisory only. Must NOT rewrite. Empty list if source adequate.",
        fallback_policy="scaffold",
    ),
    SummaryTaskType.AI_SUMMARY_REVISE: SummaryTaskConfig(
        task_type=SummaryTaskType.AI_SUMMARY_REVISE,
        calls_ai=True,
        flow_type=FlowType.SUMMARY_REVISE,
        response_model=ReviseResult,
        max_tokens=2000,
        timeout_s=60.0,
        temperature=0.4,
        persists_summary=True,
        safety_notes="Single-shot. Apply one instruction only. Never auto-approve.",
        fallback_policy="passthrough_original",
    ),
}


# ── Strict JSON parser ────────────────────────────────────────────────────────

def _strip_fences(raw: str) -> str:
    """Remove ```json ... ``` fences if present (mirrors _parse_clinical_json)."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        parts = cleaned.split("```")
        cleaned = parts[1] if len(parts) > 1 else cleaned
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    return cleaned.strip()


def parse_strict(raw: str, model: type[BaseModel]) -> Optional[BaseModel]:
    """
    Parse an AI JSON response into `model` with extra='forbid'.
    Returns None on ANY failure (JSON decode OR validation) — never raises.
    The caller applies the task's fallback_policy when this returns None.
    """
    cleaned = _strip_fences(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.warning(f"parse_strict: non-JSON response for {model.__name__}")
        return None
    if not isinstance(data, dict):
        logger.warning(f"parse_strict: top-level not an object for {model.__name__}")
        return None
    try:
        return model.model_validate(data)
    except Exception as exc:  # pydantic ValidationError (extra fields, wrong types, …)
        logger.warning(f"parse_strict: validation failed for {model.__name__}: {exc!r}")
        return None


# ── Prompt builders ───────────────────────────────────────────────────────────

def _modality_addon(modality_pack: Optional["ModalityPack"]) -> str:
    """Reuse the modality framing pattern from summary_pipeline."""
    if modality_pack and modality_pack.prompt_module:
        return "\n\n## Clinical framework for this therapist:\n" + modality_pack.prompt_module.strip()
    return ""


_SUGGEST_SCHEMA = json.dumps(
    {
        "suggestions": [
            {
                "category": "missing|clarify|risk|structure|other",
                "text": "concise advisory note to the therapist",
                "severity": "info|important",
            }
        ],
        "overall_note": "string or null",
    },
    ensure_ascii=False,
    indent=2,
)


def build_suggest_messages(
    source_text: str,
    modality_pack: Optional["ModalityPack"] = None,
    existing_draft: Optional[str] = None,
) -> tuple[str, str]:
    """
    Advisory reviewer. Returns (system_msg, user_msg).
    MUST NOT rewrite — enforced both in the prompt and structurally by SuggestResult.
    """
    system = (
        "You are an advisory clinical reviewer assisting a therapist.\n"
        "Your ONLY job is to surface short, concrete suggestions about the source text.\n"
        "You MUST NOT rewrite, rephrase, summarize, or produce any replacement text.\n"
        "Each suggestion is a note TO the therapist — never a substitute draft.\n"
        "If the source is already adequate, return an empty suggestions list. "
        "Do not invent issues.\n"
        "Return ONLY valid JSON matching the schema — no prose, no markdown fences."
        + _modality_addon(modality_pack)
    )
    parts = ["--- Source text (therapist notes / transcription) ---", source_text, "--- End ---"]
    if existing_draft:
        parts += [
            "\n--- Current AI draft (for gap analysis only; do NOT rewrite it) ---",
            existing_draft,
            "--- End draft ---",
        ]
        parts.append(
            "\nPoint out gaps between the source and the draft, or anything missing/unclear/risky."
        )
    else:
        parts.append("\nPoint out anything missing, unclear, risky, or structurally worth improving.")
    parts.append(f"\nReturn JSON in exactly this shape:\n{_SUGGEST_SCHEMA}")
    return system, "\n".join(parts)


_REVISE_SCHEMA = json.dumps(
    {"revised_summary": "the revised draft text", "change_note": "string or null", "confidence": 0.0},
    ensure_ascii=False,
    indent=2,
)


def build_revise_messages(
    current_summary: str,
    instruction: str,
    modality_pack: Optional["ModalityPack"] = None,
) -> tuple[str, str]:
    """
    Single-shot revision. Returns (system_msg, user_msg).
    Applies exactly one instruction; no iterative round.
    """
    system = (
        "You revise an existing session-summary draft on the therapist's behalf.\n"
        "Apply ONLY the single instruction given. Make no other changes.\n"
        "This is a SINGLE-SHOT revision — there is no follow-up round.\n"
        "Preserve clinical meaning and the therapist's voice. Do not add information "
        "not present in the original unless the instruction explicitly asks for it.\n"
        "Do not add any title, header, date stamp, or patient/therapist name. "
        "Do not approve or finalize.\n"
        "Return ONLY valid JSON matching the schema — no prose, no markdown fences."
        + _modality_addon(modality_pack)
    )
    user = (
        "--- Current draft ---\n"
        f"{current_summary}\n"
        "--- End draft ---\n\n"
        "--- Therapist instruction (apply this and nothing else) ---\n"
        f"{instruction}\n"
        "--- End instruction ---\n\n"
        f"Return JSON in exactly this shape:\n{_REVISE_SCHEMA}"
    )
    return system, user
