"""Unit tests for the KON Media built-in audio playback and preview system."""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from pathlib import Path

from backend.main import app
from backend.engine.audio_service import (
    resolve_audio_stream,
    find_local_downloaded_audio,
    _AUDIO_RESOLVE_CACHE,
)

client = TestClient(app)


def test_resolve_audio_missing_url():
    """Verify endpoint rejects requests without URL."""
    res = client.get("/api/audio/resolve")
    assert res.status_code == 422


def test_resolve_audio_spotify_drm_handling():
    """Verify Spotify tracks report DRM status gracefully without crashing."""
    res = client.get("/api/audio/resolve?url=https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT")
    assert res.status_code == 200
    data = res.json()
    assert data["playable"] is False or data.get("is_drm") is True
    if data["playable"] is False:
        assert data.get("is_drm") is True
        assert "DRM" in data.get("reason", "")


def test_resolve_audio_local_file_detection(tmp_path):
    """Verify that previously downloaded local audio files are served with zero network delay."""
    test_file = tmp_path / "test_song_12345.mp3"
    test_file.write_bytes(b"ID3" + b"\x00" * 100)

    # Mock history store with get_all and get_history
    records = [
        {
            "id": "cand_12345",
            "url": "https://www.youtube.com/watch?v=cand_12345",
            "title": "Local Test Track",
            "artist": "Test Artist",
            "duration": 180,
            "status": "completed",
            "file_path": str(test_file),
        }
    ]
    mock_history = MagicMock()
    mock_history.get_all.return_value = records
    mock_history.get_history.return_value = records

    res = find_local_downloaded_audio(
        url="https://www.youtube.com/watch?v=cand_12345",
        candidate_id="cand_12345",
        downloads_dir=tmp_path,
        history_store=mock_history,
    )

    assert res is not None
    assert res["playable"] is True
    assert res["is_local"] is True
    assert res["source_type"] == "local"
    assert "test_song_12345.mp3" in res["stream_url"]
    assert res["format"] == "mp3"


@pytest.mark.asyncio
async def test_resolve_audio_caching():
    """Verify in-memory caching saves latency on subsequent requests."""
    cache_key = "test_cache_song_xyz"
    _AUDIO_RESOLVE_CACHE[cache_key] = (
        pytest.importorskip("time").time(),
        {
            "playable": True,
            "source_type": "remote",
            "stream_url": "/api/audio/stream?url=https%3A%2F%2Fmock.cdn%2Faudio.m4a",
            "title": "Cached Song",
            "artist": "Cached Artist",
            "duration": 200,
            "format": "m4a",
            "is_local": False,
        },
    )

    res = await resolve_audio_stream(
        url="https://www.youtube.com/watch?v=test_cache_song_xyz",
        candidate_id="test_cache_song_xyz",
    )
    assert res["playable"] is True
    assert res["title"] == "Cached Song"
    assert res["source_type"] == "remote"


def test_audio_stream_proxy_invalid_scheme():
    """Verify proxy endpoint rejects non-http URLs."""
    res = client.get("/api/audio/stream?url=file:///etc/passwd")
    assert res.status_code == 400
