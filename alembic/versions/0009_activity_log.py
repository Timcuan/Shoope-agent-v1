"""activity log

Revision ID: 0009
Revises: 0008
Create Date: 2026-05-04 22:28:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'activity_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('shop_id', sa.String(64), nullable=False),
        sa.Column('activity_type', sa.String(64), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('severity', sa.String(16), nullable=False, server_default='info'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now())
    )
    op.create_index(op.f('ix_activity_logs_activity_type'), 'activity_logs', ['activity_type'], unique=False)
    op.create_index(op.f('ix_activity_logs_severity'), 'activity_logs', ['severity'], unique=False)
    op.create_index(op.f('ix_activity_logs_shop_id'), 'activity_logs', ['shop_id'], unique=False)


def downgrade():
    op.drop_table('activity_logs')
