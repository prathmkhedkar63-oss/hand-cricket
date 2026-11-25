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

        # Overview
        res_overview = await ac.get("/api/overview", headers=headers)
        assert res_overview.status_code == 200
        data = res_overview.json()
        assert "total_players" in data
        assert "total_tournaments" in data

        # Settings
        res_settings = await ac.get("/api/settings", headers=headers)
        assert res_settings.status_code == 200
