import pytest
import asyncio
from datetime import datetime, timedelta
from shopee_agent.persistence.repositories import (
    ShopTokenRepository, ShopTokenData, ReturnDisputeRepository, 
    OperatorTaskRepository, OrderRepository
)
from shopee_agent.app.dispute_agent import DisputeAgent
from shopee_agent.app.order_agent import OrderAgent
from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.providers.shopee.gateway import ShopeeGateway


class MockShopeeGateway:
    async def get_return_list(self, shop_id: str):
        return {"return_list": [{"return_sn": f"RET_{shop_id}_1"}]}
        
    async def get_return_detail(self, shop_id: str, return_sn: str):
        return {
            "return_sn": return_sn,
            "order_sn": f"ORD_{return_sn}",
            "buyer_user_id": 999,
            "reason": "DEFECTIVE",
            "status": "REQUESTED",
            "refund_amount": 250000.0,
            "text_reason": "It came broken",
            "image_urls": ["http://evid1"]
        }
        
    async def get_all_active_returns(self, shop_id: str):
        res = await self.get_return_list(shop_id)
        return res.get("return_list", [])


@pytest.mark.asyncio
async def test_e2e_multi_shop_sync_and_triage(db_session):
    """
    E2E scenario:
    1. Register two shops.
    2. Run parallel sync (Orders + Disputes).
    3. Verify data isolation and task creation.
    """
    # Setup
    token_repo = ShopTokenRepository(db_session)
    token_repo.upsert_token(ShopTokenData("shop_a", "a", "ra", datetime.now() + timedelta(days=1)))
    token_repo.upsert_token(ShopTokenData("shop_b", "b", "rb", datetime.now() + timedelta(days=1)))
    
    supervisor = OperationsSupervisorAgent(OperatorTaskRepository(db_session))
    mock_gateway = MockShopeeGateway()
    dispute_repo = ReturnDisputeRepository(db_session)
    order_repo = OrderRepository(db_session)
    
    # We simulate what sync_single_shop does
    async def run_sync_for_shop(shop_id):
        # Order Sync
        from shopee_agent.persistence.repositories import FinanceLedgerRepository
        ledger_repo = FinanceLedgerRepository(db_session)
        order_agent = OrderAgent(order_repo, ledger_repo, supervisor)
        demo_orders = [{"order_sn": f"O_{shop_id}", "order_status": "READY_TO_SHIP", "total_amount": 100}]
        await order_agent.ingest_orders(demo_orders, shop_id=shop_id)
        
        # Dispute Sync
        dispute_agent = DisputeAgent(mock_gateway, dispute_repo, supervisor, llm=None)
        await dispute_agent.sync_returns(shop_id)

    # Parallel Execution
    await asyncio.gather(run_sync_for_shop("shop_a"), run_sync_for_shop("shop_b"))
    
    # Assertions
    # 1. Orders isolated?
    assert order_repo.get_order("O_shop_a", "shop_a") is not None
    assert order_repo.get_order("O_shop_b", "shop_b") is not None
    
    # 2. Disputes triaged?
    active_a = dispute_repo.get_active_returns("shop_a")
    active_b = dispute_repo.get_active_returns("shop_b")
    assert len(active_a) == 1
    assert len(active_b) == 1
    assert active_a[0].shop_id == "shop_a"
    assert active_b[0].shop_id == "shop_b"
    
    # 3. Tasks created with shop_id?
    tasks = supervisor.task_repo.get_open_tasks(limit=10)
    assert len(tasks) >= 2
    shop_ids_in_tasks = [t.shop_id for t in tasks]
    assert "shop_a" in shop_ids_in_tasks
    assert "shop_b" in shop_ids_in_tasks
    
    # 4. Check severity (amount 250k > 200k threshold -> P1)
    dispute_task = next(t for t in tasks if t.category == "DISPUTE" and t.shop_id == "shop_a")
    assert dispute_task.severity == "P1"
