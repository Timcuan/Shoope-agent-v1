import pytest
from shopee_agent.app.chat_agent import ChatAgent
from shopee_agent.contracts.domain import OrderData


def test_chat_agent_classify_order_status():
    agent = ChatAgent()
    classification = agent.classify("Kapan pesanan saya dikirim?")
    assert classification.intent == "order_status"
    assert classification.risk_tier == "low"


def test_chat_agent_classify_abuse():
    agent = ChatAgent()
    classification = agent.classify("Penipu bangsat asu")
    assert classification.intent == "abuse"
    assert classification.risk_tier == "high"


def test_chat_agent_classify_refund():
    agent = ChatAgent()
    classification = agent.classify("Saya mau refund uang kembali dana")
    assert classification.intent == "refund"
    assert classification.risk_tier == "high"


@pytest.mark.asyncio
async def test_chat_agent_decide_auto_reply():
    agent = ChatAgent()
    msg = "Halo kak"
    classification = agent.classify(msg)
    decision = await agent.decide(msg, classification)
    assert decision.action == "auto_reply"
    assert "halo" in decision.draft_reply.lower()


@pytest.mark.asyncio
async def test_chat_agent_decide_draft_on_product_question_no_facts():
    agent = ChatAgent()
    msg = "Barangnya ready?"
    classification = agent.classify(msg)
    decision = await agent.decide(msg, classification)
    # Medium risk because no product facts provided to verify
    assert decision.action == "draft_for_approval"


@pytest.mark.asyncio
async def test_chat_agent_decide_escalate_on_high_value_complaint():
    agent = ChatAgent()
    order = OrderData(order_sn="ORD123", shop_id="shop1", status="SHIPPED", total_amount=1000000)
    msg = "Barangnya rusak jelek cacat"
    classification = agent.classify(msg, order_context=order)
    
    assert classification.intent == "complaint"
    assert classification.risk_tier == "high"  # High value order
    
    decision = await agent.decide(msg, classification, order_context=order)
    assert decision.action == "escalate"


@pytest.mark.asyncio
async def test_chat_agent_decide_draft_on_medium_risk():
    agent = ChatAgent()
    order = OrderData(order_sn="ORD123", shop_id="shop1", status="SHIPPED", total_amount=100000)
    msg = "Barangnya salah warna"
    classification = agent.classify(msg, order_context=order)
    
    assert classification.intent == "complaint"
    assert classification.risk_tier == "medium"
    
    decision = await agent.decide(msg, classification, order_context=order)
    assert decision.action == "draft_for_approval"
    assert "maaf" in decision.draft_reply.lower()
