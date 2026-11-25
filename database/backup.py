import os
import shutil
import glob
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("backup_manager")

class BackupManager:
    """
    Handles automatic backups, rotational purging, and restoration from corrupted states.
    """
    def __init__(self, data_dir: Path, backup_dir: Path, max_copies: int = 10):
        self.data_dir = data_dir
        self.backup_dir = backup_dir
        self.max_copies = max_copies
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, label: str = "") -> str:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        tag = f"_{label}" if label else ""
        snapshot_name = f"backup_{timestamp}{tag}"
        snapshot_dir = self.backup_dir / snapshot_name
        snapshot_dir.mkdir(parents=True, exist_ok=True)

        for json_file in self.data_dir.glob("*.json"):
            shutil.copy2(json_file, snapshot_dir / json_file.name)

        logger.info(f"Database backup created: {snapshot_name}")
        self._rotate_backups()
        return str(snapshot_dir)

    def restore_latest_backup(self, target_filename: str = None) -> bool:
        """
        Restores a specific file or all files from the latest valid backup.
        """
        snapshots = sorted(list(self.backup_dir.glob("backup_*")), key=os.path.getmtime, reverse=True)
        if not snapshots:
            logger.warning("No backups available for restoration.")
            return False

        latest_snapshot = snapshots[0]
        logger.info(f"Restoring from backup snapshot: {latest_snapshot.name}")

        if target_filename:
            source = latest_snapshot / target_filename
            if source.exists():
                shutil.copy2(source, self.data_dir / target_filename)
                logger.info(f"Successfully restored {target_filename} from backup.")
                return True
            else:
                logger.error(f"{target_filename} not found in latest backup.")
                return False
        else:
            for source in latest_snapshot.glob("*.json"):
                shutil.copy2(source, self.data_dir / source.name)
            logger.info("Successfully restored all files from latest backup.")
            return True

    def _rotate_backups(self):
        snapshots = sorted(list(self.backup_dir.glob("backup_*")), key=os.path.getmtime)
        while len(snapshots) > self.max_copies:
            oldest = snapshots.pop(0)
            try:
                shutil.rmtree(oldest)
                logger.info(f"Rotated and deleted old backup: {oldest.name}")
            except Exception as e:
                logger.error(f"Failed to remove old backup {oldest}: {e}")
