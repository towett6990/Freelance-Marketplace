"""add dispute fields to order
Revision ID: 9ce45a293354
Revises: 9910f7de7e4b
Create Date: 2026-03-16 00:05:54.343559
"""
from alembic import op
import sqlalchemy as sa

revision = '9ce45a293354'
down_revision = '9910f7de7e4b'
branch_labels = None
depends_on = None

def upgrade():
    pass  # skipped

def downgrade():
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.drop_column('resolved_by')
        batch_op.drop_column('resolved_at')
        batch_op.drop_column('resolution_note')
        batch_op.drop_column('dispute_reason')
