"""Unit and integration tests for in-browser universal video player and streaming endpoints."""

import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.engine.video_service import (
    find_local_downloaded_video,
    resolve_video_stream,
    _VIDEO_RESOLVE_CACHE,
)


@pytest.mark.asyncio
async def test_find_local_downloaded_video_none(tmp_path):
    """Verify that when no matching video exists, find_local_downloaded_video returns None."""
    result = find_local_downloaded_video(
        url="https://youtube.com/watch?v=nonexistent",
        candidate_id="nonexistent_id",
        downloads_dir=tmp_path,
        title="Unknown Title",
    )
    assert result is None


@pytest.mark.asyncio
async def test_find_local_downloaded_video_found(tmp_path):
    """Verify that local downloaded video files in downloads_dir are detected and mapped to zero-latency stream."""
    sample_video = tmp_path / "Cyberpunk City 4K.mp4"
    sample_video.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"A" * 1024)

    result = find_local_downloaded_video(
        url="https://youtube.com/watch?v=123",
        candidate_id="123",
        downloads_dir=tmp_path,
        title="Cyberpunk City 4K",
    )
    assert result is not None
    assert result["is_local"] is True
    assert "/api/stream/" in result["stream_url"]
    assert result["resolution"] == "Local Video"


@pytest.mark.asyncio
async def test_resolve_video_endpoint_validation():
    """Verify input validation on /api/video/resolve."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Loopback / SSRF attempt
        resp = await client.get("/api/video/resolve?url=http://127.0.0.1:8899/admin")
        assert resp.status_code == 400
        assert "restricted" in resp.json()["detail"].lower() or "blocked" in resp.json()["detail"].lower()

        # Direct MP4 file URL
        direct_url = "https://example.com/videos/trailer.mp4"
        resp = await client.get(f"/api/video/resolve?url={direct_url}&title=Trailer")
        assert resp.status_code == 200
        data = resp.json()
        assert data["stream_url"] is not None
        assert "Trailer" in data["title"]


@pytest.mark.asyncio
async def test_video_resolve_cache():
    """Verify that video resolve cache caches and reuses resolved video streams."""
    import time
    test_key = "https://example.com/videos/cached_test.mp4"
    _VIDEO_RESOLVE_CACHE[test_key] = (
        time.time(),
        {
            "stream_url": "/api/video/stream?url=https%3A%2F%2Fexample.com%2Fcached.mp4",
            "title": "Cached Video",
            "uploader": "Test Channel",
            "is_local": False,
            "resolution": "1080p",
            "thumbnail": None,
        },
    )

    result = await resolve_video_stream(
        url=test_key,
        title="Cached Video",
    )
    assert result["title"] == "Cached Video"
    assert result["resolution"] == "1080p"
    assert result["is_local"] is False
