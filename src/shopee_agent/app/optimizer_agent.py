import logging
from datetime import datetime, timedelta
from shopee_agent.persistence.repositories import OrderRepository, ProductKnowledgeRepository

logger = logging.getLogger("shopee_agent.optimizer")

class OptimizerAgent:
    """Proactively analyzes shop performance and suggests optimizations."""
    
    def __init__(self, session, llm_gateway):
        self.session = session
        self.llm = llm_gateway

    async def run_daily_audit(self, shop_id: str) -> str | None:
        """Audits shop performance and generates proactive tips."""
        order_repo = OrderRepository(self.session)
        
        # 1. Get Sales Trends (Last 7 days vs Previous 7 days)
        now = datetime.now()
        current_week = order_repo.get_item_sales_stats(shop_id, days=7)
        prev_week = order_repo.get_item_sales_stats(shop_id, days=14) # Need to filter properly in real repo
        
        # Simple Logic: If total sales dropped by > 20%
        curr_total = sum(current_week.values())
        prev_total = sum(prev_week.values()) - curr_total
        
        if curr_total < prev_total * 0.8:
            return await self._generate_recovery_plan(shop_id, current_week, prev_week)
        
        return None

    async def _generate_recovery_plan(self, shop_id: str, current_stats: dict, prev_stats: dict) -> str:
        prompt = (
            f"Penjualan toko {shop_id} turun drastis minggu ini ({sum(current_stats.values())} vs {sum(prev_stats.values()) - sum(current_stats.values())} minggu lalu).\n"
            f"Data Produk:\n{current_stats}\n\n"
            f"Berikan 3 saran konkret untuk mendongkrak penjualan (misal: flash sale, optimasi kata kunci, atau iklan)."
        )
        
        plan = await self.llm.generate_response(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="Anda adalah Business Optimization Consultant untuk e-commerce Shopee."
        )
        return plan
