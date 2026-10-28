"""Tests for Smart Stream Pairing, Automatic Merging, and Format Accuracy."""

import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.engine.media_engine import (
    validate_stream_pairing,
    extract_media_info,
    execute_download,
    MediaEngineError,
)
from backend.engine.ffmpeg_manager import (
    inspect_media_streams,
    validate_ffmpeg_path,
)
from backend.storage.storage import HistoryStore, SettingsStore
from backend.tasks.task_manager import TaskManager


def test_validate_stream_pairing_video_with_audio_direct():
    """A video stream that already contains audio should be accepted as a direct download without merging."""
    video_stream = {
        "format_id": "22",
        "label": "720p (AVC1, MP4) [Audio + Video]",
        "height": 720,
        "vcodec": "avc1.64001F",
        "acodec": "mp4a.40.2",
        "ext": "mp4",
        "has_video": True,
        "has_audio": True,
    }
    result = validate_stream_pairing(video_stream, None, ffmpeg_available=True)
    assert result["valid"] is True
    assert result["is_direct"] is True
    assert result["requires_ffmpeg"] is False
    assert result["recommended_container"] == "mp4"
    assert result["format_selector"] == "22"
    assert "already includes integrated audio" in result["reason"]


def test_validate_stream_pairing_video_only_requires_audio():
    """A video-only stream without an audio selection must be flagged as needing audio."""
    video_stream = {
        "format_id": "137",
        "label": "1080p (AVC1, MP4) [Video Only]",
        "height": 1080,
        "vcodec": "avc1.640028",
        "acodec": "none",
        "ext": "mp4",
        "has_video": True,
        "has_audio": False,
    }
    result = validate_stream_pairing(video_stream, None, ffmpeg_available=True)
    assert result["valid"] is False
    assert result["requires_ffmpeg"] is True
    assert "video-only" in result["reason"]


def test_validate_stream_pairing_incompatible_two_videos():
    """Pairing two video streams together must be rejected as invalid."""
    video_1 = {
        "format_id": "137",
        "has_video": True,
        "has_audio": False,
        "ext": "mp4",
    }
    video_2 = {
        "format_id": "248",
        "has_video": True,
        "has_audio": False,
        "ext": "webm",
    }
    result = validate_stream_pairing(video_1, video_2, ffmpeg_available=True)
    assert result["valid"] is False
    assert "Cannot pair two video streams" in result["reason"]


def test_validate_stream_pairing_webm_streams():
    """Compatible WebM video and audio streams should recommend a WebM container."""
    video_stream = {
        "format_id": "248",
        "height": 1080,
        "vcodec": "vp9",
        "acodec": "none",
        "ext": "webm",
        "has_video": True,
        "has_audio": False,
    }
    audio_stream = {
        "format_id": "251",
        "acodec": "opus",
        "ext": "webm",
        "has_video": False,
        "has_audio": True,
    }
    result = validate_stream_pairing(video_stream, audio_stream, ffmpeg_available=True)
    assert result["valid"] is True
    assert result["is_direct"] is False
    assert result["requires_ffmpeg"] is True
    assert result["recommended_container"] == "webm"
    assert result["format_selector"] == "248+251"
    assert "WebM" in result["reason"]


def test_validate_stream_pairing_mp4_streams():
    """Compatible MP4 video and M4A audio streams should recommend an MP4 container."""
    video_stream = {
        "format_id": "137",
        "height": 1080,
        "vcodec": "avc1.640028",
        "acodec": "none",
        "ext": "mp4",
        "has_video": True,
        "has_audio": False,
    }
    audio_stream = {
        "format_id": "140",
        "acodec": "mp4a.40.2",
        "ext": "m4a",
        "has_video": False,
        "has_audio": True,
    }
    result = validate_stream_pairing(video_stream, audio_stream, ffmpeg_available=True)
    assert result["valid"] is True
    assert result["is_direct"] is False
    assert result["requires_ffmpeg"] is True
    assert result["recommended_container"] == "mp4"
    assert result["format_selector"] == "137+140"
    assert "MP4" in result["reason"]


def test_validate_stream_pairing_cross_codec_recommends_mkv():
    """Cross-codec stream pairing (e.g. VP9 WebM video + AAC M4A audio) recommends MKV."""
    video_stream = {
        "format_id": "248",
        "height": 1080,
        "vcodec": "vp9",
        "acodec": "none",
        "ext": "webm",
        "has_video": True,
        "has_audio": False,
    }
    audio_stream = {
        "format_id": "140",
        "acodec": "mp4a.40.2",
        "ext": "m4a",
        "has_video": False,
        "has_audio": True,
    }
    result = validate_stream_pairing(video_stream, audio_stream, ffmpeg_available=True)
    assert result["valid"] is True
    assert result["recommended_container"] == "mkv"
    assert result["format_selector"] == "248+140"


