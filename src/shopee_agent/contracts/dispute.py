from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ReturnData:
    return_sn: str
    order_sn: str
    shop_id: str
    buyer_id: str | None
    reason: str
    status: str
    amount: float
    text_reason: str | None = None
    evidence_urls: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class DisputeAnalysis:
    summary: str
    risk_score: float  # 0.0 to 1.0
    recommendation: str  # "accept" | "reject" | "escalate"
    reasoning: str
    evidence_found: list[str] = field(default_factory=list)


@dataclass
class DisputeDecision:
    return_sn: str
    action: str  # "accept" | "reject" | "escalate"
    operator_note: str | None = None
    decided_at: datetime = field(default_factory=datetime.now)
