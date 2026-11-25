import json
import os
import shutil
import tempfile
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from config.settings import settings
from database.file_locker import locker
from database.backup import BackupManager
from database.validators import DataValidator, ValidationError

logger = logging.getLogger("json_manager")

class JSONDatabaseManager:
    """
    Robust JSON Database Manager:
    - Dedicated /data directory
    - Atomic writes using temp files and atomic rename
    - Async & thread locking to prevent concurrent write conflicts
    - Automatic creation of 15 required JSON files
    - Backup and automatic recovery from corrupted JSON files
    """

    DEFAULT_SCHEMAS: Dict[str, Any] = {
        "users": {},           # user_id -> user dict
        "statistics": {},      # user_id -> stats dict
        "tournaments": {},     # tournament_id -> tournament dict
        "participants": [],    # list of participant dicts
        "teams": {},           # tournament_id -> {"Team A": [...], "Team B": [...]}
        "matches": {},         # match_id -> match dict
        "innings": {},         # innings_id -> innings dict
        "ball_history": [],    # list of ball event dicts
        "hosts": {},           # user_id -> host metadata
        "admins": {},          # user_id -> admin metadata
        "leaderboard": {
            "global_wins": [],
            "highest_runs": [],
            "highest_score": [],
            "best_win_percentage": [],
            "longest_streak": [],
            "weekly": [],
            "monthly": []
        },
        "notifications": [],   # list of notification dicts
        "reports": [],         # list of report / dispute dicts
        "audit_logs": [],      # list of audit records
        "settings": {
            "innings_limit": settings.DEFAULT_INNINGS_LIMIT,
            "wickets_limit": settings.DEFAULT_WICKETS_LIMIT,
            "max_balls": settings.DEFAULT_MAX_BALLS,
            "solo_countdown_seconds": settings.SOLO_TOURNAMENT_COUNTDOWN_SECONDS,
            "matchmaking_enabled": True,
            "dispute_auto_pause": True,
            "bot_enabled": True
        }
    }

    LOG_CAP_TABLES: Dict[str, int] = {
        "ball_history": 2000,
        "notifications": 500,
        "audit_logs": 1000
    }

    def __init__(self, data_dir: Optional[Path] = None, backup_dir: Optional[Path] = None):
        self.data_dir = data_dir or settings.DATA_DIR
        self.backup_dir = backup_dir or settings.BACKUP_DIR
        self._cache: Dict[str, Any] = {}
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_manager = BackupManager(self.data_dir, self.backup_dir, settings.MAX_BACKUP_COPIES)
        self.initialize_tables()

    def get_file_path(self, table: str) -> Path:
        return self.data_dir / f"{table}.json"

    def initialize_tables(self):
        """Creates any missing JSON files with their default schema."""
        for table, default_content in self.DEFAULT_SCHEMAS.items():
            file_path = self.get_file_path(table)
            if not file_path.exists():
                self._atomic_write_sync(file_path, default_content)
                logger.info(f"Initialized table file: {file_path.name}")

    def _atomic_write_sync(self, file_path: Path, data: Any):
        """Synchronous atomic file write using temp file and rename."""
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile("w", dir=self.data_dir, delete=False, encoding="utf-8") as tf:
                temp_file = Path(tf.name)
                json.dump(data, tf, indent=2, ensure_ascii=False)
                tf.flush()
                os.fsync(tf.fileno())
            os.replace(temp_file, file_path)
        except Exception as e:
            if temp_file and temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass
            logger.error(f"Atomic write error for {file_path}: {e}")
            raise e

    def load_sync(self, table: str) -> Any:
        """Synchronously loads table content with recovery fallback."""
        file_path = self.get_file_path(table)
        lock = locker.get_thread_lock(table)
        with lock:
            if not file_path.exists():
                default_data = self.DEFAULT_SCHEMAS.get(table, {})
                self._atomic_write_sync(file_path, default_data)
                return default_data

            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                logger.error(f"Corruption detected in {table}.json: {e}. Attempting backup recovery...")
                restored = self.backup_manager.restore_latest_backup(f"{table}.json")
                if restored:
                    with open(file_path, "r", encoding="utf-8") as f:
                        return json.load(f)
                else:
                    logger.warning(f"Recovery failed for {table}.json. Reinitializing with default schema.")
                    default_data = self.DEFAULT_SCHEMAS.get(table, {})
                    self._atomic_write_sync(file_path, default_data)
                    return default_data

    def save_sync(self, table: str, data: Any):
        """Synchronously saves table data atomically with thread lock."""
        file_path = self.get_file_path(table)
        lock = locker.get_thread_lock(table)
        with lock:
            self._atomic_write_sync(file_path, data)

    async def load(self, table: str) -> Any:
        """Asynchronously loads table data using in-memory cache with disk fallback."""
        if table in self._cache:
            return self._cache[table]

        async_lock = locker.get_async_lock(table)
        async with async_lock:
            if table in self._cache:
                return self._cache[table]
            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, self.load_sync, table)
            self._cache[table] = data
            return data

    async def save(self, table: str, data: Any):
        """Asynchronously writes table data atomically and updates cache (capping unbounded logs)."""
        if table in self.LOG_CAP_TABLES and isinstance(data, list):
            cap = self.LOG_CAP_TABLES[table]
            if len(data) > cap:
                data = data[-cap:]

        self._cache[table] = data
        async_lock = locker.get_async_lock(table)
        async with async_lock:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self.save_sync, table, data)

    # Helper operations
    async def get(self, table: str, key: str, default: Any = None) -> Any:
        data = await self.load(table)
        if isinstance(data, dict):
            return data.get(str(key), default)
        return default

    async def set(self, table: str, key: str, value: Any):
        data = await self.load(table)
        if not isinstance(data, dict):
            raise ValueError(f"Table {table} is a list, not a dictionary.")
        data[str(key)] = value
        await self.save(table, data)

    async def delete(self, table: str, key: str) -> bool:
        data = await self.load(table)
        if isinstance(data, dict) and str(key) in data:
            del data[str(key)]
            await self.save(table, data)
            return True
        return False

    async def append(self, table: str, item: Any):
        data = await self.load(table)
        if not isinstance(data, list):
            raise ValueError(f"Table {table} is a dictionary, not a list.")
        data.append(item)
        await self.save(table, data)

    async def filter_list(self, table: str, predicate) -> List[Any]:
        data = await self.load(table)
        if not isinstance(data, list):
            return []
        return [item for item in data if predicate(item)]

    async def create_backup(self, label: str = "") -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.backup_manager.create_backup, label)

# Global singleton database manager instance
db = JSONDatabaseManager()
