from datetime import datetime, timedelta
from typing import TypedDict

from shopee_agent.persistence.repositories import OrderRepository, ReturnDisputeRepository


class KPIReport(TypedDict):
    revenue: float
    order_count: int
    dispute_count: int
    dispute_rate: float
    growth_revenue: float  # vs previous period
    shop_rankings: list[tuple[str, float]] = None


class AnalyticsAgent:
    def __init__(self, order_repo: OrderRepository, dispute_repo: ReturnDisputeRepository) -> None:
        self.order_repo = order_repo
        self.dispute_repo = dispute_repo

    def get_monthly_dashboard(self, shop_id: str | None = None) -> KPIReport:
        now = datetime.now()
        this_month_start = datetime(now.year, now.month, 1)
        next_month_start = (this_month_start + timedelta(days=32)).replace(day=1)
        
        last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)
        
        # Current Metrics
        revenue = self.order_repo.get_revenue_sum(shop_id, this_month_start, next_month_start)
        orders = self.order_repo.get_order_count(shop_id, this_month_start, next_month_start)
        disputes = self.dispute_repo.get_dispute_count(shop_id, this_month_start, next_month_start)
        
        # Previous Month for Growth
        prev_revenue = self.order_repo.get_revenue_sum(shop_id, last_month_start, this_month_start)
        growth = ((revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0.0
        
        dispute_rate = (disputes / orders * 100) if orders > 0 else 0.0
        
        return {
            "revenue": revenue,
            "order_count": orders,
            "dispute_count": disputes,
            "dispute_rate": dispute_rate,
            "growth_revenue": growth,
        }

    def get_kpi_report_for_range(self, days: int, shop_id: str | None = None) -> KPIReport:
        """Get KPI report for the last X days."""
        now = datetime.now()
        start_date = now - timedelta(days=days)
        prev_start_date = start_date - timedelta(days=days)
        
        revenue = self.order_repo.get_revenue_sum(shop_id, start_date, now)
        orders = self.order_repo.get_order_count(shop_id, start_date, now)
        disputes = self.dispute_repo.get_dispute_count(shop_id, start_date, now)
        
        prev_revenue = self.order_repo.get_revenue_sum(shop_id, prev_start_date, start_date)
        growth = ((revenue - prev_revenue) / prev_revenue * 100) if prev_revenue > 0 else 0.0
        
        dispute_rate = (disputes / orders * 100) if orders > 0 else 0.0
        
        # Shop Leaderboard (Global only)
        rankings = []
        if not shop_id:
            rankings = self.order_repo.get_shop_performance(start_date, now)
        
        return {
            "revenue": revenue,
            "order_count": orders,
            "dispute_count": disputes,
            "dispute_rate": dispute_rate,
            "growth_revenue": growth,
            "shop_rankings": rankings,
        }

    def format_dashboard_text(self, report: KPIReport, shop_id: str | None = None) -> str:
        title = f"📊 *Dashboard Global*" if not shop_id else f"📊 *Dashboard:* `{shop_id}`"
        
        growth_icon = "📈" if report["growth_revenue"] >= 0 else "📉"
        
        text = (
            f"{title}\n"
            f"━━━━━━━━━━━━━━━\n"
            f"💰 Omzet: `Rp {report['revenue']:,.0f}`\n"
            f"{growth_icon} Pertumbuhan: `{report['growth_revenue']:+.1f}%`\n"
            f"📦 Pesanan: `{report['order_count']}`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"⚖️ Komplain: `{report['dispute_count']}`\n"
            f"🚨 Rate: `{report['dispute_rate']:.2f}%`\n"
            f"━━━━━━━━━━━━━━━\n"
            f"Status: *PERFORMA BAIK*" if report["dispute_rate"] < 2 else "Status: *KRITIS*\n\n"
        )
        
        if report.get("shop_rankings"):
            text += "🏆 *Top Shops (Berdasarkan Omzet):*\n"
            medals = ["🥇", "🥈", "🥉", "🎖️", "🎖️"]
            for i, (sid, rev) in enumerate(report["shop_rankings"]):
                medal = medals[i] if i < len(medals) else "•"
                text += f"{medal} `{sid}`: `Rp {rev:,.0f}`\n"
            text += "\n"
            
        return text

    def get_daily_briefing(self, shop_id: str | None = None) -> str:
        """Aggregate stats for the last 24 hours for an executive briefing."""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        
        revenue = self.order_repo.get_revenue_sum(shop_id, yesterday, now)
        orders = self.order_repo.get_order_count(shop_id, yesterday, now)
        disputes = self.dispute_repo.get_dispute_count(shop_id, yesterday, now)
        
        title = "🌅 **Laporan Pagi**" if 5 <= now.hour <= 11 else "📊 **Laporan Toko**"
        
        text = (
            f"{title}\n"
            f"_{now.strftime('%A, %d %B %Y')}_\n\n"
            f"📌 **Performa (24 Jam Terakhir):**\n"
            f"💰 Omzet: `Rp {revenue:,.0f}`\n"
            f"📦 Pesanan Baru: `{orders}`\n"
            f"⚖️ Komplain Aktif: `{disputes}`\n\n"
            f"✅ **Daftar Tugas:**\n"
        )
        
        if orders > 0:
            text += f"- Kirim `{orders}` pesanan tertunda.\n"
        if disputes > 0:
            text += f"- Tinjau `{disputes}` permintaan pengembalian.\n"
        if orders == 0 and disputes == 0:
            text += "- Semua operasional lancar. Kerja bagus!\n"
            
        text += "\n🚀 *Semoga hari Anda produktif!*"
        return text
