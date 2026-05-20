"""Fix exercises.session_summary_id FK: add ON DELETE SET NULL

Revision ID: 045
Revises: 044
Create Date: 2026-05-21

Root cause: exercises_session_summary_id_fkey was created without an ON DELETE
action, so PostgreSQL defaulted to RESTRICT. Any attempt to delete a
session_summaries row that is still referenced by exercises raised a
ForeignKeyViolation. The column is nullable, so SET NULL is the correct
behavior — exercises (patient homework) survive, their summary attribution
link is cleared.

Production error this fixes:
    psycopg2.errors.ForeignKeyViolation: update or delete on table
    "session_summaries" violates foreign key constraint
    "exercises_session_summary_id_fkey" on table "exercises"
    Path: /api/v1/sessions/206
"""

from alembic import op

revision = '045'
down_revision = '044'
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL: drop and recreate the FK with ON DELETE SET NULL.
    # SQLite does not support named FK constraints and does not enforce
    # referential integrity by default, so the try/except silently skips it.
    try:
        op.drop_constraint(
            'exercises_session_summary_id_fkey',
            'exercises',
            type_='foreignkey',
        )
        op.create_foreign_key(
            'exercises_session_summary_id_fkey',
            'exercises',
            'session_summaries',
            ['session_summary_id'],
            ['id'],
            ondelete='SET NULL',
        )
    except Exception:
        pass


def downgrade():
    try:
        op.drop_constraint(
            'exercises_session_summary_id_fkey',
            'exercises',
            type_='foreignkey',
        )
        op.create_foreign_key(
            'exercises_session_summary_id_fkey',
            'exercises',
            'session_summaries',
            ['session_summary_id'],
            ['id'],
        )
    except Exception:
        pass
