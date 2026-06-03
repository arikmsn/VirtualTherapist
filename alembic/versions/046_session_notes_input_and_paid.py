"""Add notes_input to session_summaries and is_paid/paid_at to sessions

Revision ID: 046
Revises: 045
Create Date: 2026-06-03
"""

from alembic import op
import sqlalchemy as sa

revision = '046'
down_revision = '045'
branch_labels = None
depends_on = None


def upgrade():
    try:
        op.add_column('session_summaries', sa.Column('notes_input', sa.Text(), nullable=True))
    except Exception:
        pass
    try:
        op.add_column('sessions', sa.Column('is_paid', sa.Boolean(), nullable=False, server_default='false'))
    except Exception:
        pass
    try:
        op.add_column('sessions', sa.Column('paid_at', sa.DateTime(), nullable=True))
    except Exception:
        pass


def downgrade():
    try:
        op.drop_column('session_summaries', 'notes_input')
    except Exception:
        pass
    try:
        op.drop_column('sessions', 'is_paid')
    except Exception:
        pass
    try:
        op.drop_column('sessions', 'paid_at')
    except Exception:
        pass
