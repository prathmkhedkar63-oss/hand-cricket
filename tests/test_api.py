import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from config.settings import settings

@pytest.mark.asyncio
async def test_health_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/health")
        assert res.status_code == 200
        assert res.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_admin_auth_and_overview():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # Invalid login
        res = await ac.post("/api/auth/login", json={"username": "wrong", "password": "bad"})
        assert res.status_code == 401

        # Valid login
        res = await ac.post("/api/auth/login", json={
            "username": settings.ADMIN_USERNAME,
            "password": settings.ADMIN_PASSWORD
        })
        assert res.status_code == 200
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Overview includes live storage & bot transport status
        res_overview = await ac.get("/api/overview", headers=headers)
        assert res_overview.status_code == 200
        data = res_overview.json()
        assert "total_players" in data
        assert "total_tournaments" in data
        assert data["storage_mode"] in ("json", "postgresql")
        assert "storage_label" in data
        assert data["bot_mode"] in ("polling", "webhook")

        # Settings
        res_settings = await ac.get("/api/settings", headers=headers)
        assert res_settings.status_code == 200


@pytest.mark.asyncio
async def test_webhook_broadcast_and_backup_download():
    import json
    from unittest.mock import AsyncMock, MagicMock
    from config.settings import Settings
    from database.json_manager import db

    # 1. Webhook URL resolution for Render vs explicit polling override
    s_auto = Settings(USE_WEBHOOK="auto", BOT_TOKEN="123:abc")
    import os
    old_render = os.environ.get("RENDER_EXTERNAL_URL")
    try:
        os.environ["RENDER_EXTERNAL_URL"] = "https://hand-cricket-xzwd.onrender.com"
        assert s_auto.resolve_webhook_url() == "https://hand-cricket-xzwd.onrender.com/telegram/webhook"
        s_off = Settings(USE_WEBHOOK="false", BOT_TOKEN="123:abc")
        assert s_off.resolve_webhook_url() is None
    finally:
        if old_render is None:
            os.environ.pop("RENDER_EXTERNAL_URL", None)
        else:
            os.environ["RENDER_EXTERNAL_URL"] = old_render

    # 2. Webhook secret validation & Update dispatch
    mock_bot = AsyncMock()
    mock_dp = MagicMock()
    mock_dp.feed_update = AsyncMock()
    old_bot, old_dp, old_secret = app.state.bot, app.state.dp, app.state.webhook_secret
    app.state.bot = mock_bot
    app.state.dp = mock_dp
    app.state.webhook_secret = "secret-xyz"

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            bad_wh = await ac.post(settings.WEBHOOK_PATH, json={"update_id": 1}, headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"})
            assert bad_wh.status_code == 403

            good_wh = await ac.post(
                settings.WEBHOOK_PATH,
                json={"update_id": 42},
                headers={"X-Telegram-Bot-Api-Secret-Token": "secret-xyz"},
            )
            assert good_wh.status_code == 200
            assert good_wh.json()["ok"] is True
            mock_dp.feed_update.assert_awaited_once()

            # 3. Admin Login -> Broadcast & JSON Backup Download
            login_res = await ac.post("/api/auth/login", json={
                "username": settings.ADMIN_USERNAME,
                "password": settings.ADMIN_PASSWORD
            })
            headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

            users = await db.load("users")
            users["990011"] = {"user_id": 990011, "username": "bcastuser", "private_chat_id": 990011, "is_banned": False}
            await db.save("users", users)
            sys_s = await db.load("settings")
            old_groups = list(sys_s.get("known_groups", []))
            sys_s["known_groups"] = [-1009911]
            await db.save("settings", sys_s)

            bc_res = await ac.post("/api/broadcast", json={"message": "IPL Finals Tonight!", "target": "all"}, headers=headers)
            assert bc_res.status_code == 200
            bc_data = bc_res.json()
            assert bc_data["dm_sent"] >= 1
            assert bc_data["group_sent"] >= 1

            dl_res = await ac.get("/api/system/backup/download", headers=headers)
            assert dl_res.status_code == 200
            assert "jplbot_backup_" in dl_res.headers.get("content-disposition", "")
            bundle = json.loads(dl_res.text)
            assert "tables" in bundle and "statistics" in bundle["tables"]
    finally:
        app.state.bot = old_bot
        app.state.dp = old_dp
        app.state.webhook_secret = old_secret
        users = await db.load("users")
        users.pop("990011", None)
        await db.save("users", users)
        sys_s = await db.load("settings")
        if "old_groups" in locals():
            sys_s["known_groups"] = old_groups
            await db.save("settings", sys_s)
