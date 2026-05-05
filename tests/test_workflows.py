from shopee_agent.app.workflows import WorkflowEngine
from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType
from shopee_agent.contracts.workflows import WorkflowStatus


def test_workflow_starts_order_intake() -> None:
    event = EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id="shop-1",
        source_event_id="evt-order-1",
        payload={"order_sn": "250501ABC"},
    )

    workflow = WorkflowEngine().start_for_event(event)

    assert workflow.workflow_type == "order_intake"
    assert workflow.subject_id == "250501ABC"
    assert workflow.current_state == "order_seen"
    assert workflow.status == WorkflowStatus.RUNNING
