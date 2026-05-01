import pytest
from sqlalchemy import func, select

from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType
from shopee_agent.persistence.models import EventRecord, OutboxRecord
from shopee_agent.persistence.repositories import EventRepository
from shopee_agent.persistence.session import session_scope


def _make_event(source_event_id: str = "same-source-event") -> EventEnvelope:
    return EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id="shop-1",
        source_event_id=source_event_id,
        payload={"order_sn": "250501ABC"},
    )


def _make_outbox(subject_id: str) -> OutboxRecord:
    return OutboxRecord(
        outbox_id=f"outbox-{subject_id}",
        action_type="record_order",
        subject_id=subject_id,
        idempotency_key=f"idem-{subject_id}",
        payload_json='{"status":"queued"}',
    )


def test_event_repository_dedupes_source_event(db_session) -> None:
    repo = EventRepository(db_session)
    event = _make_event()

    first = repo.insert_if_new(event)
    second = repo.insert_if_new(event)

    assert first.created is True
    assert second.created is False
    assert first.event_id == second.event_id


def test_session_scope_commits_and_rolls_back(db_session_factory) -> None:
    with session_scope(db_session_factory) as session:
        session.add(_make_outbox("committed"))

    with db_session_factory() as session:
        committed_count = session.scalar(select(func.count()).select_from(OutboxRecord))

    assert committed_count == 1

    with pytest.raises(RuntimeError):
        with session_scope(db_session_factory) as session:
            session.add(_make_outbox("rolled-back"))
            raise RuntimeError("boom")

    with db_session_factory() as session:
        outbox_ids = session.scalars(select(OutboxRecord.outbox_id)).all()

    assert outbox_ids == ["outbox-committed"]


def test_event_repository_does_not_commit_unrelated_pending_work(db_session_factory) -> None:
    event = _make_event("new-source-event")

    with db_session_factory() as session:
        session.add(_make_outbox("pending-create"))
        result = EventRepository(session).insert_if_new(event)

        with db_session_factory() as observer:
            visible_events = observer.scalar(select(func.count()).select_from(EventRecord))
            visible_outbox = observer.scalar(select(func.count()).select_from(OutboxRecord))

        assert result.created is True
        assert visible_events == 0
        assert visible_outbox == 0

        session.commit()

    with db_session_factory() as observer:
        committed_events = observer.scalar(select(func.count()).select_from(EventRecord))
        committed_outbox = observer.scalar(select(func.count()).select_from(OutboxRecord))

    assert committed_events == 1
    assert committed_outbox == 1


def test_event_repository_duplicate_does_not_rollback_unrelated_pending_work(
    db_session_factory,
) -> None:
    event = _make_event("duplicate-source-event")

    with db_session_factory() as session:
        first = EventRepository(session).insert_if_new(event)
        session.commit()

    assert first.created is True

    with db_session_factory() as session:
        session.add(_make_outbox("pending-duplicate"))
        duplicate = EventRepository(session).insert_if_new(event)

        with db_session_factory() as observer:
            visible_outbox = observer.scalar(select(func.count()).select_from(OutboxRecord))

        assert duplicate.created is False
        assert duplicate.event_id == event.event_id
        assert visible_outbox == 0

        session.commit()

    with db_session_factory() as observer:
        committed_events = observer.scalar(select(func.count()).select_from(EventRecord))
        committed_outbox = observer.scalar(select(func.count()).select_from(OutboxRecord))

    assert committed_events == 1
    assert committed_outbox == 1
