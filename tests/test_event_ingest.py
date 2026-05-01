from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType
from shopee_agent.persistence.repositories import EventRepository


def test_event_repository_dedupes_source_event(db_session) -> None:
    repo = EventRepository(db_session)
    event = EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id="shop-1",
        source_event_id="same-source-event",
        payload={"order_sn": "250501ABC"},
    )

    first = repo.insert_if_new(event)
    second = repo.insert_if_new(event)

    assert first.created is True
    assert second.created is False
    assert first.event_id == second.event_id
