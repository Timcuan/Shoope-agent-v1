from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class FAQEntry:
    question: str
    answer: str


@dataclass
class ProductVariant:
    """A single product model/variation (e.g., 'Red / XL')."""
    model_id: str
    name: str
    price: float = 0.0
    stock: int = 0
    sku: str = ""


@dataclass
class ProductFact:
    item_id: str
    shop_id: str
    name: str
    category: str | None = None
    # Pricing
    price_min: float = 0.0
    price_max: float = 0.0
    # Variants / Models
    variants: list[ProductVariant] = field(default_factory=list)
    # Physical attributes
    weight_gram: int = 0
    condition: str = "NEW"           # "NEW" | "USED"
    # Content
    description: str = ""
    spec_json: dict = field(default_factory=dict)   # e.g. {"Bahan": "Cotton", "Garansi": "1 Tahun"}
    # CS Knowledge
    selling_points: list[str] = field(default_factory=list)
    forbidden_claims: list[str] = field(default_factory=list)
    faq: list[FAQEntry] = field(default_factory=list)
    aliases: list[str] = field(default_factory=list)


@dataclass
class ChatMessage:
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ChatClassification:
    intent: str
    risk_tier: str  # "low" | "medium" | "high"
    confidence: float
    reason_codes: list[str] = field(default_factory=list)


@dataclass
class ChatDecision:
    action: str  # "auto_reply" | "draft_for_approval" | "escalate" | "freeze"
    draft_reply: str | None = None
    reason_codes: list[str] = field(default_factory=list)
    classification: ChatClassification | None = None


@dataclass
class ChatAnalysis:
    sentiment_score: float  # -1.0 to 1.0
    urgency_score: float  # 0.0 to 1.0
    suggested_intent: str | None = None
    buyer_mood: str | None = None  # e.g. "angry", "happy", "anxious"
    reasoning: str | None = None
