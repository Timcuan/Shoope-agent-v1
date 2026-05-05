from datetime import UTC, datetime, timedelta

import pytest

from shopee_agent.app.operations import OperationsSupervisorAgent
from shopee_agent.app.order_agent import OrderAgent
from shopee_agent.contracts.operations import TaskStatus
from shopee_agent.persistence.repositories import (
    FinanceLedgerRepository,
    OperatorTaskRepository,
    OrderRepository,
)


def make_order_agent(db_session):
    supervisor = OperationsSupervisorAgent(OperatorTaskRepository(db_session))
    return OrderAgent(
        order_repo=OrderRepository(db_session),
        ledger_repo=FinanceLedgerRepository(db_session),
        supervisor=supervisor,
    ), supervisor


@pytest.mark.asyncio
async def test_order_agent_ingest_creates_records(db_session) -> None:
    agent, supervisor = make_order_agent(db_session)

    orders = [
        {"order_sn": "ORD001", "order_status": "READY_TO_SHIP", "total_amount": 100000},
        {"order_sn": "ORD002", "order_status": "PROCESSED", "total_amount": 50000},
    ]
    result = await agent.ingest_orders(orders, shop_id="shop1")

    assert result.synced == 2
    assert result.created == 2
    assert result.updated == 0

    repo = OrderRepository(db_session)
    stored = repo.get_orders_by_status("shop1", "READY_TO_SHIP")
    assert len(stored) == 1
    assert stored[0].order_sn == "ORD001"
    assert stored[0].total_amount == 100000.0


@pytest.mark.asyncio
async def test_order_agent_upsert_is_idempotent(db_session) -> None:
    agent, _ = make_order_agent(db_session)
    orders = [{"order_sn": "ORD001", "order_status": "READY_TO_SHIP", "total_amount": 100000}]

    result1 = await agent.ingest_orders(orders, shop_id="shop1")
    # Second call with updated status
    orders[0]["order_status"] = "SHIPPED"
    result2 = await agent.ingest_orders(orders, shop_id="shop1")

    assert result1.created == 1
    assert result2.updated == 1
    assert result2.created == 0

    repo = OrderRepository(db_session)
    stored = repo.get_orders_by_status("shop1", "SHIPPED")
    assert len(stored) == 1


@pytest.mark.asyncio
async def test_order_agent_sla_task_created_when_close(db_session) -> None:
    agent, supervisor = make_order_agent(db_session)
    import time
    now = int(time.time())

    # Ship by in 4 hours — should trigger P0 SLA task
    orders = [{
        "order_sn": "SLA001",
        "order_status": "READY_TO_SHIP",
        "total_amount": 200000,
        "ship_by_date": now + 3600 * 4,
    }]
    result = await agent.ingest_orders(orders, shop_id="shop1")

    assert result.sla_tasks_created == 1
    task = supervisor.task_repo.get_task("sla_SLA001")
    assert task is not None
    assert task.category == "order"
    assert task.severity in ("P0", "P1")


@pytest.mark.asyncio
async def test_order_agent_no_sla_task_when_not_close(db_session) -> None:
    agent, supervisor = make_order_agent(db_session)
    import time
    now = int(time.time())

    # Ship by in 2 days — no SLA task needed
    orders = [{
        "order_sn": "NOSLA001",
        "order_status": "READY_TO_SHIP",
        "total_amount": 100000,
        "ship_by_date": now + 3600 * 48,
    }]
    result = await agent.ingest_orders(orders, shop_id="shop1")
    assert result.sla_tasks_created == 0


@pytest.mark.asyncio
async def test_finance_ledger_created_alongside_order(db_session) -> None:
    agent, _ = make_order_agent(db_session)
    orders = [{"order_sn": "FIN001", "order_status": "READY_TO_SHIP", "total_amount": 200000}]
    await agent.ingest_orders(orders, shop_id="shop1")

    from shopee_agent.persistence.repositories import FinanceLedgerRepository
    ledger_repo = FinanceLedgerRepository(db_session)
    # Ledger record should have been created with estimated_income = 200000 * 0.98
    from sqlalchemy import select
    from shopee_agent.persistence.models import FinanceLedgerRecord
    record = db_session.scalar(
        select(FinanceLedgerRecord).where(FinanceLedgerRecord.order_sn == "FIN001")
    )
    assert record is not None
    assert record.estimated_income == pytest.approx(196000.0)
