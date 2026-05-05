from shopee_agent.contracts.events import EventEnvelope, EventType
from shopee_agent.contracts.workflows import WorkflowInstance


class WorkflowEngine:
    def start_for_event(self, event: EventEnvelope) -> WorkflowInstance:
        if event.event_type == EventType.ORDER_CREATED:
            return WorkflowInstance(
                workflow_type="order_intake",
                version="v1",
                subject_id=str(event.payload["order_sn"]),
                current_state="order_seen",
                event_id=event.event_id,
                data={"shop_id": event.shop_id},
            )
        return WorkflowInstance(
            workflow_type="unsupported_event",
            version="v1",
            subject_id=event.source_event_id,
            current_state="needs_operator_review",
            event_id=event.event_id,
            data={"event_type": event.event_type.value},
        )
