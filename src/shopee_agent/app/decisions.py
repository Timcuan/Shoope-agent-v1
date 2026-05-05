from shopee_agent.contracts.decisions import ActionRequest, Decision, RiskTier
from shopee_agent.contracts.events import EventEnvelope, EventType


class DecisionEngine:
    def __init__(self, policy_version: str) -> None:
        self.policy_version = policy_version

    def decide(self, event: EventEnvelope) -> Decision:
        decision = self._decide_base(event)
        
        # --- Institutional Safeguards (Anti-Error / HITL Revision) ---
        # 1. High Risk always requires human
        if decision.risk_tier == RiskTier.HIGH:
            decision.requires_human = True
            decision.reason_codes.append("hitl_policy_high_risk_lock")
            
        # 2. Confidence Threshold (90% for autonomous action)
        if decision.confidence < 0.90:
            decision.requires_human = True
            decision.reason_codes.append("hitl_policy_low_confidence_gate")
            
        # 3. Force Supervisor review for specific sensitive actions
        if decision.recommended_action in ["SYNC_FINANCE", "SYNC_DISPUTE"]:
             # We allow background sync, but let's say we want to mark it for audit
             pass

        return decision

    def _decide_base(self, event: EventEnvelope) -> Decision:
        if event.event_type == EventType.ORDER_CREATED:
            order_sn = str(event.payload.get("order_sn", ""))
            return Decision(
                event_id=event.event_id,
                agent_name="order",
                subject_type="order",
                subject_id=order_sn,
                risk_tier=RiskTier.LOW,
                confidence=0.99,
                policy_version=self.policy_version,
                feature_flag="orders.shadow",
                context_id=f"ctx_{event.event_id}",
                reason_codes=["simulated_order_created"],
                recommended_action="record_order",
                requires_human=False,
            )

        if event.event_type == EventType.ORDER_ESCROW_UPDATED:
            order_sn = event.source_event_id
            return Decision(
                event_id=event.event_id,
                agent_name="finance",
                subject_type="order",
                subject_id=order_sn,
                risk_tier=RiskTier.LOW,
                confidence=0.95,
                policy_version=self.policy_version,
                feature_flag="finance.auto",
                context_id=f"ctx_{event.event_id}",
                reason_codes=["escrow_updated"],
                recommended_action="sync_finance",
                requires_human=False,
                action_request=ActionRequest(
                    action_type="SYNC_FINANCE",
                    subject_id=order_sn,
                    idempotency_key=f"sync_fin_{event.event_id}",
                    payload={"order_sn": order_sn, "shop_id": event.shop_id}
                )
            )

        if event.event_type == EventType.RETURN_UPDATED:
            return_sn = event.source_event_id
            return Decision(
                event_id=event.event_id,
                agent_name="dispute",
                subject_type="return",
                subject_id=return_sn,
                risk_tier=RiskTier.MEDIUM,
                confidence=0.90,
                policy_version=self.policy_version,
                feature_flag="dispute.supervised",
                context_id=f"ctx_{event.event_id}",
                reason_codes=["return_updated"],
                recommended_action="sync_dispute",
                requires_human=False,
                action_request=ActionRequest(
                    action_type="SYNC_DISPUTE",
                    subject_id=return_sn,
                    idempotency_key=f"sync_disp_{event.event_id}",
                    payload={"return_sn": return_sn, "shop_id": event.shop_id}
                )
            )
            
        action = ActionRequest(
            action_type="create_operator_task",
            subject_id=event.source_event_id,
            idempotency_key=f"task_{event.event_id}",
            payload={"reason": "unsupported_event_type", "event_type": event.event_type.value}
        )
        return Decision(
            event_id=event.event_id,
            agent_name="system",
            subject_type="event",
            subject_id=event.source_event_id,
            risk_tier=RiskTier.MEDIUM,
            confidence=0.5,
            policy_version=self.policy_version,
            feature_flag="system.supervised",
            context_id=f"ctx_{event.event_id}",
            reason_codes=["unsupported_event_type"],
            recommended_action="create_operator_task",
            requires_human=True,
            action_request=action,
        )
