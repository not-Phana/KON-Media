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
async def test_retry_task_and_clear_finished_endpoints():
    from backend.api.router import task_manager
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Non-existent task retry returns 400
        resp = await client.post("/api/tasks/nonexistent_id/retry")
        assert resp.status_code == 400

        # Inject completed and failed tasks into task_manager
        task_manager.tasks["api_test_failed"] = {
            "id": "api_test_failed",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Failed Task",
            "format_id": "18",
            "media_type": "video",
            "ext": "mp4",
            "audio_bitrate": "192",
            "status": "failed",
            "percentage": 10.0,
            "error": "Timeout",
        }
        task_manager.tasks["api_test_done"] = {
            "id": "api_test_done",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "title": "Done Task",
            "status": "completed",
        }

        # Clear finished
        clear_resp = await client.post("/api/tasks/clear-finished")
        assert clear_resp.status_code == 200
        data = clear_resp.json()
        assert "api_test_done" in data["cleared_ids"]
        assert "api_test_failed" in data["cleared_ids"]
        assert data["count"] >= 2


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


@pytest.mark.asyncio
async def test_downloads_endpoint_and_security(tmp_path):
    from backend.config import DOWNLOADS_DIR
    transport = ASGITransport(app=app)

    # Path traversal attempt
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/downloads/..%2F..%2Fwindows%2Fwin.ini")
        assert resp.status_code in (400, 403, 404)

        # Create a real test file in configured downloads directory
        sample_file = DOWNLOADS_DIR / "sample_test_serve.txt"
        DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
        sample_file.write_text("KON Media Download Content")

        try:
            resp = await client.get("/api/downloads/sample_test_serve.txt")
            assert resp.status_code == 200
            assert resp.text == "KON Media Download Content"
            assert "attachment" in resp.headers.get("content-disposition", "")

            # Stream endpoint
            stream_resp = await client.get("/api/stream/sample_test_serve.txt")
            assert stream_resp.status_code == 200
            assert stream_resp.text == "KON Media Download Content"
        finally:
            if sample_file.exists():
                sample_file.unlink()
