"""AI layer Phase 1 — schema additions for modality packs, signature profiles,
generation log, and reference vault; extend session_summaries and
therapist_profiles with AI metadata columns.

What this migration adds
------------------------
New tables:
  modality_packs              — versioned modality-pack definitions (CBT, DBT, etc.)
  therapist_signature_profiles— learned style profile built from approved summaries
  ai_generation_log           — append-only telemetry row per AI generation call
  therapist_reference_vault   — therapist-owned reference/notebook items

Extended columns on existing tables:
  session_summaries:
    ai_draft_text        TEXT    — original AI output before any therapist edits
                                   (CRITICAL for signature learning; mandatory per spec)
    ai_model             VARCHAR — model that generated this summary
    ai_prompt_version    VARCHAR — prompt version tag at generation time
    ai_confidence        FLOAT   — confidence score returned by generation
    modality_pack_id     INTEGER — which modality pack was active

  therapist_profiles:
    modality_pack_id     INTEGER — therapist's currently selected modality pack

Seed data:
  Two starter modality packs are inserted: 'generic_integrative' and 'cbt'.
  See prompt_module strings for clinical framing text from the spec.

Design notes:
  - All new tables use the same integer PK + created_at/updated_at pattern
    as existing BaseModel tables.
  - ai_generation_log has no updated_at (append-only; never updated in place).
  - modality_pack_id FKs use SET NULL on delete so deleting a pack does not
    cascade to clinical records.
  - Backward compatibility: all new columns are nullable / have server defaults.
  - PostgreSQL only: the enum-to-varchar and partial-index patterns from
    migration 009 are not needed here; all new columns use VARCHAR / FLOAT / TEXT.

Revision ID: 014
Revises: 013
Create Date: 2026-03-06
"""

from datetime import datetime
from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


# ─────────────────────────────────────────────────────────────────────────────
# Seed data for starter modality packs
# ─────────────────────────────────────────────────────────────────────────────

