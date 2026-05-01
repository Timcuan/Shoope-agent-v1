from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class EventSource(StrEnum):
    SHOPEE_WEBHOOK = "shopee_webhook"
    SHOPEE_POLL = "shopee_poll"
    TELEGRAM = "telegram"
    SIMULATOR = "simulator"


class EventType(StrEnum):
    ORDER_CREATED = "order.created"
    ORDER_UPDATED = "order.updated"
    SHIPPING_DOCUMENT_REQUESTED = "shipping_document.requested"
    CHAT_MESSAGE_RECEIVED = "chat.message_received"
    SYSTEM_COMMAND = "system.command"


class EventEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(default_factory=lambda: f"evt_{uuid4().hex}")
    source: EventSource
    event_type: EventType
    shop_id: str
    source_event_id: str
    payload: dict
    correlation_id: str = Field(default_factory=lambda: f"corr_{uuid4().hex}")
