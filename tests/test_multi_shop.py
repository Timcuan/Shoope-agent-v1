import pytest
from datetime import datetime
from shopee_agent.persistence.repositories import ShopTokenRepository, ShopTokenData, OrderRepository, OperatorTaskRepository
from shopee_agent.contracts.domain import OrderData
from shopee_agent.contracts.operations import OperatorTask, TaskSeverity, TaskStatus
from shopee_agent.app.operations import OperationsSupervisorAgent


def test_multi_shop_token_retrieval(db_session):
    repo = ShopTokenRepository(db_session)
    
    t1 = ShopTokenData(shop_id="shop1", access_token="a1", refresh_token="r1", expires_at=datetime.now())
    t2 = ShopTokenData(shop_id="shop2", access_token="a2", refresh_token="r2", expires_at=datetime.now())
    
    repo.upsert_token(t1)
    repo.upsert_token(t2)
    
    shops = repo.get_all_tokens()
    assert len(shops) == 2
    shop_ids = [s.shop_id for s in shops]
    assert "shop1" in shop_ids
    assert "shop2" in shop_ids


def test_multi_shop_task_isolation(db_session):
    task_repo = OperatorTaskRepository(db_session)
    supervisor = OperationsSupervisorAgent(task_repo)
    
    task1 = OperatorTask(
        task_id="t1", category="TEST", subject_id="s1", shop_id="shop1",
        severity=TaskSeverity.P1, title="Task 1", summary="Sum 1"
    )
    task2 = OperatorTask(
        task_id="t2", category="TEST", subject_id="s2", shop_id="shop2",
        severity=TaskSeverity.P1, title="Task 2", summary="Sum 2"
    )
    
    supervisor.create_task(task1)
    supervisor.create_task(task2)
    
    # Verify both exist but have correct shop_id
    res1 = task_repo.get_task("t1")
    assert res1.shop_id == "shop1"
    
    res2 = task_repo.get_task("t2")
    assert res2.shop_id == "shop2"


def test_multi_shop_order_isolation(db_session):
    repo = OrderRepository(db_session)
    
    o1 = OrderData(order_sn="SN1", shop_id="shop1", status="READY_TO_SHIP", total_amount=100)
    o2 = OrderData(order_sn="SN1", shop_id="shop2", status="READY_TO_SHIP", total_amount=200)
    
    repo.upsert_order(o1)
    repo.upsert_order(o2)
    
    # Should be distinct records due to unique constraint (shop_id, order_sn)
    res1 = repo.get_order("SN1", "shop1")
    assert res1.total_amount == 100
    
    res2 = repo.get_order("SN1", "shop2")
    assert res2.total_amount == 200
