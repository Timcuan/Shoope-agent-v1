import pytest
from pydantic import ValidationError

from shopee_agent.contracts.decisions import ActionRequest, Decision, RiskTier
from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType
from shopee_agent.contracts.workflows import WorkflowInstance


def test_decision_explanation_contains_policy_and_context_ids() -> None:
    event = EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id="shop-1",
        source_event_id="evt-1",
        payload={"order_sn": "250501ABC"},
    )
    decision = Decision(
        decision_id="dec-1",
        event_id=event.event_id,
        agent_name="order",
        subject_type="order",
        subject_id="250501ABC",
        risk_tier=RiskTier.LOW,
        confidence=0.95,
        policy_version="policy-v1",
        feature_flag="orders.shadow",
        context_id="ctx-1",
        reason_codes=["order_created"],
        recommended_action="record_order",
        requires_human=False,
    )

    explanation = decision.explain()

    assert "dec-1" in explanation
    assert "ctx-1" in explanation
    assert "policy-v1" in explanation
    assert "orders.shadow" in explanation


def test_contracts_reject_extra_fields() -> None:
    with pytest.raises(ValidationError):
        EventEnvelope(
            source=EventSource.SIMULATOR,
            event_type=EventType.ORDER_CREATED,
            shop_id="shop-1",
            source_event_id="evt-1",
            payload={},
            ignored="nope",
        )

    with pytest.raises(ValidationError):
        ActionRequest(
            action_type="record_order",
            subject_id="250501ABC",
            idempotency_key="idem-1",
            unexpected=True,
        )

    with pytest.raises(ValidationError):
        WorkflowInstance(
            workflow_type="order_review",
            version="v1",
            subject_id="250501ABC",
            current_state="pending",
            event_id="evt-1",
            extra_field="nope",
        )


def test_action_request_payload_default_is_not_shared() -> None:
    first = ActionRequest(
        action_type="record_order",
        subject_id="250501ABC",
        idempotency_key="idem-1",
    )
    second = ActionRequest(
        action_type="record_order",
        subject_id="250501XYZ",
        idempotency_key="idem-2",
    )

    first.payload["status"] = "queued"

    assert second.payload == {}


def test_generated_ids_use_expected_prefixes() -> None:
    event = EventEnvelope(
        source=EventSource.SIMULATOR,
        event_type=EventType.ORDER_CREATED,
        shop_id="shop-1",
        source_event_id="evt-1",
        payload={},
    )
    action = ActionRequest(
        action_type="record_order",
        subject_id="250501ABC",
        idempotency_key="idem-1",
    )
    decision = Decision(
        event_id=event.event_id,
        agent_name="order",
        subject_type="order",
        subject_id="250501ABC",
        risk_tier=RiskTier.LOW,
        confidence=0.95,
        policy_version="policy-v1",
        feature_flag="orders.shadow",
        context_id="ctx-1",
        reason_codes=["order_created"],
        recommended_action="record_order",
        requires_human=False,
    )
    workflow = WorkflowInstance(
        workflow_type="order_review",
        version="v1",
        subject_id="250501ABC",
        current_state="pending",
        event_id=event.event_id,
    )

    assert event.event_id.startswith("evt_")
    assert action.action_id.startswith("act_")
    assert decision.decision_id.startswith("dec_")
    assert workflow.workflow_id.startswith("wf_")


def test_decision_explain_includes_requires_human_and_action_request() -> None:
    action = ActionRequest(
        action_id="act-1",
        action_type="escalate",
        subject_id="250501ABC",
        idempotency_key="idem-1",
    )
    decision = Decision(
        decision_id="dec-1",
        event_id="evt-1",
        agent_name="order",
        subject_type="order",
        subject_id="250501ABC",
        risk_tier=RiskTier.HIGH,
        confidence=0.65,
        policy_version="policy-v1",
        feature_flag="orders.shadow",
        context_id="ctx-1",
        reason_codes=["needs_review"],
        recommended_action="escalate_order",
        requires_human=True,
        action_request=action,
    )

    explanation = decision.explain()

    assert "requires_human=True" in explanation
    assert "action_request=act-1/escalate" in explanation
