from __future__ import annotations

from shopee_agent.contracts.domain import InventoryItem
from shopee_agent.contracts.operations import OperatorTask, TaskSeverity
from shopee_agent.persistence.repositories import InventoryRepository
from shopee_agent.app.operations import OperationsSupervisorAgent

DEFAULT_LOW_STOCK_THRESHOLD = 5


class InventoryAgent:
    """Maintains local inventory cache and raises low-stock operator tasks."""

    def __init__(
        self,
        inventory_repo: InventoryRepository,
        supervisor: OperationsSupervisorAgent,
        low_stock_threshold: int = DEFAULT_LOW_STOCK_THRESHOLD,
    ) -> None:
        self.inventory_repo = inventory_repo
        self.supervisor = supervisor
        self.low_stock_threshold = low_stock_threshold

    def sync_inventory(self, shop_id: str, items: list[dict]) -> dict:
        """
        Upsert items from raw product list (gateway or simulator).
        Automatically creates P2 OperatorTask for low-stock items.
        Returns a summary dict.
        """
        synced = 0
        low_stock_flagged = 0

        for raw in items:
            # Support both flat and nested model responses
            models = raw.get("model", [raw])
            item_id = str(raw.get("item_id", raw.get("id", "")))
            base_name = raw.get("item_name", raw.get("name", "Unknown"))

            for model in models:
                model_id = str(model.get("model_id", ""))
                stock = int(model.get("normal_stock", model.get("stock", 0)))
                reserved = int(model.get("reserved_stock", 0))
                price_info = model.get("price_info", [{}])
                price = float(
                    price_info[0].get("current_price", model.get("price", 0))
                    if price_info else model.get("price", 0)
                )
                name = model.get("model_name") or base_name
                sku = model.get("model_sku") or raw.get("item_sku")

                self.inventory_repo.upsert_item(InventoryItem(
                    shop_id=shop_id,
                    item_id=item_id,
                    model_id=model_id,
                    sku=sku,
                    name=name,
                    stock=stock,
                    reserved_stock=reserved,
                    price=price,
                ))
                synced += 1

                if stock <= self.low_stock_threshold:
                    self.supervisor.create_task(OperatorTask(
                        task_id=f"lowstock_{shop_id}_{item_id}_{model_id}",
                        category="inventory",
                        subject_id=item_id,
                        severity=TaskSeverity.P2 if stock > 0 else TaskSeverity.P1,
                        title=f"Low Stock: {name}",
                        summary=(
                            f"'{name}' (SKU: {sku or 'N/A'}) has {stock} unit(s) remaining "
                            f"(threshold: {self.low_stock_threshold})."
                        ),
                    ))
                    low_stock_flagged += 1

        return {"synced": synced, "low_stock_flagged": low_stock_flagged}
