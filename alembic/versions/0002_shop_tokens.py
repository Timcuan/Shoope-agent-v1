from alembic import op
import sqlalchemy as sa

revision = "0002_shop_tokens"
down_revision = "0001_core_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shop_tokens",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("shop_id", sa.String(length=64), nullable=False),
        sa.Column("access_token", sa.String(length=256), nullable=False),
        sa.Column("refresh_token", sa.String(length=256), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("shop_id"),
    )
    op.create_index("ix_shop_tokens_shop_id", "shop_tokens", ["shop_id"])


def downgrade() -> None:
    op.drop_table("shop_tokens")
