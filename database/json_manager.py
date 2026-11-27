import json
import os
import shutil
import tempfile
import asyncio
import logging
import time
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

    def __init__(self, data_dir: Optional[Path] = None, backup_dir: Optional[Path] = None, database_url: Optional[str] = None):
        self.data_dir = data_dir or settings.DATA_DIR
        self.backup_dir = backup_dir or settings.BACKUP_DIR
        # When tests pass an explicit tmp data_dir without database_url, keep them local JSON isolated
        if database_url is not None:
            self.database_url: Optional[str] = database_url.strip() or None
        elif data_dir is not None:
            self.database_url = None
        else:
            raw_url = settings.DATABASE_URL
            self.database_url = raw_url.strip() if isinstance(raw_url, str) and raw_url.strip() else None

        self._pg_pool = None
        self._pg_init_lock: Optional[asyncio.Lock] = None
        self._pg_failed: bool = False
        self._cache: Dict[str, Any] = {}
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_manager = BackupManager(self.data_dir, self.backup_dir, settings.MAX_BACKUP_COPIES)
        self.initialize_tables()

    @property
    def using_external_db(self) -> bool:
        return bool(self.database_url and not self._pg_failed)

    @staticmethod
    def _normalize_pg_url(url: str) -> str:
        from urllib.parse import quote, unquote
        clean = url.strip().strip('"').strip("'")
        if clean.startswith("postgres://"):
            clean = "postgresql://" + clean[len("postgres://"):]
        if "://" in clean:
            scheme, rest = clean.split("://", 1)
            if "@" in rest:
                userinfo, host_part = rest.rsplit("@", 1)
                if ":" in userinfo:
                    user, raw_pw = userinfo.split(":", 1)
                    if raw_pw.startswith("[") and raw_pw.endswith("]") and raw_pw != "[YOUR-PASSWORD]":
                        raw_pw = raw_pw[1:-1]
                    encoded_pw = quote(unquote(raw_pw), safe="")
                    clean = f"{scheme}://{user}:{encoded_pw}@{host_part}"
        return clean

    async def _get_pg_pool(self):
        if not self.database_url or self._pg_failed:
            return None
        if self._pg_pool is not None:
            return self._pg_pool

        if self._pg_init_lock is None:
            self._pg_init_lock = asyncio.Lock()

        async with self._pg_init_lock:
            if self._pg_pool is not None:
                return self._pg_pool
            safe_host = "unknown"
            try:
                import asyncpg
                dsn = self._normalize_pg_url(self.database_url)
                if "@" in dsn:
                    safe_host = dsn.rsplit("@", 1)[1].split("/", 1)[0].split("?", 1)[0]
                if "[YOUR-PASSWORD]" in dsn:
                    raise ValueError("DATABASE_URL still contains the placeholder [YOUR-PASSWORD]")
                connect_kwargs: Dict[str, Any] = {
                    "min_size": 1,
                    "max_size": 5,
                    "statement_cache_size": 0,  # Compatible with Supabase/PgBouncer transaction poolers
                }
                if "localhost" not in safe_host and "127.0.0.1" not in safe_host and "sslmode=" not in dsn:
                    connect_kwargs["ssl"] = "require"
                pool = await asyncpg.create_pool(dsn, **connect_kwargs)
                async with pool.acquire() as conn:
                    await conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS bot_tables (
                            table_name TEXT PRIMARY KEY,
                            payload JSONB NOT NULL,
                            updated_at DOUBLE PRECISION NOT NULL
                        )
                        """
                    )
                self._pg_pool = pool
                logger.info(f"Connected to external PostgreSQL database ({safe_host}, bot_tables ready).")
                return self._pg_pool
            except Exception as e:
                if safe_host.startswith("db.") and ".supabase.co" in safe_host:
                    logger.error(
                        f"External PostgreSQL DNS/network error for '{safe_host}': {e}. "
                        f"Supabase Direct (db.*.supabase.co) is IPv6-only; use Session/Transaction Pooler (*.pooler.supabase.com) in Render DATABASE_URL."
                    )
                else:
                    logger.error(f"External PostgreSQL connection failed for '{safe_host}', falling back to local JSON: {e}")
                self._pg_failed = True
                return None

    async def init_external_db(self) -> bool:
        """Connects to PostgreSQL (if DATABASE_URL is configured) and seeds any missing tables."""
        pool = await self._get_pg_pool()
        if not pool:
            return False
        try:
            async with pool.acquire() as conn:
                rows = await conn.fetch("SELECT table_name FROM bot_tables")
                existing = {r["table_name"] for r in rows}
                now = time.time()
                for table in self.DEFAULT_SCHEMAS:
                    if table not in existing:
                        seed_data = self.load_sync(table)
                        await conn.execute(
                            """
                            INSERT INTO bot_tables (table_name, payload, updated_at)
                            VALUES ($1, $2::jsonb, $3)
                            ON CONFLICT (table_name) DO NOTHING
                            """,
                            table,
                            json.dumps(seed_data, ensure_ascii=False),
                            now,
                        )
            return True
        except Exception as e:
            logger.error(f"Failed seeding external DB tables: {e}")
            return False

    async def close(self):
        """Cleanly closes external DB connection pool on shutdown."""
        if self._pg_pool is not None:
            try:
                await self._pg_pool.close()
            except Exception:
                pass
            self._pg_pool = None

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
        """Asynchronously loads table data using in-memory cache with external DB / disk fallback."""
        if table in self._cache:
            return self._cache[table]

        async_lock = locker.get_async_lock(table)
        async with async_lock:
            if table in self._cache:
                return self._cache[table]

            pool = await self._get_pg_pool()
            if pool is not None:
                try:
                    async with pool.acquire() as conn:
                        row = await conn.fetchrow("SELECT payload FROM bot_tables WHERE table_name = $1", table)
                        if row is not None:
                            raw = row["payload"]
                            data = json.loads(raw) if isinstance(raw, str) else raw
                            self._cache[table] = data
                            return data
                        # Missing table row: seed from local JSON or default schema
                        data = self.load_sync(table)
                        await conn.execute(
                            """
                            INSERT INTO bot_tables (table_name, payload, updated_at)
                            VALUES ($1, $2::jsonb, $3)
                            ON CONFLICT (table_name) DO NOTHING
                            """,
                            table,
                            json.dumps(data, ensure_ascii=False),
                            time.time(),
                        )
                        self._cache[table] = data
                        return data
                except Exception as e:
                    logger.warning(f"External DB load failed for '{table}', falling back to JSON: {e}")

            loop = asyncio.get_running_loop()
            data = await loop.run_in_executor(None, self.load_sync, table)
            self._cache[table] = data
            return data

    async def save(self, table: str, data: Any):
        """Asynchronously writes table data to external DB (or local atomic JSON) and updates cache."""
        if table in self.LOG_CAP_TABLES and isinstance(data, list):
            cap = self.LOG_CAP_TABLES[table]
            if len(data) > cap:
                data = data[-cap:]

        self._cache[table] = data
        async_lock = locker.get_async_lock(table)
        async with async_lock:
            pool = await self._get_pg_pool()
            if pool is not None:
                try:
                    payload_json = json.dumps(data, ensure_ascii=False)
                    async with pool.acquire() as conn:
                        await conn.execute(
                            """
                            INSERT INTO bot_tables (table_name, payload, updated_at)
                            VALUES ($1, $2::jsonb, $3)
                            ON CONFLICT (table_name) DO UPDATE
                            SET payload = EXCLUDED.payload, updated_at = EXCLUDED.updated_at
                            """,
                            table,
                            payload_json,
                            time.time(),
                        )
                    return
                except Exception as e:
                    logger.warning(f"External DB save failed for '{table}', falling back to JSON: {e}")

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
