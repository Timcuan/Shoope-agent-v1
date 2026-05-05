import logging
import json
from shopee_agent.providers.shopee.gateway import ShopeeGateway
from shopee_agent.persistence.repositories import LogisticsRepository, OrderRepository, ProductKnowledgeRepository

logger = logging.getLogger("shopee_agent.dispute_evidence")

class DisputeEvidenceAgent:
    """Collects objective evidence to challenge unfair refund requests."""
    
    def __init__(self, shopee_gateway: ShopeeGateway, order_repo: OrderRepository, pk_repo: ProductKnowledgeRepository):
        self.shopee_gateway = shopee_gateway
        self.order_repo = order_repo
        self.pk_repo = pk_repo

    async def collect_evidence(self, order_sn: str, shop_id: str) -> dict:
        """
        Gathers logistics history, weight information, and delivery photos.
        """
        evidence = {
            "logistics_status": "UNKNOWN",
            "weight_mismatch": False,
            "actual_weight": 0,
            "expected_weight": 0,
            "proof_of_delivery": None,
            "dispute_strategy": "INVESTIGATE"
        }
        
        try:
            # 1. Fetch Logistics Tracking
            logistics = await self.shopee_gateway.get_logistics_info(shop_id, order_sn)
            tracking_info = logistics.get("tracking_info", [])
            
            if tracking_info:
                last_status = tracking_info[0].get("description", "")
                evidence["logistics_status"] = last_status
                if any(k in last_status.lower() for k in ["delivered", "diterima", "selesai"]):
                    evidence["proof_of_delivery"] = "Logistics confirms delivery."

            # 2. Fetch Escrow/Finance for Weight
            escrow = await self.shopee_gateway.get_escrow_detail(shop_id, order_sn)
            # Shopee provides chargeable weight and sometimes actual weight
            actual_weight = escrow.get("order_chargeable_weight_gram", 0)
            evidence["actual_weight"] = actual_weight
            
            # 3. Calculate Expected Weight from Product Knowledge
            order_record = self.order_repo.get_order(order_sn, shop_id)
            if order_record:
                raw_data = json.loads(order_record.data_json or "{}")
                items = raw_data.get("item_list", [])
                
                total_expected = 0
                for item in items:
                    item_id = str(item.get("item_id", ""))
                    count = item.get("model_quantity_purchased", 1)
                    pk = self.pk_repo.get_pk(shop_id, item_id)
                    if pk:
                        total_expected += (pk.weight_gram * count)
                
                evidence["expected_weight"] = total_expected
                
                # 4. Weight Anomaly Detection (God-Tier Logic)
                # If actual weight is < 50% of expected, or difference > 1kg
                if total_expected > 0 and actual_weight > 0:
                    diff = total_expected - actual_weight
                    if actual_weight < (total_expected * 0.5) or diff > 1000:
                        evidence["weight_mismatch"] = True
                        evidence["dispute_strategy"] = "REJECT_WEIGHT_ANOMALY"
            
            if not evidence["weight_mismatch"] and evidence["proof_of_delivery"]:
                evidence["dispute_strategy"] = "REJECT_WITH_PROOF"
                
            return evidence
            
        except Exception as e:
            logger.error(f"Failed to collect evidence for {order_sn}: {e}")
            return evidence
