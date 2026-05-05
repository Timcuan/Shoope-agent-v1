import logging
from datetime import datetime, timedelta
from shopee_agent.persistence.repositories import OrderRepository, InventoryRepository

logger = logging.getLogger("shopee_agent.bi")

class BusinessIntelligenceAgent:
    """Provides strategic insights and operational alerts based on shop data."""
    
    def __init__(self, order_repo: OrderRepository, inventory_repo: InventoryRepository):
        self.order_repo = order_repo
        self.inventory_repo = inventory_repo

    def get_daily_snapshot(self, shop_id: str) -> str:
        """Generates a high-level strategic summary for the day."""
        today = datetime.now()
        yesterday = today - timedelta(days=1)
        
        # 1. Fetch Sales Data
        orders = self.order_repo.get_for_shop(shop_id) # Simplify for now
        today_orders = [o for o in orders if o.pay_time and o.pay_time.date() == today.date()]
        
        total_rev = sum(o.total_amount for o in today_orders)
        order_count = len(today_orders)
        
        # 2. Inventory Alerts
        low_stock_items = self.inventory_repo.get_low_stock(shop_id, threshold=5)
        
        # 3. Format Premium Report
        report = (
            f"🚀 **Laporan Intelijen Harian**\n"
            f"📅 `{today.strftime('%d %b %Y')}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 **Omzet:** `Rp {total_rev:,.0f}`\n"
            f"📦 **Pesanan:** `{order_count}`\n"
            f"📈 **Rata-rata Tiket:** `Rp {total_rev/order_count if order_count > 0 else 0:,.0f}`\n"
            f"━━━━━━━━━━━━━━━━━━\n"
        )
        
        if low_stock_items:
            report += "⚠️ **Peringatan Stok:**\n"
            for item in low_stock_items[:3]:
                report += f"• `{item.item_name[:20]}...` (Stok: {item.stock})\n"
        else:
            report += "✅ **Stok:** Semua aman.\n"
            
        report += (
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 **AI Insight:** "
        )
        
        # Basic heuristic insights (Localized)
        if order_count > 10:
             report += "Trafik tinggi hari ini. Pastikan waktu respon chat tetap di bawah 10 menit."
        elif total_rev == 0:
             report += "Belum ada penjualan. Coba cek apakah produk utama Anda masih aktif."
        else:
             report += "Performa stabil. Waktu yang baik untuk memperbarui deskripsi produk."
             
        return report
