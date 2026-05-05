import pytest
import json
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime
from shopee_agent.app.dispute_agent import DisputeAgent
from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.contracts.dispute import ReturnData
from shopee_agent.persistence.repositories import ReturnDisputeRepository, OperatorTaskRepository, OrderRepository
from shopee_agent.providers.shopee.gateway import ShopeeGateway


@pytest.fixture
def mock_shopee_gateway():
    gateway = MagicMock(spec=ShopeeGateway)
    gateway.get_return_list = AsyncMock(return_value={
        "return_list": [{"return_sn": "RET123"}]
    })
    gateway.get_return_detail = AsyncMock(return_value={
        "return_sn": "RET123",
        "order_sn": "ORD123",
        "buyer_user_id": 999,
        "reason": "DEFECTIVE",
        "status": "REQUESTED",
        "refund_amount": 150000.0,
        "text_reason": "The item is broken",
        "image_urls": ["http://image1.jpg"]
    })
    gateway.get_all_active_returns = AsyncMock(return_value=[
        {"return_sn": "RET123"}
    ])
    gateway.get_logistics_info = AsyncMock(return_value={"tracking_info": []})
    gateway.get_escrow_detail = AsyncMock(return_value={})
    return gateway


@pytest.mark.asyncio
async def test_dispute_agent_sync_and_analyze(db_session, mock_shopee_gateway):
    dispute_repo = ReturnDisputeRepository(db_session)
    task_repo = OperatorTaskRepository(db_session)
    supervisor = OperationsSupervisorAgent(task_repo)
    
    agent = DisputeAgent(mock_shopee_gateway, dispute_repo, supervisor)
    
    # Mock PK Repo for evidence agent internal call
    # Note: DisputeAgent creates repositories internally from its session
    # so we might need to mock the imports or just let it run if db_session is fine
    
    # Sync returns
    synced = await agent.sync_returns("shop1")
    assert synced == 1
    
    # Verify persistence
    res = dispute_repo.get_return("RET123")
    assert res is not None
    assert res.reason == "DEFECTIVE"
    assert res.amount == 150000.0
    
    # Verify task creation
    tasks = task_repo.get_open_tasks(limit=10)
    assert len(tasks) == 1
    assert tasks[0].category == "DISPUTE"
    assert "DEFECTIVE" in tasks[0].title
    assert "RET123" in tasks[0].subject_id


@pytest.mark.asyncio
async def test_dispute_agent_llm_analysis(db_session, mock_shopee_gateway):
    dispute_repo = ReturnDisputeRepository(db_session)
    task_repo = OperatorTaskRepository(db_session)
    supervisor = OperationsSupervisorAgent(task_repo)
    
    # Mock LLM
    from shopee_agent.contracts.knowledge import ChatAnalysis
    mock_llm = MagicMock()
    mock_llm.analyze_message = AsyncMock(return_value=ChatAnalysis(
        sentiment_score=-0.8,
        urgency_score=0.9,
        reasoning="Strong evidence of damage"
    ))
    
    agent = DisputeAgent(mock_shopee_gateway, dispute_repo, supervisor, llm=mock_llm)
    
    data = ReturnData(
        return_sn="RET456", order_sn="ORD456", shop_id="shop1", 
        buyer_id="999", reason="WRONG_ITEM", status="REQUESTED", amount=50000.0
    )
    
    await agent.analyze_case(data)
    
    # Verify analysis in repo
    record = dispute_repo.get_return("RET456")
    # Note: analyze_case upserts to repo if called directly or via sync
    # In my implementation analyze_case calls update_analysis
    
    # Check task severity for high risk
    tasks = task_repo.get_open_tasks(limit=10)
    # Severity should be P1 because risk_score (urgency) is 0.9
    assert tasks[0].severity == "P1"


@pytest.mark.asyncio
async def test_dispute_agent_weight_anomaly(db_session, mock_shopee_gateway):
    from shopee_agent.persistence.repositories import ProductKnowledgeRepository
    from shopee_agent.contracts.knowledge import ProductFact
    from shopee_agent.contracts.domain import OrderData
    
    dispute_repo = ReturnDisputeRepository(db_session)
    task_repo = OperatorTaskRepository(db_session)
    order_repo = OrderRepository(db_session)
    pk_repo = ProductKnowledgeRepository(db_session)
    supervisor = OperationsSupervisorAgent(task_repo)

    # 1. Setup Order with 1.2kg expected weight
    order_data = OrderData(
        order_sn="ORD_WEIGHT_BUG", shop_id="shop1", status="COMPLETED", total_amount=500000,
        data_json=json.dumps({
            "item_list": [{"item_id": "ITEM1", "model_quantity_purchased": 1}]
        })
    )
    order_repo.upsert_order(order_data)
    
    # 2. Setup Product Knowledge
    pk_repo.upsert_pk(ProductFact(
        item_id="ITEM1", shop_id="shop1", name="Heavy Item", 
        weight_gram=1200, category="Tools"
    ))
    
    # 3. Mock Escrow to return 400g (Clear Fraud!)
    mock_shopee_gateway.get_escrow_detail.return_value = {
        "order_chargeable_weight_gram": 400
    }
    mock_shopee_gateway.get_logistics_info.return_value = {
        "tracking_info": [{"description": "Delivered to buyer"}]
    }

    agent = DisputeAgent(mock_shopee_gateway, dispute_repo, supervisor)
    
    data = ReturnData(
        return_sn="RET_WEIGHT", order_sn="ORD_WEIGHT_BUG", shop_id="shop1", 
        buyer_id="999", reason="EMPTY_PARCEL", status="REQUESTED", amount=500000.0
    )
    
    # 4. Trigger evidence collection manually for deep testing
    from shopee_agent.app.dispute_evidence_agent import DisputeEvidenceAgent
    evidence_agent = DisputeEvidenceAgent(mock_shopee_gateway, order_repo, pk_repo)
    evidence = await evidence_agent.collect_evidence(data.order_sn, data.shop_id)
    
    # Run analysis with gathered evidence
    await agent.analyze_case(data, evidence)
    
    # 5. Verify Task Summary contains the flag
    tasks = task_repo.get_open_tasks(limit=10)
    task = next(t for t in tasks if t.subject_id == "RET_WEIGHT")
    
    assert "REJECT WEIGHT ANOMALY" in task.summary # Strategy comes from evidence which is still English key
    assert "Berat: `400g` (Exp: `1200g`)" in task.summary
    assert task.severity == "P0"
