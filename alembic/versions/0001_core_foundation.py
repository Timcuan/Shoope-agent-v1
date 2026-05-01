from alembic import op
import sqlalchemy as sa

revision = "0001_core_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("shop_id", sa.String(length=64), nullable=False),
        sa.Column("source_event_id", sa.String(length=128), nullable=False),
        sa.Column("correlation_id", sa.String(length=128), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint(
            "source",
            "shop_id",
            "source_event_id",
            "event_type",
            name="uq_events_source_event",
        ),
    )
    op.create_index("ix_events_correlation_id", "events", ["correlation_id"])
    op.create_index("ix_events_event_id", "events", ["event_id"], unique=True)
    op.create_index("ix_events_shop_id", "events", ["shop_id"])
    op.create_index("ix_events_event_type", "events", ["event_type"])
    op.create_index("ix_events_source", "events", ["source"])
    op.create_index("ix_events_source_event_id", "events", ["source_event_id"])
    op.create_index("ix_events_status", "events", ["status"])

    op.create_table(
        "outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("outbox_id", sa.String(length=64), nullable=False),
        sa.Column("action_type", sa.String(length=128), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("idempotency_key", sa.String(length=256), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_outbox_action_type", "outbox", ["action_type"])
    op.create_index("ix_outbox_idempotency_key", "outbox", ["idempotency_key"], unique=True)
    op.create_index("ix_outbox_lease_until", "outbox", ["lease_until"])
    op.create_index("ix_outbox_outbox_id", "outbox", ["outbox_id"], unique=True)
    op.create_index("ix_outbox_priority", "outbox", ["priority"])
    op.create_index("ix_outbox_status", "outbox", ["status"])
    op.create_index("ix_outbox_subject_id", "outbox", ["subject_id"])

    op.create_table(
        "workflow_instances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("workflow_id", sa.String(length=64), nullable=False),
        sa.Column("workflow_type", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("subject_id", sa.String(length=128), nullable=False),
        sa.Column("current_state", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("event_id", sa.String(length=64), nullable=False),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_workflow_instances_event_id", "workflow_instances", ["event_id"])
    op.create_index("ix_workflow_instances_status", "workflow_instances", ["status"])
    op.create_index("ix_workflow_instances_subject_id", "workflow_instances", ["subject_id"])
    op.create_index("ix_workflow_instances_workflow_id", "workflow_instances", ["workflow_id"], unique=True)
    op.create_index("ix_workflow_instances_workflow_type", "workflow_instances", ["workflow_type"])


def downgrade() -> None:
    op.drop_table("workflow_instances")
    op.drop_table("outbox")
    op.drop_table("events")
