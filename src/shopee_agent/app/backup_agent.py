import logging
import os
import shutil
from pathlib import Path
from datetime import datetime

logger = logging.getLogger("shopee_agent.backup")

class BackupAgent:
    """Handles automated database backups (Domain logic only)."""
    
    def __init__(self, db_path: str, backup_dir: str = "./data/backups"):
        self.db_path = Path(db_path)
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_sqlite_backup(self) -> Path | None:
        """Creates a timestamped copy of the SQLite database."""
        if not self.db_path.exists():
            logger.error(f"Database file not found: {self.db_path}")
            return None
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"shopee_agent_{timestamp}.db"
        
        try:
            shutil.copy2(self.db_path, backup_file)
            logger.info(f"Backup created: {backup_file}")
            self._cleanup_old_backups()
            return backup_file
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return None

    def _cleanup_old_backups(self, keep=5):
        files = sorted(self.backup_dir.glob("*.db"), key=os.path.getmtime)
        if len(files) > keep:
            for f in files[:-keep]:
                f.unlink()
                logger.info(f"Cleaned up old backup: {f.name}")
