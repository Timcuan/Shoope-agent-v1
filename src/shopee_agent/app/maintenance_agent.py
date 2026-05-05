import logging
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from shopee_agent.persistence.repositories import ShopTokenRepository

logger = logging.getLogger("shopee_agent.maintenance")

class MaintenanceAgent:
    """Ensures long-term system stability and cleanliness."""
    
    def __init__(self, session, settings):
        self.session = session
        self.settings = settings

    async def perform_scheduled_maintenance(self):
        """Runs routine cleanup and health checks."""
        logger.info("Starting scheduled maintenance...")
        
        # 1. Cleanup Old Media/Labels (Retention: 7 days)
        self._cleanup_dir("./data/media", days=7)
        self._cleanup_dir("./data/exports", days=30)
        
        # 2. Prune Activity Logs (Retention: 90 days)
        self._prune_db_logs(days=90)
        
        # 3. Check Token Expiry
        expiring_shops = self.check_token_health()
        
        # 3. Check Disk Space
        disk_warning = self._check_disk_space()
        
        return {
            "expiring_shops": expiring_shops,
            "disk_warning": disk_warning
        }

    def _prune_db_logs(self, days: int):
        """Prunes old activity logs from the database."""
        from shopee_agent.persistence.models import ActivityLogRecord
        from sqlalchemy import delete
        
        cutoff = datetime.now() - timedelta(days=days)
        stmt = delete(ActivityLogRecord).where(ActivityLogRecord.created_at < cutoff)
        self.session.execute(stmt)
        self.session.commit()
        logger.info(f"Pruned activity logs older than {days} days")

    def check_token_health(self) -> list[str]:
        """Returns list of shop IDs whose tokens expire soon."""
        repo = ShopTokenRepository(self.session)
        tokens = repo.get_all_tokens()
        
        warning_list = []
        for t in tokens:
            days_left = (t.expiry - datetime.now()).days
            if days_left < 7:
                warning_list.append(f"{t.shop_id} ({days_left} hari lagi)")
        
        return warning_list

    def _cleanup_dir(self, dir_path: str, days: int):
        """Deletes files older than N days."""
        path = Path(dir_path)
        if not path.exists(): return
        
        cutoff = datetime.now() - timedelta(days=days)
        count = 0
        for f in path.iterdir():
            if f.is_file() and datetime.fromtimestamp(f.stat().st_mtime) < cutoff:
                f.unlink()
                count += 1
        logger.info(f"Cleaned up {count} files from {dir_path}")

    def _check_disk_space(self) -> str | None:
        """Alerts if disk space is low."""
        total, used, free = shutil.disk_usage("/")
        free_gb = free // (2**30)
        if free_gb < 2: # Warning if less than 2GB
            return f"⚠️ Sisa disk rendah: {free_gb} GB"
        return None
