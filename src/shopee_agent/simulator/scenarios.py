from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType


def order_created(shop_id: str, order_sn: str) -> EventEnvelope:
    return EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id=shop_id,
        source_event_id=f"sim-order-created-{order_sn}",
        payload={"order_sn": order_sn},
    )
