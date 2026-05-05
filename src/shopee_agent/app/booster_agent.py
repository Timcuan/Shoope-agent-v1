import logging
from datetime import datetime, timedelta
from sqlalchemy import select, delete
from shopee_agent.persistence.models import BoostSlotRecord
from shopee_agent.persistence.repositories import OrderRepository, ProductKnowledgeRepository

logger = logging.getLogger("shopee_agent.booster")

class BoosterAgent:
    """Rotates top-selling products in Shopee's 'Boost' (Naikkan Produk) slots every 4 hours."""
    
    def __init__(self, session, gateway):
        self.session = session
        self.gateway = gateway

    async def auto_rotate_boosts(self, shop_id: str):
        """Main loop: Check expired boosts and trigger new ones."""
        # 1. Clean up expired boosts in DB
        now = datetime.now()
        self.session.execute(
            delete(BoostSlotRecord).where(
                BoostSlotRecord.shop_id == shop_id,
                BoostSlotRecord.expires_at <= now
            )
        )
        self.session.commit()
        
        # 2. Check current active slots
        current_slots = self.session.scalars(
            select(BoostSlotRecord).where(BoostSlotRecord.shop_id == shop_id)
        ).all()
        
        if len(current_slots) >= 5:
            logger.info(f"[Booster] {shop_id} slots full ({len(current_slots)}/5)")
            return []

        # 3. Pick candidates (Top 5 selling items not currently boosted)
        order_repo = OrderRepository(self.session)
        stats = order_repo.get_item_sales_stats(shop_id, days=14)
        
        currently_boosted_ids = [s.item_id for s in current_slots]
        candidates = sorted(
            [iid for iid in stats.keys() if iid not in currently_boosted_ids],
            key=lambda x: stats[x],
            reverse=True
        )[:5 - len(current_slots)]
        
        newly_boosted = []
        if candidates:
            res = await self.gateway.boost_item(shop_id, [int(iid) for iid in candidates])
            success_ids = res.get("success_list", [])
            
            for item_id in success_ids:
                record = BoostSlotRecord(
                    shop_id=shop_id,
                    item_id=str(item_id),
                    boosted_at=now,
                    expires_at=now + timedelta(hours=4, minutes=5) # 5 min buffer
                )
                self.session.add(record)
                newly_boosted.append(str(item_id))
                logger.info(f"[Booster] Boosted item {item_id} for {shop_id}")
        
        self.session.commit()
        return newly_boosted

    def get_active_boosts(self, shop_id: str):
        return self.session.scalars(
            select(BoostSlotRecord).where(BoostSlotRecord.shop_id == shop_id)
        ).all()
