import pytest
from unittest.mock import AsyncMock, MagicMock
from shopee_agent.app.chat_agent import ChatAgent
from shopee_agent.contracts.knowledge import ChatAnalysis, ChatClassification
from shopee_agent.providers.llm.gateway import LLMGateway


@pytest.fixture
def mock_llm():
    llm = MagicMock(spec=LLMGateway)
    llm.analyze_message = AsyncMock(return_value=ChatAnalysis(
        sentiment_score=-0.9, 
        urgency_score=0.9, 
        suggested_intent="complaint",
        buyer_mood="angry",
        reasoning="User is very upset"
    ))
    llm.draft_response = AsyncMock(return_value="Maaf Kak, kami bantu cek.")
    llm.generate_response = AsyncMock(return_value="Indonesian") # For language detection
    return llm


@pytest.mark.asyncio
async def test_chat_agent_with_llm_escalation(mock_llm):
    agent = ChatAgent(llm=mock_llm)
    msg = "BARANG SAYA MANA?! SUDAH SEMINGGU!"
    
    # Deterministic might say order_status low risk
    classification = agent.classify(msg)
    assert classification.intent == "order_status"
    assert classification.risk_tier == "low"
    
    # LLM should escalate it due to sentiment/urgency
    decision = await agent.decide(msg, classification)
    
    assert decision.classification.risk_tier == "medium"  # low -> medium refinement
    assert "llm_detected_high_urgency_or_negativity" in decision.reason_codes
    assert "llm_generated_draft" in decision.reason_codes
    assert decision.draft_reply == "Maaf Kak, kami bantu cek."


@pytest.mark.asyncio
async def test_chat_agent_llm_drafting(mock_llm):
    agent = ChatAgent(llm=mock_llm)
    msg = "Halo"
    classification = agent.classify(msg)
    
    # Mock analysis for positive sentiment
    mock_llm.analyze_message.return_value = ChatAnalysis(
        sentiment_score=0.8, urgency_score=0.1, suggested_intent="general"
    )
    
    decision = await agent.decide(msg, classification)
    assert decision.action == "auto_reply"
    assert "llm_generated_draft" in decision.reason_codes
    assert decision.draft_reply == "Maaf Kak, kami bantu cek." # from mock
