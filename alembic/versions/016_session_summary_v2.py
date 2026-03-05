"""Session Summary 2.0 — clinical_json, therapist_edit_distance, CBT prompt update.

Revision ID: 016
Revises: 015
Create Date: 2026-03-06
"""

import sqlalchemy as sa
from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None

# Full CBT prompt_module as specified in the Phase 3 spec.
_CBT_PROMPT_MODULE = """\
You are assisting a CBT therapist. All outputs must follow the cognitive model.

SESSION STRUCTURE to follow: agenda setting → homework review → new material → new homework assignment.

REQUIRED elements in every CBT summary:
- Homework review: was previous homework completed? What were the barriers?
- Automatic thoughts: quote or paraphrase specific thoughts that surfaced
- Cognitive distortions: NAME them explicitly (catastrophizing, mind-reading, all-or-nothing thinking, personalization, fortune-telling, emotional reasoning, should statements, labeling, magnification/minimization)
- Core beliefs or schemas when they surface
- Interventions used — name them precisely: Socratic questioning, thought record, behavioral experiment, activity scheduling, exposure, graded task assignment
- Client's response to interventions
- Between-session task: specific and measurable
- Next session focus

RECOMMENDED elements: severity/mood tracking, scales (PHQ-9, GAD-7 or equivalent) when applicable, between-session observations.

MISSING ITEMS: If any required element is absent from what the therapist provided, flag it explicitly at the end: "⚠️ חסר בסיכום זה: [element]"

IMPORTANT: Do NOT be rigid or robotic. CBT structure guides completeness — it does not force every session into a form. Use clinical judgment. A session that focused entirely on a crisis does not need forced homework review framing.

Use CBT terminology naturally: "מחשבה אוטומטית", "אמונת ליבה", "ניסוי התנהגותי", "עיוות קוגניטיבי", "מודל ABC", "סכמה". If the therapist mixes Hebrew-English terms, mirror that.\
"""


def upgrade():
    # 1. New columns on session_summaries
    op.add_column(
        "session_summaries",
        sa.Column("clinical_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "session_summaries",
        sa.Column("therapist_edit_distance", sa.Integer(), nullable=True),
    )

    # 2. Update CBT modality pack prompt_module to the full Phase 3 version
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE modality_packs SET prompt_module = :pm, version = version + 1 "
            "WHERE name = 'cbt'"
        ),
        {"pm": _CBT_PROMPT_MODULE},
    )


def downgrade():
    op.drop_column("session_summaries", "therapist_edit_distance")
    op.drop_column("session_summaries", "clinical_json")
    # Note: we do not roll back the CBT prompt_module text — that would require
    # storing the old value. Downgrade is best-effort for schema changes only.
