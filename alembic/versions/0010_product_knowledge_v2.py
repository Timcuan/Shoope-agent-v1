from alembic import op
import sqlalchemy as sa

revision = "0010_product_knowledge_v2"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("product_knowledge") as batch_op:
        batch_op.add_column(sa.Column("price_min", sa.Float(), nullable=False, server_default="0.0"))
        batch_op.add_column(sa.Column("price_max", sa.Float(), nullable=False, server_default="0.0"))
        batch_op.add_column(sa.Column("variants_json", sa.Text(), nullable=False, server_default="[]"))
        batch_op.add_column(sa.Column("weight_gram", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("condition", sa.String(16), nullable=False, server_default="NEW"))
        batch_op.add_column(sa.Column("description", sa.Text(), nullable=False, server_default=""))
        batch_op.add_column(sa.Column("spec_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("product_knowledge") as batch_op:
        batch_op.drop_column("price_min")
        batch_op.drop_column("price_max")
        batch_op.drop_column("variants_json")
        batch_op.drop_column("weight_gram")
        batch_op.drop_column("condition")
        batch_op.drop_column("description")
        batch_op.drop_column("spec_json")
