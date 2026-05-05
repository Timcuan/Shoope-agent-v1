from datetime import datetime, timedelta
from typing import Callable, Coroutine, Any
from sqlalchemy import select, func
from shopee_agent.persistence.models import OrderRecord, InventoryRecord, OperatorTaskRecord
from shopee_agent.persistence.repositories import OperatorTaskRepository, OrderRepository
from shopee_agent.contracts.operations import OperatorTask, TaskSeverity, TaskStatus

class InventoryHealthAgent:
    def __init__(self, session, supervisor=None, notify_fn: Callable[[str], Coroutine[Any, Any, None]] | None = None):
        self.session = session
        self.supervisor = supervisor
        self.notify_fn = notify_fn

    async def check_health(self, shop_id: str):
        # 1. Calculate REAL item sales velocity (last 14 days for more stability)
        order_repo = OrderRepository(self.session)
        item_stats = order_repo.get_item_sales_stats(shop_id, days=14)
        
        # 2. Check inventory
        inv_stmt = select(InventoryRecord).where(InventoryRecord.shop_id == shop_id)
        items = self.session.scalars(inv_stmt).all()
        
        alerts = []
        for item in items:
            total_sold = item_stats.get(item.item_id, 0)
            daily_velocity = total_sold / 14.0
            
            # Default fallback if no sales but we want some buffer
            if daily_velocity == 0:
                runway_days = 999
            else:
                runway_days = item.stock / daily_velocity
            
            if runway_days < 7:
                severity = "p0" if runway_days < 3 else "p1"
                alerts.append({
                    "item_id": item.item_id,
                    "name": item.name,
                    "stock": item.stock,
                    "velocity": round(daily_velocity, 2),
                    "runway": round(runway_days, 1),
                    "severity": severity
                })
                
                if self.supervisor:
                    task_id = f"inv_{shop_id}_{item.item_id}"
                    if not self.supervisor.task_repo.task_exists(task_id):
                        self.supervisor.create_task(OperatorTask(
                            task_id=task_id,
                            category="inventory",
                            subject_id=item.item_id,
                            shop_id=shop_id,
                            severity=TaskSeverity.P0 if severity == "p0" else TaskSeverity.P1,
                            title=f"Stok Kritis: {item.name}",
                            summary=f"Penjualan cepat! Runway: {round(runway_days, 1)} hari. Stok: {item.stock}.",
                            due_at=datetime.now() + timedelta(hours=48),
                        ))
        
        if alerts and self.notify_fn:
            text = self.get_stock_status_text(alerts, shop_id)
            import asyncio
            asyncio.create_task(self.notify_fn(text))
        
        return alerts

    def propose_restock_plan(self, shop_id: str):
        """Propose exact restock quantities to maintain 30 days of inventory."""
        order_repo = OrderRepository(self.session)
        item_stats = order_repo.get_item_sales_stats(shop_id, days=14)
        
        inv_stmt = select(InventoryRecord).where(InventoryRecord.shop_id == shop_id)
        items = self.session.scalars(inv_stmt).all()
        
        proposals = []
        for item in items:
            velocity = item_stats.get(item.item_id, 0) / 14.0
            target_stock = velocity * 30 # 30 days buffer
            
            if item.stock < target_stock or item.stock < 5: # Basic minimum buffer
                restock_qty = int(max(target_stock - item.stock, 10)) # Minimum 10 units
                proposals.append({
                    "item_id": item.item_id,
                    "name": item.name,
                    "sku": item.sku,
                    "current_stock": item.stock,
                    "velocity": round(velocity, 2),
                    "restock_qty": restock_qty,
                    "priority": "HIGH" if item.stock < (velocity * 3) else "MEDIUM"
                })
        
        return proposals

    def get_stock_status_text(self, alerts, shop_id):
        if not alerts:
            return f"✅ **Kesehatan Stok: {shop_id}**\nWah mantap Kak, stok aman semua! (> 7 hari)."
            
        text = f"🚨 **Peringatan Stok: {shop_id}**\n━━━━━━━━━━━━━━━\n\n"
        for a in alerts:
            icon = "🔴" if a["severity"] == "p0" else "🟡"
            text += f"{icon} *{a['name']}*\n   Sisa Stok: `{a['stock']} pcs` | Estimasi Habis: `{a['runway']} hari lagi`\n\n"
        
        text += "━━━━━━━━━━━━━━━\n💡 *Saran AI:* Segera restock barang-barang di atas agar tidak kehabisan (lost sales) ya Kak!"
        return text
