import pytest
import asyncio
from pathlib import Path
from database.json_manager import JSONDatabaseManager

@pytest.mark.asyncio
async def test_database_crud(tmp_path):
    data_dir = tmp_path / "data"
    backup_dir = tmp_path / "backups"
    manager = JSONDatabaseManager(data_dir=data_dir, backup_dir=backup_dir)

    # Test set and get
    await manager.set("users", "123456", {"user_id": 123456, "username": "cricketer"})
    user = await manager.get("users", "123456")
    assert user["username"] == "cricketer"

    # Test append
    await manager.append("ball_history", {"ball_id": "b1", "runs": 4})
    balls = await manager.load("ball_history")
    assert len(balls) == 1
    assert balls[0]["runs"] == 4

    # Test backup creation
    backup_path = await manager.create_backup("test")
    assert Path(backup_path).exists()

    # Test in-memory cache hit
    cached_user = await manager.get("users", "123456")
    assert cached_user["username"] == "cricketer"
    assert "users" in manager._cache

    # Test log cap keeps memory & disk bounded
    oversized = [{"ball_id": f"b_{i}"} for i in range(2500)]
    await manager.save("ball_history", oversized)
    loaded_balls = await manager.load("ball_history")
    assert len(loaded_balls) == manager.LOG_CAP_TABLES["ball_history"]


@pytest.mark.asyncio
async def test_external_postgres_adapter(tmp_path):
    from unittest.mock import AsyncMock, MagicMock, patch

    pg_store = {}

    class FakeConn:
        async def execute(self, query, *args):
            if "INSERT INTO bot_tables" in query:
                tname, payload_json = args[0], args[1]
                if "DO UPDATE" in query or tname not in pg_store:
                    pg_store[tname] = payload_json

        async def fetch(self, query):
            return [{"table_name": k} for k in pg_store.keys()]

        async def fetchrow(self, query, tname):
            if tname in pg_store:
                return {"payload": pg_store[tname]}
            return None

    class FakeAcquire:
        def __init__(self, conn):
            self.conn = conn
        async def __aenter__(self):
            return self.conn
        async def __aexit__(self, *args):
            return False

    fake_conn = FakeConn()
    fake_pool = MagicMock()
    fake_pool.acquire.return_value = FakeAcquire(fake_conn)
    fake_pool.close = AsyncMock()

    # Verify password with @ and # and stray brackets is URL-encoded safely
    norm = JSONDatabaseManager._normalize_pg_url("postgres://u:[P@ss#1]@aws-0-sg.pooler.supabase.com:6543/postgres")
    assert norm == "postgresql://u:P%40ss%231@aws-0-sg.pooler.supabase.com:6543/postgres"

    with patch("asyncpg.create_pool", new=AsyncMock(return_value=fake_pool)) as mock_pool:
        mgr = JSONDatabaseManager(
            data_dir=tmp_path / "d",
            backup_dir=tmp_path / "b",
            database_url="postgres://user:pass@db.example.com:5432/jplbot"
        )
        assert await mgr.init_external_db() is True
        assert mgr.using_external_db is True
        # Ensure postgres:// normalized to postgresql:// and SSL enabled for remote host
        dsn_arg = mock_pool.call_args[0][0]
        assert dsn_arg.startswith("postgresql://")
        assert mock_pool.call_args.kwargs.get("ssl") == "require"
        assert mock_pool.call_args.kwargs.get("statement_cache_size") == 0

        await mgr.set("users", "901", {"user_id": 901, "username": "ExternalUser"})
        assert "ExternalUser" in pg_store["users"]

        # Clear RAM cache and reload strictly from mocked Postgres
        mgr._cache.clear()
        reloaded = await mgr.get("users", "901")
        assert reloaded["username"] == "ExternalUser"

        await mgr.close()
        fake_pool.close.assert_awaited_once()
