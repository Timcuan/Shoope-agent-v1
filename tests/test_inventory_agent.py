import pytest

from shopee_agent.app.inventory_agent import InventoryAgent
from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.contracts.operations import TaskSeverity
from shopee_agent.persistence.repositories import InventoryRepository, OperatorTaskRepository


def make_inventory_agent(db_session, threshold: int = 5):
    supervisor = OperationsSupervisorAgent(OperatorTaskRepository(db_session))
    agent = InventoryAgent(
        inventory_repo=InventoryRepository(db_session),
        supervisor=supervisor,
        low_stock_threshold=threshold,
    )
    return agent, supervisor


def test_inventory_sync_creates_records(db_session) -> None:
    agent, _ = make_inventory_agent(db_session)
    items = [
        {"item_id": "1001", "item_name": "Widget A", "model": [
            {"model_id": "m1", "model_name": "Blue", "normal_stock": 20, "price": 50000},
            {"model_id": "m2", "model_name": "Red", "normal_stock": 15, "price": 55000},
        ]},
    ]
    result = agent.sync_inventory("shop1", items)
    assert result["synced"] == 2
    assert result["low_stock_flagged"] == 0

    repo = InventoryRepository(db_session)
    # Both stocks (20, 15) are above default threshold (5)
    low = repo.get_low_stock("shop1", threshold=5)
    assert len(low) == 0  # both are well above threshold=5


def test_inventory_sync_triggers_low_stock_task(db_session) -> None:
    agent, supervisor = make_inventory_agent(db_session, threshold=10)
    items = [
        {"item_id": "2001", "item_name": "Rare Item", "model": [
            {"model_id": "", "normal_stock": 3, "price": 100000},
        ]},
    ]
    result = agent.sync_inventory("shop1", items)

    assert result["low_stock_flagged"] == 1
    task = supervisor.task_repo.get_task("lowstock_shop1_2001_")
    assert task is not None
    assert task.category == "inventory"
    # stock=3 > 0, threshold=10 → P2 (P1 only when stock==0)
    assert task.severity == TaskSeverity.P2.value


def test_inventory_sync_zero_stock_is_p1(db_session) -> None:
    agent, supervisor = make_inventory_agent(db_session)
    items = [{"item_id": "3001", "item_name": "Sold Out", "model": [
        {"model_id": "", "normal_stock": 0, "price": 99000},
    ]}]
    agent.sync_inventory("shop1", items)
    task = supervisor.task_repo.get_task("lowstock_shop1_3001_")
    assert task is not None
    assert task.severity == TaskSeverity.P1.value


def test_inventory_upsert_is_idempotent(db_session) -> None:
    agent, _ = make_inventory_agent(db_session, threshold=0)
    items = [{"item_id": "4001", "item_name": "Stable", "model": [
        {"model_id": "", "normal_stock": 50, "price": 10000},
    ]}]
    agent.sync_inventory("shop1", items)
    # Update stock
    items[0]["model"][0]["normal_stock"] = 45
    agent.sync_inventory("shop1", items)

    repo = InventoryRepository(db_session)
    from sqlalchemy import select
    from shopee_agent.persistence.models import InventoryRecord
    record = db_session.scalar(
        select(InventoryRecord).where(
            InventoryRecord.shop_id == "shop1",
            InventoryRecord.item_id == "4001",
        )
    )
    assert record.stock == 45
