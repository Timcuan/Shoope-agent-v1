from alembic import op
import sqlalchemy as sa

revision = "0005_domain_tables"
down_revision = "0004_exports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_sn", sa.String(64), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("buyer_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(64), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False, server_default="0"),
        sa.Column("pay_time", sa.DateTime(), nullable=True),
        sa.Column("ship_by_date", sa.DateTime(), nullable=True),
        sa.Column("data_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("shop_id", "order_sn", name="uq_orders_shop_order"),
    )
    op.create_index("ix_orders_shop_id", "orders", ["shop_id"])
    op.create_index("ix_orders_status", "orders", ["status"])
    op.create_index("ix_orders_ship_by_date", "orders", ["ship_by_date"])

    op.create_table(
        "logistics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_sn", sa.String(64), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("tracking_no", sa.String(128), nullable=True),
        sa.Column("logistics_channel", sa.String(128), nullable=True),
        sa.Column("ship_status", sa.String(64), nullable=False, server_default="pending"),
        sa.Column("label_status", sa.String(64), nullable=False, server_default="not_generated"),
        sa.Column("file_path", sa.String(512), nullable=True),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("order_sn"),
    )
    op.create_index("ix_logistics_order_sn", "logistics", ["order_sn"])
    op.create_index("ix_logistics_shop_id", "logistics", ["shop_id"])
    op.create_index("ix_logistics_label_status", "logistics", ["label_status"])

    op.create_table(
        "finance_ledger",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("order_sn", sa.String(64), nullable=False),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("escrow_amount", sa.Float(), server_default="0"),
        sa.Column("commission_fee", sa.Float(), server_default="0"),
        sa.Column("service_fee", sa.Float(), server_default="0"),
        sa.Column("shipping_fee", sa.Float(), server_default="0"),
        sa.Column("estimated_income", sa.Float(), server_default="0"),
        sa.Column("final_income", sa.Float(), server_default="0"),
        sa.Column("settlement_status", sa.String(32), server_default="pending"),
        sa.Column("data_json", sa.Text(), server_default="{}"),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("order_sn"),
    )
    op.create_index("ix_finance_ledger_order_sn", "finance_ledger", ["order_sn"])
    op.create_index("ix_finance_ledger_shop_id", "finance_ledger", ["shop_id"])

    op.create_table(
        "inventory",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_id", sa.String(64), nullable=False),
        sa.Column("item_id", sa.String(64), nullable=False),
        sa.Column("model_id", sa.String(64), nullable=False, server_default=""),
        sa.Column("sku", sa.String(128), nullable=True),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("stock", sa.Integer(), server_default="0"),
        sa.Column("reserved_stock", sa.Integer(), server_default="0"),
        sa.Column("price", sa.Float(), server_default="0"),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now()),
        sa.UniqueConstraint("shop_id", "item_id", "model_id", name="uq_inventory_item"),
    )
    op.create_index("ix_inventory_shop_id", "inventory", ["shop_id"])
    op.create_index("ix_inventory_item_id", "inventory", ["item_id"])


def downgrade() -> None:
    op.drop_table("inventory")
    op.drop_table("finance_ledger")
    op.drop_table("logistics")
    op.drop_table("orders")
