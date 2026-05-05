from alembic import op
import sqlalchemy as sa

revision = "0007_disputes"
down_revision = "0006_knowledge_chat"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "returns_disputes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("return_sn", sa.String(64), nullable=False),
        sa.Column("order_sn", sa.String(64), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("buyer_id", sa.String(64), nullable=True),
        sa.Column("reason", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("text_reason", sa.Text(), nullable=True),
        sa.Column("evidence_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("agent_recommendation", sa.Text(), nullable=True),
        sa.Column("risk_score", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("return_sn"),
    )
    op.create_index("ix_returns_disputes_return_sn", "returns_disputes", ["return_sn"])
    op.create_index("ix_returns_disputes_order_sn", "returns_disputes", ["order_sn"])
    op.create_index("ix_returns_disputes_shop_id", "returns_disputes", ["shop_id"])
    op.create_index("ix_returns_disputes_buyer_id", "returns_disputes", ["buyer_id"])
    op.create_index("ix_returns_disputes_status", "returns_disputes", ["status"])


def downgrade() -> None:
    op.drop_table("returns_disputes")
