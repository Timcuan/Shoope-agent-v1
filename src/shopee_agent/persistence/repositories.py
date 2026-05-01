from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shopee_agent.contracts.events import EventEnvelope
from shopee_agent.persistence.models import EventRecord


@dataclass(frozen=True)
class InsertEventResult:
    event_id: str
    created: bool


class EventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def insert_if_new(self, event: EventEnvelope) -> InsertEventResult:
        record = EventRecord(
            event_id=event.event_id,
            source=event.source.value,
            event_type=event.event_type.value,
            shop_id=event.shop_id,
            source_event_id=event.source_event_id,
            correlation_id=event.correlation_id,
            payload_json=json.dumps(event.payload, sort_keys=True),
        )
        self.session.add(record)
        try:
            self.session.commit()
            return InsertEventResult(event_id=event.event_id, created=True)
        except IntegrityError:
            self.session.rollback()
            existing = self.session.scalar(
                select(EventRecord).where(
                    EventRecord.source == event.source.value,
                    EventRecord.shop_id == event.shop_id,
                    EventRecord.source_event_id == event.source_event_id,
                    EventRecord.event_type == event.event_type.value,
                )
            )
            if existing is None:
                raise
            return InsertEventResult(event_id=existing.event_id, created=False)
