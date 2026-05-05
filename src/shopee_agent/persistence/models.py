from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint, func, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from shopee_agent.persistence.base import Base


class EventRecord(Base):
    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint(
            "source",
            "shop_id",
            "source_event_id",
            "event_type",
            name="uq_events_source_event",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    event_type: Mapped[str] = mapped_column(String(128), index=True)
    shop_id: Mapped[str] = mapped_column(String(64), index=True)
    source_event_id: Mapped[str] = mapped_column(String(128), index=True)
    correlation_id: Mapped[str] = mapped_column(String(128), index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="stored", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OutboxRecord(Base):
    __tablename__ = "outbox"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    outbox_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    action_type: Mapped[str] = mapped_column(String(64), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    payload_json: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class WorkflowRecord(Base):
    __tablename__ = "workflow_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    workflow_type: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    current_state: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(32), index=True)
    event_id: Mapped[str] = mapped_column(String(64), index=True)
    data_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ShopTokenRecord(Base):
    __tablename__ = "shop_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    access_token: Mapped[str] = mapped_column(String(256), nullable=False)
    refresh_token: Mapped[str] = mapped_column(String(256), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class OperatorTaskRecord(Base):
    __tablename__ = "operator_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    shop_id: Mapped[str] = mapped_column(String(64), index=True, default="demo_shop")
    severity: Mapped[str] = mapped_column(String(16), index=True)
    title: Mapped[str] = mapped_column(String(256))
    summary: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    is_notified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
    )


class ExportRecord(Base):
    __tablename__ = "exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    export_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    report_type: Mapped[str] = mapped_column(String(64), index=True)
    shop_id: Mapped[str] = mapped_column(String(64), index=True)
    period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    creator: Mapped[str] = mapped_column(String(64), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class OrderRecord(Base):
    __tablename__ = "orders"
    __table_args__ = (UniqueConstraint("shop_id", "order_sn", name="uq_orders_shop_order"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_sn: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    shop_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    buyer_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    total_amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    pay_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ship_by_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class LogisticsRecord(Base):
    __tablename__ = "logistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_sn: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    shop_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    tracking_no: Mapped[str | None] = mapped_column(String(128), nullable=True)
    logistics_channel: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ship_status: Mapped[str] = mapped_column(String(64), default="pending", index=True)
    label_status: Mapped[str] = mapped_column(String(64), default="not_generated", index=True)
    file_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class FinanceLedgerRecord(Base):
    __tablename__ = "finance_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_sn: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    shop_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    escrow_amount: Mapped[float] = mapped_column(default=0.0)
    commission_fee: Mapped[float] = mapped_column(default=0.0)
    service_fee: Mapped[float] = mapped_column(default=0.0)
    shipping_fee: Mapped[float] = mapped_column(default=0.0)
    estimated_income: Mapped[float] = mapped_column(default=0.0)
    final_income: Mapped[float] = mapped_column(default=0.0)
    settlement_status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    data_json: Mapped[str] = mapped_column(Text, default="{}")
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class InventoryRecord(Base):
    __tablename__ = "inventory"
    __table_args__ = (UniqueConstraint("shop_id", "item_id", "model_id", name="uq_inventory_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    item_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    model_id: Mapped[str] = mapped_column(String(64), default="")
    sku: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0)
    reserved_stock: Mapped[int] = mapped_column(Integer, default=0)
    price: Mapped[float] = mapped_column(default=0.0)
    synced_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ProductKnowledgeRecord(Base):
    __tablename__ = "product_knowledge"
    __table_args__ = (UniqueConstraint("shop_id", "item_id", name="uq_pk_shop_item"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    shop_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    category: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # Pricing & variants
    price_min: Mapped[float] = mapped_column(Float, default=0.0)
    price_max: Mapped[float] = mapped_column(Float, default=0.0)
    variants_json: Mapped[str] = mapped_column(Text, default="[]")
    # Physical
    weight_gram: Mapped[int] = mapped_column(Integer, default=0)
    condition: Mapped[str] = mapped_column(String(16), default="NEW")
    # Content
    description: Mapped[str] = mapped_column(Text, default="")
    spec_json: Mapped[str] = mapped_column(Text, default="{}")
    # CS Knowledge
    selling_points: Mapped[str] = mapped_column(Text, default="")
    forbidden_claims: Mapped[str] = mapped_column(Text, default="")
    faq_json: Mapped[str] = mapped_column(Text, default="[]")
    aliases_json: Mapped[str] = mapped_column(Text, default="[]")
    freshness_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ChatSessionRecord(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    shop_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    order_sn: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    buyer_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="open", index=True)
    last_intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_tier: Mapped[str] = mapped_column(String(16), default="low", index=True)
    messages_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )


class ReturnDisputeRecord(Base):
    __tablename__ = "returns_disputes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    return_sn: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    order_sn: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    shop_id: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    buyer_id: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)
    reason: Mapped[str] = mapped_column(String(128), nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    amount: Mapped[float] = mapped_column(default=0.0)
    text_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[str] = mapped_column(Text, default="[]")
    agent_recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_score: Mapped[float] = mapped_column(default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

class ReviewRecord(Base):
    __tablename__ = "product_reviews"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    review_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    order_sn: Mapped[str] = mapped_column(String(64), index=True)
    shop_id: Mapped[str] = mapped_column(String(64), index=True)
    rating_star: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str] = mapped_column(Text, default="")
    reply_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending") # pending, replied
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

class ActivityLogRecord(Base):
    __tablename__ = "activity_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[str] = mapped_column(String(64), index=True)
    activity_type: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="info", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class BoostSlotRecord(Base):
    __tablename__ = "boost_slots"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    shop_id: Mapped[str] = mapped_column(String(64), index=True)
    item_id: Mapped[str] = mapped_column(String(64), index=True)
    boosted_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime)

class IncidentRecord(Base):
    __tablename__ = "incidents"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    component: Mapped[str] = mapped_column(String(64), index=True) # "Logistics", "Print", "API"
    error_message: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(16), default="error")
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True) # "pending", "resolved"
    retry_payload: Mapped[str | None] = mapped_column(Text) # JSON for retry logic
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class DecisionRecord(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    decision_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    event_id: Mapped[str] = mapped_column(String(64), index=True)
    agent_name: Mapped[str] = mapped_column(String(64), index=True)
    subject_type: Mapped[str] = mapped_column(String(64))
    subject_id: Mapped[str] = mapped_column(String(128), index=True)
    risk_tier: Mapped[str] = mapped_column(String(16))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    policy_version: Mapped[str] = mapped_column(String(64))
    recommended_action: Mapped[str] = mapped_column(String(128))
    requires_human: Mapped[bool] = mapped_column(default=False)
    reason_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