def test_extract_media_info_populates_detailed_streams():
    """extract_media_info must return video_streams and audio_streams for the pairing UI."""
    mock_info = {
        "title": "Pairing Test Media",
        "uploader": "Test Channel",
        "duration": 60,
        "thumbnail": "https://example.com/thumb.jpg",
        "extractor": "Youtube",
        "webpage_url": "https://example.com/watch?v=pair123",
        "formats": [
            {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a", "ext": "mp4", "tbr": 400},
            {"format_id": "137", "height": 1080, "vcodec": "avc1", "acodec": "none", "ext": "mp4", "tbr": 3000},
            {"format_id": "248", "height": 1080, "vcodec": "vp9", "acodec": "none", "ext": "webm", "tbr": 2800},
            {"format_id": "140", "height": None, "vcodec": "none", "acodec": "mp4a.40.2", "ext": "m4a", "abr": 128},
            {"format_id": "251", "height": None, "vcodec": "none", "acodec": "opus", "ext": "webm", "abr": 160},
        ],
    }

    with patch("backend.engine.media_engine.yt_dlp.YoutubeDL") as MockYDL:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = mock_info
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.__exit__.return_value = None
        MockYDL.return_value = mock_instance

        info = extract_media_info("https://example.com/watch?v=pair123")

        # video_streams list has both video-only and combined streams
        assert len(info["video_streams"]) == 3
        # Format 18 is marked as combined
        fmt18 = next(v for v in info["video_streams"] if v["format_id"] == "18")
        assert fmt18["has_audio"] is True
        assert fmt18["stream_type"] == "combined"

        # Format 137 is marked as video_only
        fmt137 = next(v for v in info["video_streams"] if v["format_id"] == "137")
        assert fmt137["has_audio"] is False
        assert fmt137["stream_type"] == "video_only"

        # audio_streams has the 2 standalone audio streams
        assert len(info["audio_streams"]) == 2
        fmt251 = next(a for a in info["audio_streams"] if a["format_id"] == "251")
        assert fmt251["ext"] == "webm"
        assert fmt251["has_audio"] is True
        assert fmt251["has_video"] is False


@pytest.mark.asyncio
async def test_validate_pairing_api_endpoint():
    """Verify POST /api/validate-pairing endpoint evaluates stream pairs correctly."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/validate-pairing",
            json={
                "video_stream": {"format_id": "137", "vcodec": "avc1", "ext": "mp4", "has_video": True, "has_audio": False},
                "audio_stream": {"format_id": "140", "acodec": "mp4a", "ext": "m4a", "has_video": False, "has_audio": True},
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["recommended_container"] == "mp4"
        assert data["format_selector"] == "137+140"


@pytest.mark.asyncio
async def test_start_download_with_merged_streams_queued():
    """Verify POST /api/download with merge_streams queues format_id as video_id+audio_id."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/download",
            json={
                "url": "https://example.com/watch?v=test_merge",
                "title": "Merged Video Test",
                "merge_streams": True,
                "video_format_id": "137",
                "audio_format_id": "140",
                "merge_output_format": "mp4",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert "task_id" in data
        assert data["status"] == "queued"


def test_missing_ffmpeg_blocks_merging():
    """execute_download must raise MediaEngineError if separate streams are requested without FFmpeg."""
    with patch("backend.engine.media_engine.validate_ffmpeg_path", return_value={"available": False, "path": None}):
        with pytest.raises(MediaEngineError, match="merging separate video and audio streams with FFmpeg"):
            execute_download(
                url="https://example.com/video",
                format_selector="137+140",
                media_type="video",
                output_path_template="dummy_out",
            )


def test_inspect_media_streams_fallback_when_ffmpeg_unavailable(tmp_path):
    """inspect_media_streams gracefully inspects file extension when FFmpeg is not available."""
    test_file = tmp_path / "sample.mp4"
    test_file.write_bytes(b"\x00" * 100)

    with patch("backend.engine.ffmpeg_manager.validate_ffmpeg_path", return_value={"available": False, "path": None}):
        result = inspect_media_streams(test_file)
        assert result["has_video"] is True
        assert result["container"] == "mp4"


def test_inspect_media_streams_detects_real_streams(tmp_path):
    """inspect_media_streams accurately parses FFmpeg stderr stream lines."""
    fake_video = tmp_path / "valid_clip.mp4"
    fake_video.write_bytes(b"data")

    mock_ffmpeg_output = (
        "Input #0, mov,mp4,m4a,3gp,3g2,mj2, from 'valid_clip.mp4':\n"
        "  Duration: 00:01:30.00, start: 0.000000, bitrate: 1200 kb/s\n"
        "  Stream #0:0[0x1](und): Video: h264 (High) (avc1 / 0x31637661), yuv420p, 1920x1080, 24 fps\n"
        "  Stream #0:1[0x2](und): Audio: aac (LC) (mp4a / 0x6134706D), 48000 Hz, stereo, fltp, 128 kb/s\n"
    )

    with patch("backend.engine.ffmpeg_manager.validate_ffmpeg_path", return_value={"available": True, "path": "mock_ffmpeg"}):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stderr=mock_ffmpeg_output, stdout="")
            result = inspect_media_streams(fake_video)
            assert result["inspected"] is True
            assert result["has_video"] is True
            assert result["has_audio"] is True
            assert result["video_codec"] == "h264"
            assert result["audio_codec"] == "aac"
            assert len(result["streams"]) == 2
