from alembic import op
import sqlalchemy as sa

revision = "0006_knowledge_chat"
down_revision = "0005_domain_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_knowledge",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("category", sa.String(256), nullable=True),
        sa.Column("selling_points", sa.Text(), nullable=False, server_default=""),
        sa.Column("forbidden_claims", sa.Text(), nullable=False, server_default=""),
        sa.Column("faq_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("aliases_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("freshness_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("shop_id", "item_id", name="uq_pk_shop_item"),
    )
    op.create_index("ix_product_knowledge_item_id", "product_knowledge", ["item_id"])
    op.create_index("ix_product_knowledge_shop_id", "product_knowledge", ["shop_id"])

    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("order_sn", sa.String(64), nullable=True),
        sa.Column("buyer_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column("last_intent", sa.String(64), nullable=True),
        sa.Column("risk_tier", sa.String(16), nullable=False, server_default="low"),
        sa.Column("messages_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_chat_sessions_session_id", "chat_sessions", ["session_id"])
    op.create_index("ix_chat_sessions_shop_id", "chat_sessions", ["shop_id"])
    op.create_index("ix_chat_sessions_order_sn", "chat_sessions", ["order_sn"])
    op.create_index("ix_chat_sessions_buyer_id", "chat_sessions", ["buyer_id"])
    op.create_index("ix_chat_sessions_status", "chat_sessions", ["status"])
    op.create_index("ix_chat_sessions_risk_tier", "chat_sessions", ["risk_tier"])


def downgrade() -> None:
    op.drop_table("chat_sessions")
    op.drop_table("product_knowledge")
