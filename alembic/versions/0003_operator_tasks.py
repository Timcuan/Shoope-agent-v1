from alembic import op
import sqlalchemy as sa

revision = "0003_operator_tasks"
down_revision = "0002_shop_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "operator_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.String(length=64), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("shop_id", sa.String(length=64), nullable=False, server_default="demo_shop"),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("task_id"),
    )
    op.create_index("ix_operator_tasks_task_id", "operator_tasks", ["task_id"])
    op.create_index("ix_operator_tasks_status", "operator_tasks", ["status"])
    op.create_index("ix_operator_tasks_severity", "operator_tasks", ["severity"])


def downgrade() -> None:
    op.drop_table("operator_tasks")
