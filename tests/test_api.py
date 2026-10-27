"""Integration tests for FastAPI endpoints and static SPA serving."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app


@pytest.mark.asyncio
async def test_health_check_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert data["service"] == "KON Media"
        assert "engine" in data
        assert data["engine"]["ytdlp_available"] is True
        assert "disk_free_gb" in data


@pytest.mark.asyncio
async def test_analyze_endpoint_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Loopback URL should be rejected with 400
        resp = await client.post("/api/analyze", json={"url": "http://127.0.0.1:8899/exploit"})
        assert resp.status_code == 400
        assert "restricted" in resp.json()["detail"].lower() or "blocked" in resp.json()["detail"].lower()

        # Invalid protocol
        resp = await client.post("/api/analyze", json={"url": "file:///etc/passwd"})
        assert resp.status_code == 400
        assert "protocol" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_download_endpoint_validation():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Loopback URL must be rejected
        resp = await client.post("/api/download", json={"url": "http://localhost:5000"})
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_settings_and_history_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Settings
        resp = await client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "downloads_dir" in data

        # History
        resp = await client.get("/api/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


@pytest.mark.asyncio
async def test_dismiss_task_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Dismiss non-existent task
        resp = await client.post("/api/tasks/nonexistent_id/dismiss")
        assert resp.status_code == 404


@pytest.mark.asyncio
async def test_open_folder_outside_path_rejected():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/api/open-folder", json={"file_path": "C:/Windows/System32/cmd.exe"})
        assert resp.status_code == 400


@pytest.mark.asyncio
async def test_spa_root_serving():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/")
        assert resp.status_code == 200
        assert "<html" in resp.text.lower()
