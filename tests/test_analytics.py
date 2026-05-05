import pytest
from datetime import datetime, timedelta
from shopee_agent.app.analytics_agent import AnalyticsAgent
from shopee_agent.persistence.repositories import OrderRepository, ReturnDisputeRepository, OrderData, ReturnData

@pytest.mark.asyncio
async def test_analytics_kpi_calculation(db_session):
    order_repo = OrderRepository(db_session)
    dispute_repo = ReturnDisputeRepository(db_session)
    
    now = datetime.now()
    this_month_start = datetime(now.year, now.month, 1) + timedelta(hours=1)
    
    # Add some data
    order_repo.upsert_order(OrderData(
        order_sn="ORD_ANALYTICS_1", shop_id="shop1", status="COMPLETED",
        total_amount=100000.0, buyer_id="1", pay_time=this_month_start
    ))
    
    # Dispute count doesn't need to be async yet based on repo implementation (using cat append)
    # Wait, my cat append used session.scalars().all() which is sync.
    
    agent = AnalyticsAgent(order_repo, dispute_repo)
    report = agent.get_monthly_dashboard("shop1")
    
    assert report["revenue"] == 100000.0
    assert report["order_count"] == 1
    assert report["dispute_rate"] == 0.0
