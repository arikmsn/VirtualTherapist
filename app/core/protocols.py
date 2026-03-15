"""Protocol Library — system-defined and custom therapeutic protocols.

System protocols are defined in code (no DB table required).
Custom protocols are stored per-therapist as JSON in
therapist_profiles.custom_protocols.

Protocol ID conventions:
  System:  e.g. "cbt_depression", "ot_sensory_integration"
  Custom:  e.g. "custom_<uuid4-short>"
"""

from __future__ import annotations

from typing import List, Optional
from pydantic import BaseModel


class Protocol(BaseModel):
    """Represents a therapeutic protocol — system-defined or custom."""

    id: str
    name: str
    approach_id: str        # matches a key in THERAPY_MODES (therapistConstants.ts)
    target_problem: str     # free-text clinical indication
    description: str        # shown in UI + injected into prompts
    typical_sessions: Optional[int] = None
    core_techniques: List[str] = []
    is_system: bool = True  # False for therapist-defined custom protocols


# ---------------------------------------------------------------------------
# System protocol library
# ---------------------------------------------------------------------------

SYSTEM_PROTOCOLS: List[Protocol] = [

    # ── CBT ─────────────────────────────────────────────────────────────────

    Protocol(
        id="cbt_depression",
        name="CBT לדיכאון",
        approach_id="cbt",
        target_problem="דיכאון קליני (MDD), דיסתימיה",
        description=(
            "פרוטוקול CBT לדיכאון: זיהוי מחשבות אוטומטיות שליליות, מודל ABC, "
            "הפעלה התנהגותית ותכנון פעילות."
        ),
        typical_sessions=16,
        core_techniques=[
            "מודל ABC", "יומן מחשבות", "הפעלה התנהגותית",
            "תכנון פעילויות", "ניסויים התנהגותיים",
        ],
    ),

    Protocol(
        id="cbt_anxiety",
        name="CBT לחרדה",
        approach_id="cbt",
        target_problem="הפרעת חרדה כללית (GAD), חרדה חברתית",
        description=(
            "פרוטוקול CBT לחרדה: חשיפה הדרגתית, ניהול חרדה, "
            "אתגור מחשבות קטסטרופיות ורכישת כלי ויסות."
        ),
        typical_sessions=12,
        core_techniques=[
            "היררכיית חשיפה", "רלקסציה", "נשימה סרעפתית",
            "אתגור קוגניטיבי", "חשיפה בדמיון",
        ],
    ),

    Protocol(
        id="cbt_panic",
        name="CBT להפרעת פאניקה",
        approach_id="cbt",
        target_problem="הפרעת פאניקה עם/בלי אגורפוביה",
        description=(
            "פרוטוקול CBT ממוקד לפאניקה: פסיכוחינוך על מנגנון הפאניקה, "
            "חשיפה interoceptive וחשיפה in-vivo להימנעויות."
        ),
        typical_sessions=10,
        core_techniques=[
            "פסיכוחינוך", "חשיפה interoceptive", "נשימה מבוקרת", "הפחתת בטחה",
        ],
    ),

    Protocol(
        id="cbt_ocd",
        name="CBT ל-OCD — ERP",
        approach_id="cbt",
        target_problem="הפרעה אובססיבית-קומפולסיבית (OCD)",
        description=(
            "פרוטוקול ERP (Exposure and Response Prevention): "
            "חשיפה מבוקרת לטריגרים ומניעת טכסים."
        ),
        typical_sessions=20,
        core_techniques=[
            "ERP", "היררכיית חשיפה", "מניעת תגובה", "פסיכוחינוך", "חוזה טיפולי",
        ],
    ),

    # ── ACT ─────────────────────────────────────────────────────────────────

    Protocol(
        id="act_general",
        name="ACT — קבלה ומחויבות",
        approach_id="act",
        target_problem="דיכאון, חרדה, כאב כרוני, בעיות זהות",
        description=(
            "פרוטוקול ACT: גמישות פסיכולוגית כמטרה; defusion, acceptance, "
            "values clarification ו-committed action בעברית."
        ),
        typical_sessions=12,
        core_techniques=[
            "Defusion קוגניטיבי", "קבלה", "הווה מודע",
            "עצמי כהקשר", "ערכים", "פעולה מחויבת",
        ],
    ),

    # ── DBT ─────────────────────────────────────────────────────────────────

    Protocol(
        id="dbt_skills",
        name="DBT — מיומנויות",
        approach_id="dbt",
        target_problem="הפרעת אישיות גבולית, רגשיות גבוהה, פגיעה עצמית",
        description=(
            "הוראת ארבעת מודולי DBT: mindfulness, סבילות למצוקה, "
            "ויסות רגשי ויעילות בינאישית."
        ),
        typical_sessions=24,
        core_techniques=[
            "Mindfulness", "TIPP", "DEAR MAN", "FAST", "PLEASE", "הפחתת פגיעות",
        ],
    ),

    # ── Occupational Therapy ─────────────────────────────────────────────────

    Protocol(
        id="ot_functional_adl",
        name="ריפוי בעיסוק — גישה תפקודית (ADL)",
        approach_id="ot_functional",
        target_problem="קשיים בפעילויות יומיומיות: לבוש, רחצה, בישול, כתיבה, עבודה",
        description=(
            "מיפוי תפקוד בעיסוקים יומיומיים (לבוש, רחצה, כתיבה, עבודה, לימודים) "
            "והגדרת מטרות שיפור השתתפות בהתאם לסביבה ולתפקידים של המטופל."
        ),
        typical_sessions=20,
        core_techniques=[
            "הערכת AMPS", "אימון תפקוד", "הסתגלות סביבתית",
            "אמצעי עזר", "אסטרטגיות פיצוי",
        ],
    ),

    Protocol(
        id="ot_sensory_integration",
        name="ריפוי בעיסוק — אינטגרציה חושית",
        approach_id="ot_sensory",
        target_problem="קשיי ויסות חושי, קשב ואוטיזם",
        description=(
            "עבודה על ויסות חושי ומוטורי, התאמת סביבה ופעילויות לילדים ומבוגרים "
            "עם קשיי קשב, ויסות, אוטיזם או רגישות יתר/חסר לגירויים "
            "(מגע, רעש, תנועה)."
        ),
        typical_sessions=24,
        core_techniques=[
            "פרופיל חושי", "חדר סנסורי", "דיאטה חושית",
            "ויסות עצמי", "פעילויות הבנייה",
        ],
    ),

    # ── Psychodynamic ────────────────────────────────────────────────────────

    Protocol(
        id="psychodynamic_brief",
        name="פסיכודינמי קצר מועד (STDP)",
        approach_id="psychodynamic",
        target_problem="דפוסי יחסים, עיבוד רגשי, קונפליקטים לא מודעים",
        description=(
            "פרוטוקול פסיכודינמי קצר: זיהוי קונפליקטים מרכזיים, "
            "עבודה על העברה והעברה נגדית."
        ),
        typical_sessions=16,
        core_techniques=[
            "חופשיות אסוציאציות", "פרשנות", "עבודה עם העברה", "עיבוד הגנות",
        ],
    ),

    # ── EMDR ─────────────────────────────────────────────────────────────────

    Protocol(
        id="emdr_trauma",
        name="EMDR לטראומה",
        approach_id="emdr",
        target_problem="PTSD, טראומה מורכבת, אירועים מכוננים",
        description=(
            "פרוטוקול EMDR: 8 שלבים — היסטוריה, הכנה, הערכה, עיבוד, "
            "התקנה, בדיקת גוף, סגירה, הערכה מחדש."
        ),
        typical_sessions=12,
        core_techniques=[
            "BLS (גירוי דו-צדדי)", "פרוטוקול 8 שלבים", "SUDS", "VOC", "NC/PC",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_system_protocols() -> List[Protocol]:
    """Return all system-defined protocols (read-only copy)."""
    return list(SYSTEM_PROTOCOLS)


def get_protocol_by_id(protocol_id: str) -> Optional[Protocol]:
    """Look up a system protocol by its ID. Returns None if not found."""
    for p in SYSTEM_PROTOCOLS:
        if p.id == protocol_id:
            return p
    return None


def get_protocols_for_approach(approach_id: str) -> List[Protocol]:
    """Return system protocols that belong to a given therapy approach."""
    return [p for p in SYSTEM_PROTOCOLS if p.approach_id == approach_id]


def merge_protocols(
    system_protocols: List[Protocol],
    custom_protocols: List[dict],
) -> List[Protocol]:
    """Merge system and custom protocol dicts into a single Protocol list.

    Custom protocol dicts (stored as JSON in the DB) are converted to
    Protocol instances with ``is_system=False``.  Malformed entries are
    silently skipped.
    """
    result = list(system_protocols)
    for cp in custom_protocols or []:
        try:
            # Require the four fields that make a protocol meaningful
            if not (cp.get("id") and cp.get("name") and
                    cp.get("target_problem") and cp.get("description")):
                continue
            result.append(Protocol(
                id=cp["id"],
                name=cp["name"],
                approach_id=cp.get("approach_id", "other"),
                target_problem=cp["target_problem"],
                description=cp["description"],
                typical_sessions=cp.get("typical_sessions"),
                core_techniques=cp.get("core_techniques", []),
                is_system=False,
            ))
        except Exception:
            pass  # skip malformed entries
    return result
