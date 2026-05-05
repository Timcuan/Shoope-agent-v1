from alembic import op
import sqlalchemy as sa

revision = "0004_exports"
down_revision = "0003_operator_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exports",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("export_id", sa.String(length=64), nullable=False),
        sa.Column("report_type", sa.String(length=64), nullable=False),
        sa.Column("shop_id", sa.String(length=64), nullable=False),
        sa.Column("period_start", sa.DateTime(), nullable=False),
        sa.Column("period_end", sa.DateTime(), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("creator", sa.String(length=64), nullable=False, server_default="system"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("export_id"),
    )
    op.create_index("ix_exports_export_id", "exports", ["export_id"])
    op.create_index("ix_exports_report_type", "exports", ["report_type"])
    op.create_index("ix_exports_shop_id", "exports", ["shop_id"])


def downgrade() -> None:
    op.drop_table("exports")
