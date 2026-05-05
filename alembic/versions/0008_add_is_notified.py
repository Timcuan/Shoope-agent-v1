"""add is_notified

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-04 22:18:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0008'
down_revision = '0007_disputes'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('operator_tasks', sa.Column('is_notified', sa.Boolean(), nullable=False, server_default=sa.text('0')))
    op.create_index(op.f('ix_operator_tasks_is_notified'), 'operator_tasks', ['is_notified'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_operator_tasks_is_notified'), table_name='operator_tasks')
    op.drop_column('operator_tasks', 'is_notified')
