from datetime import datetime, timedelta
from typing import TypedDict

from shopee_agent.persistence.repositories import ShopTokenRepository, ShopTokenData


class ShopHealth(TypedDict):
    shop_id: str
    status: str
    days_left: int
    needs_reauth: bool


class HealthAgent:
    """Proactively monitors shop tokens and system status."""

    def __init__(self, token_repo: ShopTokenRepository) -> None:
        self.token_repo = token_repo

    def get_global_health(self) -> list[ShopHealth]:
        tokens = self.token_repo.get_all_tokens()
        results = []
        now = datetime.now()
        
        for t in tokens:
            days_left = (t.expires_at - now).days
            status = "HEALTHY"
            needs_reauth = False
            
            if days_left <= 0:
                status = "EXPIRED"
                needs_reauth = True
            elif days_left <= 3:
                status = "CRITICAL"
                needs_reauth = True
            elif days_left <= 7:
                status = "WARNING"
            
            results.append({
                "shop_id": t.shop_id,
                "status": status,
                "days_left": max(0, days_left),
                "needs_reauth": needs_reauth
            })
        return results

    def get_shop_health(self, shop_id: str) -> ShopHealth:
        token = self.token_repo.get_token(shop_id)
        if not token:
            return {"shop_id": shop_id, "status": "UNKNOWN", "days_left": 0, "needs_reauth": True}
        
        now = datetime.now()
        days_left = (token.expires_at - now).days
        status = "HEALTHY"
        needs_reauth = False
        
        if days_left <= 0:
            status = "EXPIRED"
            needs_reauth = True
        elif days_left <= 3:
            status = "CRITICAL"
            needs_reauth = True
        elif days_left <= 7:
            status = "WARNING"
            
        return {
            "shop_id": shop_id,
            "status": status,
            "days_left": max(0, days_left),
            "needs_reauth": needs_reauth
        }

    def format_health_report(self, health_list: list[ShopHealth]) -> str:
        if not health_list:
            return "⚠️ *Belum ada toko yang terhubung.* Gunakan `/link` untuk memulai."
            
        text = "🛰️ *Laporan Kesehatan Toko*\n\n"
        for h in health_list:
            icon = "✅"
            status_text = "SEHAT"
            if h["status"] == "CRITICAL": 
                icon = "🚨"
                status_text = "KRITIS"
            elif h["status"] == "WARNING": 
                icon = "🟡"
                status_text = "PERINGATAN"
            elif h["status"] == "EXPIRED": 
                icon = "❌"
                status_text = "KEDALUWARSA"
            
            text += (
                f"{icon} `{h['shop_id']}`: *{status_text}*\n"
                f"   └ Berakhir dalam: `{h['days_left']} hari`\n"
            )
            if h["needs_reauth"]:
                text += "   └ ⚠️ *Tindakan:* Harap `/link` ulang toko ini.\n"
            text += "\n"
        return text
