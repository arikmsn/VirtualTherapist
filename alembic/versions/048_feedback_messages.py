"""Add feedback_messages table

Revision ID: 048
Revises: 047
Create Date: 2026-06-04
"""

from alembic import op
import sqlalchemy as sa

revision = '048'
down_revision = '047'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'feedback_messages',
        sa.Column('id', sa.Integer(), primary_key=True, index=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('therapist_id', sa.Integer(), sa.ForeignKey('therapists.id', ondelete='SET NULL'), nullable=True, index=True),
        sa.Column('therapist_name', sa.String(255), nullable=False),
        sa.Column('therapist_email', sa.String(255), nullable=False),
        sa.Column('type', sa.String(20), nullable=False),
        sa.Column('subject', sa.String(255), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='new'),
        sa.Column('email_delivery_status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('email_delivery_error', sa.Text(), nullable=True),
    )


def downgrade():
    op.drop_table('feedback_messages')
