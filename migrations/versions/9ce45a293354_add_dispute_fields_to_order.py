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
    # Dispute fields were added manually via ALTER TABLE
    # This migration just records the foreign key for resolved_by
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.add_column(sa.Column('dispute_reason', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('resolution_note', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('resolved_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('resolved_by', sa.Integer(), nullable=True))

def downgrade():
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.drop_column('resolved_by')
        batch_op.drop_column('resolved_at')
        batch_op.drop_column('resolution_note')
        batch_op.drop_column('dispute_reason')
