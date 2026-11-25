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
