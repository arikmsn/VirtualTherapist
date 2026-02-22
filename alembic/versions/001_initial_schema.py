"""Initial schema with all models

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-02-16
"""
from alembic import op
import sqlalchemy as sa


revision = "001"
down_revision = None
branch_labels = None
depends_on = None

# Enum values matching the Python model enums
THERAPEUTIC_APPROACH_VALUES = (
    "CBT", "psychodynamic", "humanistic", "gestalt",
    "DBT", "ACT", "EMDR", "integrative", "other",
)
PATIENT_STATUS_VALUES = ("active", "paused", "completed", "inactive")
SESSION_TYPE_VALUES = (
    "individual", "couples", "family", "group", "intake", "follow_up",
)
MESSAGE_STATUS_VALUES = (
    "draft", "pending_approval", "approved", "sent",
    "delivered", "read", "replied", "rejected",
)
MESSAGE_DIRECTION_VALUES = ("to_patient", "from_patient")


def upgrade() -> None:
    # Create ENUMs
    therapeutic_approach = sa.Enum(
        *THERAPEUTIC_APPROACH_VALUES, name="therapeuticapproach",
    )
    patient_status = sa.Enum(
        *PATIENT_STATUS_VALUES, name="patientstatus",
    )
    session_type = sa.Enum(
        *SESSION_TYPE_VALUES, name="sessiontype",
    )
    message_status = sa.Enum(
        *MESSAGE_STATUS_VALUES, name="messagestatus",
    )
    message_direction = sa.Enum(
        *MESSAGE_DIRECTION_VALUES, name="messagedirection",
    )

    # 1. therapists (no FKs)
    op.create_table(
        "therapists",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "email", sa.String(255),
            unique=True, index=True, nullable=False,
        ),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50)),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("is_verified", sa.Boolean, default=False),
    )

    # 2. therapist_profiles (FK to therapists)
    op.create_table(
        "therapist_profiles",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "therapist_id", sa.Integer,
            sa.ForeignKey("therapists.id"),
            unique=True, nullable=False,
        ),
        sa.Column(
            "therapeutic_approach", therapeutic_approach,
            nullable=False,
        ),
        sa.Column("approach_description", sa.Text),
        sa.Column("tone", sa.String(100)),
        sa.Column("message_length_preference", sa.String(50)),
        sa.Column("common_terminology", sa.JSON),
        sa.Column("summary_template", sa.Text),
        sa.Column("summary_sections", sa.JSON),
        sa.Column("follow_up_frequency", sa.String(50)),
        sa.Column("preferred_exercises", sa.JSON),
        sa.Column("language", sa.String(10), default="he"),
        sa.Column("cultural_considerations", sa.Text),
        sa.Column("example_summaries", sa.JSON),
        sa.Column("example_messages", sa.JSON),
        sa.Column("onboarding_completed", sa.Boolean, default=False),
        sa.Column("onboarding_step", sa.Integer, default=0),
    )

    # 3. session_summaries (no FKs, created before sessions)
    op.create_table(
        "session_summaries",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("topics_discussed", sa.JSON),
        sa.Column("interventions_used", sa.JSON),
        sa.Column("patient_progress", sa.Text),
        sa.Column("homework_assigned", sa.JSON),
        sa.Column("next_session_plan", sa.Text),
        sa.Column("full_summary", sa.Text),
        sa.Column("generated_from", sa.String(50)),
        sa.Column("therapist_edited", sa.Boolean, default=False),
        sa.Column(
            "approved_by_therapist", sa.Boolean, default=False,
        ),
        sa.Column("mood_observed", sa.String(100)),
        sa.Column("risk_assessment", sa.Text),
    )

    # 4. patients (FK to therapists)
    op.create_table(
        "patients",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "therapist_id", sa.Integer,
            sa.ForeignKey("therapists.id"), nullable=False,
            index=True,
        ),
        sa.Column("full_name_encrypted", sa.Text, nullable=False),
        sa.Column("phone_encrypted", sa.Text),
        sa.Column("email_encrypted", sa.Text),
        sa.Column("status", patient_status, default="active"),
        sa.Column("start_date", sa.Date),
        sa.Column("primary_concerns", sa.Text),
        sa.Column("diagnosis", sa.Text),
        sa.Column("treatment_goals", sa.JSON),
        sa.Column("current_exercises", sa.JSON),
        sa.Column("last_contact_date", sa.Date),
        sa.Column("next_session_date", sa.Date),
        sa.Column("pending_followups", sa.JSON),
        sa.Column(
            "completed_exercises_count", sa.Integer, default=0,
        ),
        sa.Column("missed_exercises_count", sa.Integer, default=0),
        sa.Column("allow_ai_contact", sa.Boolean, default=True),
        sa.Column("preferred_contact_time", sa.String(50)),
    )

    # 5. sessions (FK to therapists, patients, session_summaries)
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "therapist_id", sa.Integer,
            sa.ForeignKey("therapists.id"), nullable=False,
            index=True,
        ),
        sa.Column(
            "patient_id", sa.Integer,
            sa.ForeignKey("patients.id"), nullable=False,
            index=True,
        ),
        sa.Column("session_date", sa.Date, nullable=False),
        sa.Column(
            "session_type", session_type,
            default="individual",
        ),
        sa.Column("duration_minutes", sa.Integer),
        sa.Column("session_number", sa.Integer),
        sa.Column("audio_file_path", sa.String(500)),
        sa.Column("has_recording", sa.Boolean, default=False),
        sa.Column(
            "summary_id", sa.Integer,
            sa.ForeignKey("session_summaries.id"),
        ),
    )

    # 6. messages (FK to therapists, patients, sessions)
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "therapist_id", sa.Integer,
            sa.ForeignKey("therapists.id"), nullable=False,
            index=True,
        ),
        sa.Column(
            "patient_id", sa.Integer,
            sa.ForeignKey("patients.id"), nullable=False,
            index=True,
        ),
        sa.Column("direction", message_direction, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("status", message_status, default="draft"),
        sa.Column("requires_approval", sa.Boolean, default=True),
        sa.Column("approved_at", sa.DateTime),
        sa.Column("rejected_at", sa.DateTime),
        sa.Column("rejection_reason", sa.Text),
        sa.Column("sent_at", sa.DateTime),
        sa.Column("delivered_at", sa.DateTime),
        sa.Column("read_at", sa.DateTime),
        sa.Column("message_type", sa.String(50)),
        sa.Column(
            "related_session_id", sa.Integer,
            sa.ForeignKey("sessions.id"),
        ),
        sa.Column("related_exercise", sa.String(255)),
        sa.Column("generated_by_ai", sa.Boolean, default=True),
        sa.Column("ai_prompt_used", sa.Text),
        sa.Column("ai_model", sa.String(100)),
        sa.Column("patient_response", sa.Text),
        sa.Column("response_received_at", sa.DateTime),
    )

    # 7. audit_logs (no FKs)
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Integer, primary_key=True, index=True),
        sa.Column(
            "created_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("user_id", sa.Integer),
        sa.Column("user_type", sa.String(50)),
        sa.Column("user_email", sa.String(255)),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("resource_id", sa.Integer),
        sa.Column(
            "timestamp", sa.DateTime, nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ip_address", sa.String(50)),
        sa.Column("user_agent", sa.String(500)),
        sa.Column("action_details", sa.JSON),
        sa.Column("old_value", sa.Text),
        sa.Column("new_value", sa.Text),
        sa.Column("success", sa.Boolean, default=True),
        sa.Column("error_message", sa.Text),
        sa.Column("gdpr_relevant", sa.Boolean, default=False),
        sa.Column("data_category", sa.String(100)),
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("patients")
    op.drop_table("session_summaries")
    op.drop_table("therapist_profiles")
    op.drop_table("therapists")

    # Drop ENUMs
    sa.Enum(name="messagedirection").drop(op.get_bind())
    sa.Enum(name="messagestatus").drop(op.get_bind())
    sa.Enum(name="sessiontype").drop(op.get_bind())
    sa.Enum(name="patientstatus").drop(op.get_bind())
    sa.Enum(name="therapeuticapproach").drop(op.get_bind())
