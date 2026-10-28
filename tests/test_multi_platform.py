"""Phase 3 Tests: Multi-platform extractors, Spotify oEmbed metadata, and alternative audio matching."""

import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.engine.media_engine import (
    extract_media_info,
    fetch_spotify_oembed,
    find_spotify_match,
    MediaEngineError,
)
from backend.engine.ffmpeg_manager import validate_ffmpeg_path


@pytest.mark.asyncio
async def test_spotify_oembed_metadata_extraction():
    """Verify fetch_spotify_oembed fetches live metadata or handles offline gracefully."""
    track_url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
    data = fetch_spotify_oembed(track_url)
    assert isinstance(data, dict)
    if data:
        assert data.get("title") == "Never Gonna Give You Up"
        assert "image-cdn" in data.get("thumbnail", "")


@pytest.mark.asyncio
async def test_spotify_match_api_endpoint():
    """Verify POST /api/spotify/match endpoint accepts Spotify URLs and returns matched public media."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Mock find_spotify_match to test API contract quickly and reliably
        mock_match_result = {
            "title": "Rick Astley - Never Gonna Give You Up (Official Video)",
            "uploader": "Rick Astley",
            "duration": 213,
            "duration_formatted": "03:33",
            "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
            "extractor": "Youtube",
            "webpage_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "video_formats": [{"format_id": "best", "label": "1080p MP4", "requires_ffmpeg": False}],
            "audio_formats": [{"format_id": "bestaudio/best", "label": "MP3 High (320 kbps)", "bitrate": "320k", "requires_ffmpeg": False}],
            "ffmpeg_available": True,
            "is_alternative_match": True,
            "original_spotify_title": "Never Gonna Give You Up",
            "original_spotify_url": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
        }

        with patch("backend.api.router.find_spotify_match", return_value=mock_match_result):
            res = await client.post(
                "/api/spotify/match",
                json={
                    "url": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
                    "title": "Never Gonna Give You Up",
                },
            )
            assert res.status_code == 200
            data = res.json()
            assert data["is_alternative_match"] is True
            assert data["original_spotify_title"] == "Never Gonna Give You Up"
            assert "dQw4w9WgXcQ" in data["webpage_url"]


@pytest.mark.asyncio
async def test_spotify_match_invalid_source_rejected():
    """Verify non-Spotify URLs are rejected by the Spotify match endpoint."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/spotify/match",
            json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
        )
        assert res.status_code == 400
        assert "not a recognized Spotify source" in res.json()["detail"]


def test_youtube_direct_audio_format_inclusion():
    """Verify YouTube analysis includes direct audio options without requiring FFmpeg."""
    mock_yt_info = {
        "title": "Test YouTube Video",
        "uploader": "Test Channel",
        "duration": 120,
        "thumbnail": "https://example.com/thumb.jpg",
        "extractor": "Youtube",
        "webpage_url": "https://www.youtube.com/watch?v=test1234",
        "formats": [
            {"format_id": "137", "height": 1080, "vcodec": "avc1", "acodec": "none", "tbr": 3000},
            {"format_id": "140", "height": None, "vcodec": "none", "acodec": "mp4a.40.2", "ext": "m4a", "tbr": 128},
            {"format_id": "251", "height": None, "vcodec": "none", "acodec": "opus", "ext": "webm", "tbr": 160},
        ],
    }

    with patch("backend.engine.media_engine.yt_dlp.YoutubeDL") as MockYDL:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = mock_yt_info
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.__exit__.return_value = None
        MockYDL.return_value = mock_instance

        info = extract_media_info("https://www.youtube.com/watch?v=test1234")
        # Video option exists
        assert len(info["video_formats"]) == 1
        # Direct audio option is present and requires_ffmpeg is False
        audio_direct = next((a for a in info["audio_formats"] if a.get("bitrate") == "original"), None)
        assert audio_direct is not None
        assert audio_direct["requires_ffmpeg"] is False
        assert audio_direct["ext"] == "m4a"


def test_bundled_ffmpeg_detection():
    """Verify bundled FFmpeg from imageio-ffmpeg is recognized and reports valid status."""
    status = validate_ffmpeg_path(None)
    assert status["available"] is True
    assert status["source"] in ("bundled", "path", "custom")
    assert status["version"] is not None
    assert "ffmpeg version" in status["version"].lower()
