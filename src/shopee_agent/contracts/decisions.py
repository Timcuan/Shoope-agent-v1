from __future__ import annotations

from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class RiskTier(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(default_factory=lambda: f"act_{uuid4().hex}")
    action_type: str
    subject_id: str
    idempotency_key: str
    payload: dict = Field(default_factory=dict)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str = Field(default_factory=lambda: f"dec_{uuid4().hex}")
    event_id: str
    agent_name: str
    subject_type: str
    subject_id: str
    risk_tier: RiskTier
    confidence: float
    policy_version: str
    feature_flag: str
    context_id: str
    reason_codes: list[str]
    recommended_action: str
    requires_human: bool
    action_request: ActionRequest | None = None

    def explain(self) -> str:
        action_request_summary = "none"
        if self.action_request is not None:
            action_request_summary = (
                f"{self.action_request.action_id}/{self.action_request.action_type}"
            )

        return (
            f"Decision {self.decision_id}: event={self.event_id}, "
            f"context={self.context_id}, policy={self.policy_version}, "
            f"flag={self.feature_flag}, risk={self.risk_tier}, "
            f"confidence={self.confidence}, action={self.recommended_action}, "
            f"requires_human={self.requires_human}, "
            f"action_request={action_request_summary}, "
            f"reasons={','.join(self.reason_codes)}"
        )
