"""Shared error constants and response schemas for AI-layer endpoints."""

from dataclasses import dataclass, field
from typing import Optional
from pydantic import BaseModel


# ── Hebrew error messages ──────────────────────────────────────────────────────
# Centralised strings so every route returns the same copy and tests can assert
# against constants rather than hard-coded literals.

AI_ERRORS_HE: dict[str, str] = {
    "no_approved_summaries": (
        "אין סיכומים מאושרים עבור מטופל זה. "
        "אשר לפחות סיכום אחד לפני יצירת תוכן AI."
    ),
    "client_not_found": "המטופל לא נמצא או שאינו שייך לחשבון שלך.",
    "summary_not_found": "הסיכום לא נמצא.",
    "plan_not_found": "תוכנית הטיפול לא נמצאה.",
    "deep_summary_not_found": "הסיכום העמוק לא נמצא.",
    "ai_generation_failed": (
        "שגיאה בייצור תוכן AI. אנא נסה שוב מאוחר יותר."
    ),
    "signature_not_active": (
        "חתימת AI טרם הופעלה. נדרשים לפחות 5 סיכומים מאושרים."
    ),
    "no_active_plan": "אין תוכנית טיפול פעילה עבור מטופל זה.",
    "edit_already_started": "עריכת הסיכום כבר החלה.",
    "summary_already_approved": "לא ניתן לערוך סיכום שכבר אושר.",
}


class HebrewError(BaseModel):
    """Standard error response for AI-layer 4xx/5xx responses."""

    code: str                       # machine-readable key from AI_ERRORS_HE
    message: str                    # Hebrew user-facing message
    detail: Optional[str] = None    # optional technical detail (logged, not shown in UI)


# ── AIMeta ────────────────────────────────────────────────────────────────────

@dataclass
class AIMeta:
    """
    Metadata attached to every AI-generated response.

    Included as an optional block in route responses so the frontend can show
    generation quality indicators and the backend can build a feedback loop.
    """

    model_used: str
    tokens_used: int
    generation_time_ms: int
    completeness_score: Optional[float] = None   # 0.0–1.0 from CompletenessChecker
    confidence: Optional[int] = None             # 0–100 from AI call
    signature_applied: bool = False              # whether Signature Engine was active
    ai_layer_version: str = "9.0"               # bumped with each phase that changes prompts
