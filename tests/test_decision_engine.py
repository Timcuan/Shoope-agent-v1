from shopee_agent.contracts.decisions import Decision, RiskTier
from shopee_agent.contracts.events import EventEnvelope, EventSource, EventType


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
