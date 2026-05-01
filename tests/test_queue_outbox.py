from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from shopee_agent.app.queue import OutboxQueue
from shopee_agent.contracts.decisions import ActionRequest
from shopee_agent.persistence.models import OutboxRecord


def _make_action(
    suffix: str,
    *,
    action_type: str = "telegram.send_message",
    subject_id: str | None = None,
) -> ActionRequest:
    return ActionRequest(
        action_type=action_type,
        subject_id=subject_id or f"task-{suffix}",
        idempotency_key=f"{action_type}:{suffix}",
        payload={"text": f"hello {suffix}"},
    )


def _make_pending_record(suffix: str) -> OutboxRecord:
    return OutboxRecord(
        outbox_id=f"outbox-{suffix}",
        action_type="telegram.send_message",
        subject_id=f"pending-{suffix}",
        idempotency_key=f"pending:{suffix}",
        payload_json='{"text":"pending"}',
    )


def test_outbox_dedupes_by_idempotency_key(db_session) -> None:
    queue = OutboxQueue(db_session)
    action = _make_action("task-1")

    first = queue.enqueue(action)
    second = queue.enqueue(action)

    outbox_count = db_session.scalar(select(func.count()).select_from(OutboxRecord))

    assert first.created is True
    assert second.created is False
    assert first.outbox_id == second.outbox_id
    assert outbox_count == 1


def test_claim_next_respects_priority_lease_and_order(db_session) -> None:
    queue = OutboxQueue(db_session)
    now = datetime.now(UTC)
    blocked = queue.enqueue(_make_action("blocked"), priority=1)
    expired = queue.enqueue(_make_action("expired"), priority=10)
    ready = queue.enqueue(_make_action("ready"), priority=10)

    blocked_record = db_session.scalar(
        select(OutboxRecord).where(OutboxRecord.outbox_id == blocked.outbox_id)
    )
    expired_record = db_session.scalar(
        select(OutboxRecord).where(OutboxRecord.outbox_id == expired.outbox_id)
    )
    ready_record = db_session.scalar(
        select(OutboxRecord).where(OutboxRecord.outbox_id == ready.outbox_id)
    )

    assert blocked_record is not None
    assert expired_record is not None
    assert ready_record is not None

    blocked_record.lease_until = now + timedelta(minutes=5)
    expired_record.lease_until = now - timedelta(seconds=1)
    db_session.flush()

    first_claim = queue.claim_next(now=now, lease_for=timedelta(seconds=30))
    second_claim = queue.claim_next(now=now, lease_for=timedelta(seconds=30))
    third_claim = queue.claim_next(now=now, lease_for=timedelta(seconds=30))

    refreshed_expired = db_session.scalar(
        select(OutboxRecord).where(OutboxRecord.outbox_id == expired.outbox_id)
    )

    assert first_claim is not None
    assert first_claim.outbox_id == expired.outbox_id
    assert first_claim.action_type == "telegram.send_message"
    assert first_claim.subject_id == "task-expired"
    assert first_claim.payload == {"text": "hello expired"}
    assert refreshed_expired is not None
    assert refreshed_expired.status == "running"
    assert refreshed_expired.attempts == 1
    assert refreshed_expired.lease_until == now + timedelta(seconds=30)

    assert second_claim is not None
    assert second_claim.outbox_id == ready.outbox_id
    assert third_claim is None


def test_mark_done_updates_status(db_session) -> None:
    queue = OutboxQueue(db_session)
    action = _make_action("done")
    enqueued = queue.enqueue(action)

    queue.mark_done(enqueued.outbox_id)

    record = db_session.scalar(select(OutboxRecord).where(OutboxRecord.outbox_id == enqueued.outbox_id))

    assert record is not None
    assert record.status == "done"


def test_mark_done_raises_for_unknown_outbox_id(db_session) -> None:
    queue = OutboxQueue(db_session)

    with pytest.raises(ValueError, match="Unknown outbox_id: missing-outbox"):
        queue.mark_done("missing-outbox")


def test_enqueue_does_not_commit_unrelated_pending_work(db_session_factory) -> None:
    action = _make_action("no-commit")

    with db_session_factory() as session:
        session.add(_make_pending_record("unrelated-create"))
        result = OutboxQueue(session).enqueue(action)

        with db_session_factory() as observer:
            visible_outbox = observer.scalar(select(func.count()).select_from(OutboxRecord))

        assert result.created is True
        assert visible_outbox == 0

        session.commit()

    with db_session_factory() as observer:
        committed_outbox = observer.scalar(select(func.count()).select_from(OutboxRecord))

    assert committed_outbox == 2


def test_duplicate_enqueue_does_not_rollback_unrelated_pending_work(
    db_session_factory,
) -> None:
    action = _make_action("duplicate")

    with db_session_factory() as session:
        first = OutboxQueue(session).enqueue(action)
        session.commit()

    assert first.created is True

    with db_session_factory() as session:
        session.add(_make_pending_record("unrelated-duplicate"))
        duplicate = OutboxQueue(session).enqueue(action)

        with db_session_factory() as observer:
            visible_outbox = observer.scalar(select(func.count()).select_from(OutboxRecord))

        assert duplicate.created is False
        assert duplicate.outbox_id == first.outbox_id
        assert visible_outbox == 1

        session.commit()

    with db_session_factory() as observer:
        committed_outbox = observer.scalar(select(func.count()).select_from(OutboxRecord))

    assert committed_outbox == 2