_MODALITY_PACK_SEED = [
    {
        "name": "generic_integrative",
        "label": "Generic / Integrative",
        "label_he": "אינטגרטיבי / כללי",
        "description": (
            "Default pack for therapists with an integrative or unspecified approach. "
            "Outputs are structured around common clinical elements without imposing "
            "a single theoretical lens."
        ),
        "prompt_module": (
            "You are assisting an integrative therapist. Organize outputs around "
            "universal clinical dimensions: presenting concerns, session focus, "
            "observable change, therapeutic relationship, between-session tasks, "
            "and next steps. Avoid imposing a single theoretical framework. "
            "Use clear, professional Hebrew. Invite the therapist to specify their "
            "approach more precisely over time."
        ),
        "required_summary_fields": (
            '["presenting_concerns", "session_focus", "interventions_used", '
            '"patient_response", "next_session_plan"]'
        ),
        "recommended_summary_fields": (
            '["mood_observed", "risk_assessment", "homework_assigned"]'
        ),
        "preferred_terminology": "{}",
        "evidence_tags": '["integrative", "generic"]',
        "output_style_hints": "Balanced structure. Neither too directive nor too open.",
        "version": 1,
        "is_active": True,
        "created_at": datetime(2026, 3, 6),
        "updated_at": datetime(2026, 3, 6),
    },
    {
        "name": "cbt",
        "label": "Cognitive Behavioral Therapy (CBT)",
        "label_he": "טיפול קוגניטיבי-התנהגותי (CBT)",
        "description": (
            "First-class CBT pack. Structures all outputs around the cognitive model: "
            "automatic thoughts, core beliefs, behavioral patterns, and between-session "
            "skill practice. Completeness checks flag missing CBT-specific elements."
        ),
        "prompt_module": (
            "You are assisting a CBT therapist. All outputs should be structured around "
            "the cognitive model. Required elements: presenting problem focus, session "
            "agenda, homework review, automatic thoughts and core beliefs when present, "
            "emotional/behavioral patterns, interventions used (name them: Socratic "
            "questioning, thought records, behavioral experiments, etc.), between-session "
            "tasks, next session focus. Use CBT terminology naturally: \"automatic "
            "thoughts\", \"core beliefs\", \"cognitive distortions\", \"schemas\", "
            "\"behavioral activation\". Flag missing elements explicitly. Cognitive "
            "distortions should be named when identified (catastrophizing, mind-reading, "
            "etc.). Do NOT make CBT rigid or robotic — the goal is guided completeness, "
            "not forcing every note into a form."
        ),
        "required_summary_fields": (
            '["presenting_problem", "session_agenda", "homework_review", '
            '"automatic_thoughts", "interventions_used", "between_session_tasks", '
            '"next_session_focus"]'
        ),
        "recommended_summary_fields": (
            '["core_beliefs", "cognitive_distortions", "behavioral_patterns", '
            '"mood_observed", "risk_assessment"]'
        ),
        "preferred_terminology": (
            '{"automatic_thoughts": "מחשבות אוטומטיות", '
            '"core_beliefs": "אמונות ליבה", '
            '"cognitive_distortions": "עיוותי חשיבה", '
            '"schemas": "סכמות", '
            '"behavioral_activation": "הפעלה התנהגותית"}'
        ),
        "evidence_tags": '["CBT", "Beck", "cognitive_model", "structured"]',
        "output_style_hints": (
            "Structured with clear CBT section headers. Use bullet points for "
            "automatic thoughts and distortions. Narrative for progress and next steps."
        ),
        "version": 1,
        "is_active": True,
        "created_at": datetime(2026, 3, 6),
        "updated_at": datetime(2026, 3, 6),
    },
]


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. modality_packs ──────────────────────────────────────────────────────
    op.create_table(
        "modality_packs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), unique=True, nullable=False),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("label_he", sa.String(200)),
        sa.Column("description", sa.Text),
        sa.Column("prompt_module", sa.Text),
        sa.Column("required_summary_fields", sa.JSON),
        sa.Column("recommended_summary_fields", sa.JSON),
        sa.Column("preferred_terminology", sa.JSON),
        sa.Column("evidence_tags", sa.JSON),
        sa.Column("output_style_hints", sa.Text),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # ── 2. therapist_signature_profiles ───────────────────────────────────────
    op.create_table(
        "therapist_signature_profiles",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("therapist_id", sa.Integer,
                  sa.ForeignKey("therapists.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        # Style dimensions — 0.0 (one extreme) → 1.0 (other extreme)
        sa.Column("concise_vs_detailed", sa.Float),         # 0=concise, 1=detailed
        sa.Column("directive_vs_exploratory", sa.Float),    # 0=directive, 1=exploratory
        sa.Column("emotional_vs_cognitive_emphasis", sa.Float),  # 0=emotional, 1=cognitive
        sa.Column("homework_task_orientation", sa.Float),   # 0=low, 1=high
        sa.Column("structure_preference", sa.String(50)),   # "bullets" | "narrative" | "mixed"
        sa.Column("preferred_intervention_naming", sa.JSON),
        sa.Column("documentation_rigor", sa.Float),         # 0=minimal, 1=thorough
        sa.Column("risk_followup_inclusion", sa.Float),     # 0=rarely, 1=always
        sa.Column("measurable_goals_tendency", sa.Float),
        sa.Column("preferred_tone", sa.String(100)),
        sa.Column("conceptual_evidence_orientation", sa.Float),
        sa.Column("hebrew_english_mix", sa.Float),          # 0=Hebrew only, 1=heavy mix
        sa.Column("preferred_terminology", sa.JSON),
        # Metadata
        sa.Column("confidence_scores", sa.JSON),            # {dimension: 0–1}
        sa.Column("evidence_snippets", sa.JSON),            # non-PHI phrases
        sa.Column("approved_summary_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # ── 3. ai_generation_log — append-only telemetry ──────────────────────────
    op.create_table(
        "ai_generation_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("therapist_id", sa.Integer,
                  sa.ForeignKey("therapists.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("flow_type", sa.String(100), nullable=False, index=True),
        sa.Column("session_summary_id", sa.Integer,
                  sa.ForeignKey("session_summaries.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("session_id", sa.Integer,
                  sa.ForeignKey("sessions.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("modality_pack_id", sa.Integer,
                  sa.ForeignKey("modality_packs.id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("model_used", sa.String(200), nullable=False),
        sa.Column("route_reason", sa.String(500)),
        sa.Column("prompt_version", sa.String(50)),
        sa.Column("ai_confidence", sa.Float),
        sa.Column("completeness_score", sa.Float),
        sa.Column("therapist_edit_distance", sa.Integer),   # filled post-approval
        sa.Column("prompt_tokens", sa.Integer),
        sa.Column("completion_tokens", sa.Integer),
        sa.Column("generation_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime, nullable=False),
        # No updated_at — this table is append-only
    )

    # ── 4. therapist_reference_vault ──────────────────────────────────────────
    op.create_table(
        "therapist_reference_vault",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("therapist_id", sa.Integer,
                  sa.ForeignKey("therapists.id", ondelete="CASCADE"),
                  nullable=False, index=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tags", sa.JSON),
        sa.Column("modality_pack_ids", sa.JSON),
        sa.Column("source_type", sa.String(50), nullable=False,
                  server_default="'therapist'"),  # "therapist" | "system"
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )

    # ── 5. Extend session_summaries ────────────────────────────────────────────
    op.add_column("session_summaries",
        sa.Column("ai_draft_text", sa.Text, nullable=True))
    op.add_column("session_summaries",
        sa.Column("ai_model", sa.String(200), nullable=True))
    op.add_column("session_summaries",
        sa.Column("ai_prompt_version", sa.String(50), nullable=True))
    op.add_column("session_summaries",
        sa.Column("ai_confidence", sa.Float, nullable=True))
    op.add_column("session_summaries",
        sa.Column("modality_pack_id", sa.Integer,
                  sa.ForeignKey("modality_packs.id", ondelete="SET NULL"),
                  nullable=True))

    # ── 6. Extend therapist_profiles ──────────────────────────────────────────
    op.add_column("therapist_profiles",
        sa.Column("modality_pack_id", sa.Integer,
                  sa.ForeignKey("modality_packs.id", ondelete="SET NULL"),
                  nullable=True))

    # ── 7. Seed starter modality packs ────────────────────────────────────────
    modality_table = sa.table(
        "modality_packs",
        sa.column("name", sa.String),
        sa.column("label", sa.String),
        sa.column("label_he", sa.String),
        sa.column("description", sa.Text),
        sa.column("prompt_module", sa.Text),
        sa.column("required_summary_fields", sa.JSON),
        sa.column("recommended_summary_fields", sa.JSON),
        sa.column("preferred_terminology", sa.JSON),
        sa.column("evidence_tags", sa.JSON),
        sa.column("output_style_hints", sa.Text),
        sa.column("version", sa.Integer),
        sa.column("is_active", sa.Boolean),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    op.bulk_insert(modality_table, _MODALITY_PACK_SEED)


def downgrade() -> None:
    # Remove seed data before dropping the table
    bind = op.get_bind()
    bind.execute(sa.text("DELETE FROM modality_packs WHERE name IN ('generic_integrative', 'cbt')"))

    op.drop_column("therapist_profiles", "modality_pack_id")
    op.drop_column("session_summaries", "modality_pack_id")
    op.drop_column("session_summaries", "ai_confidence")
    op.drop_column("session_summaries", "ai_prompt_version")
    op.drop_column("session_summaries", "ai_model")
    op.drop_column("session_summaries", "ai_draft_text")

    op.drop_table("therapist_reference_vault")
    op.drop_table("ai_generation_log")
    op.drop_table("therapist_signature_profiles")
    op.drop_table("modality_packs")
