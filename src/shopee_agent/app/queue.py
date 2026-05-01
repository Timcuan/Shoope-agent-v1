from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from shopee_agent.contracts.decisions import ActionRequest
from shopee_agent.persistence.models import OutboxRecord


@dataclass(frozen=True)
class EnqueueResult:
    outbox_id: str
    created: bool


@dataclass(frozen=True)
class ClaimedAction:
    outbox_id: str
    action_type: str
    subject_id: str
    payload: dict


class OutboxQueue:
    def __init__(self, session: Session) -> None:
        self.session = session

    def enqueue(self, action: ActionRequest, priority: int = 100) -> EnqueueResult:
        outbox_id = f"out_{uuid4().hex}"
        record = OutboxRecord(
            outbox_id=outbox_id,
            action_type=action.action_type,
            subject_id=action.subject_id,
            idempotency_key=action.idempotency_key,
            payload_json=json.dumps(action.payload, sort_keys=True),
            priority=priority,
        )
        try:
            with self.session.begin_nested():
                self.session.add(record)
                self.session.flush()
            return EnqueueResult(outbox_id=outbox_id, created=True)
        except IntegrityError:
            existing = self.session.scalar(
                select(OutboxRecord).where(
                    OutboxRecord.idempotency_key == action.idempotency_key,
                )
            )
            if existing is None:
                raise
            return EnqueueResult(outbox_id=existing.outbox_id, created=False)

    def claim_next(self, now: datetime, lease_for: timedelta) -> ClaimedAction | None:
        record = self.session.scalar(
            select(OutboxRecord)
            .where(
                OutboxRecord.status == "pending",
                or_(
                    OutboxRecord.lease_until.is_(None),
                    OutboxRecord.lease_until <= now,
                ),
            )
            .order_by(OutboxRecord.priority.asc(), OutboxRecord.id.asc())
            .limit(1)
        )
        if record is None:
            return None

        record.status = "running"
        record.lease_until = now + lease_for
        record.attempts += 1
        self.session.flush()

        return ClaimedAction(
            outbox_id=record.outbox_id,
            action_type=record.action_type,
            subject_id=record.subject_id,
            payload=json.loads(record.payload_json),
        )

    def mark_done(self, outbox_id: str) -> None:
        record = self.session.scalar(
            select(OutboxRecord).where(OutboxRecord.outbox_id == outbox_id)
        )
        if record is None:
            raise ValueError(f"Unknown outbox_id: {outbox_id}")

        record.status = "done"
        record.lease_until = None
        self.session.flush()
