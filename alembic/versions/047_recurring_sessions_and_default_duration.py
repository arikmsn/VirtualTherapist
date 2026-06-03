"""Add recurring session fields and default_session_duration

Revision ID: 047
Revises: 046
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa

revision = '047'
down_revision = '046'
branch_labels = None
depends_on = None


def upgrade():
    # Recurring session support on sessions table
    try:
        op.add_column('sessions', sa.Column('recurrence_rule', sa.String(20), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('sessions', sa.Column('recurrence_ends_at', sa.Date(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('sessions', sa.Column('recurrence_parent_id', sa.Integer(), nullable=True))
    except Exception:
        pass
    try:
        op.create_foreign_key(
            'sessions_recurrence_parent_id_fkey',
            'sessions', 'sessions',
            ['recurrence_parent_id'], ['id'],
            ondelete='SET NULL',
        )
    except Exception:
        pass

    # Default session duration on therapist_profiles
    try:
        op.add_column('therapist_profiles', sa.Column(
            'default_session_duration', sa.Integer(), nullable=False, server_default='50'
        ))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_constraint('sessions_recurrence_parent_id_fkey', 'sessions', type_='foreignkey')
    except Exception:
        pass
    try:
        op.drop_column('sessions', 'recurrence_parent_id')
    except Exception:
        pass
    try:
        op.drop_column('sessions', 'recurrence_ends_at')
    except Exception:
        pass
    try:
        op.drop_column('sessions', 'recurrence_rule')
    except Exception:
        pass
    try:
        op.drop_column('therapist_profiles', 'default_session_duration')
    except Exception:
        pass
