"""Tests for Media Engine workflow, formatting, and cancellation."""

import threading
import pytest
from unittest.mock import MagicMock, patch
from backend.engine.media_engine import (
    format_duration,
    extract_media_info,
    execute_download,
    DownloadCancelledError,
    MediaEngineError,
)


def test_format_duration():
    assert format_duration(None) == "Unknown"
    assert format_duration(0) == "Unknown"
    assert format_duration(45) == "00:45"
    assert format_duration(125) == "02:05"
    assert format_duration(3665) == "01:01:05"


def test_extract_media_info_format_grouping():
    mock_info = {
        "title": "Creative Commons Nature Video",
        "uploader": "Earth Explorer",
        "duration": 180,
        "thumbnail": "https://example.com/thumb.jpg",
        "extractor": "Generic",
        "webpage_url": "https://example.com/nature",
        "formats": [
            {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a", "tbr": 500, "filesize": 5000000},
            {"format_id": "22", "height": 720, "vcodec": "avc1", "acodec": "mp4a", "tbr": 1500, "filesize": 15000000},
            {"format_id": "137", "height": 1080, "vcodec": "avc1", "acodec": "none", "tbr": 3000, "filesize": 30000000},
            {"format_id": "audio_only", "height": None, "vcodec": "none", "acodec": "mp4a", "tbr": 128},
        ],
    }

    with patch("backend.engine.media_engine.yt_dlp.YoutubeDL") as MockYDL:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = mock_info
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.__exit__.return_value = None
        MockYDL.return_value = mock_instance

        result = extract_media_info("https://example.com/nature")
        assert result["title"] == "Creative Commons Nature Video"
        assert result["uploader"] == "Earth Explorer"
        assert result["duration_formatted"] == "03:00"
        assert len(result["video_formats"]) == 3
        # Ensure highest resolution is first
        assert result["video_formats"][0]["height"] == 1080
        # Verify video-only format merged with bestaudio
        assert result["video_formats"][0]["format_id"] == "137+bestaudio/best"
        assert result["video_formats"][1]["height"] == 720
        assert result["video_formats"][2]["height"] == 360
        # Verify audio options
        assert len(result["audio_formats"]) == 3
        assert result["audio_formats"][0]["bitrate"] == "320k"


def test_extract_media_info_direct_stream_fallback():
    mock_direct_info = {
        "title": "sample_video",
        "uploader": None,
        "duration": None,
        "thumbnail": None,
        "extractor": "Generic",
        "webpage_url": "https://example.com/sample.mp4",
        "ext": "mp4",
        "formats": [
            {"format_id": "mp4", "height": None, "vcodec": None, "acodec": None}
        ],
    }

    with patch("backend.engine.media_engine.yt_dlp.YoutubeDL") as MockYDL:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = mock_direct_info
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.__exit__.return_value = None
        MockYDL.return_value = mock_instance

        result = extract_media_info("https://example.com/sample.mp4")
        assert len(result["video_formats"]) == 1
        assert result["video_formats"][0]["format_id"] == "best"
        assert "Original Quality" in result["video_formats"][0]["label"]


def test_download_cancellation():
    abort_event = threading.Event()
    abort_event.set()  # Pre-abort

    with pytest.raises(DownloadCancelledError):
        execute_download(
            url="https://example.com/video",
            format_selector="best",
            media_type="video",
            output_path_template="dummy.%(ext)s",
            abort_event=abort_event,
        )


def test_missing_ffmpeg_audio_error():
    with patch("shutil.which", return_value=None):
        with pytest.raises(MediaEngineError, match=r"FFmpeg is not (available|installed)"):
            execute_download(
                url="https://example.com/audio",
                format_selector="bestaudio/best",
                media_type="audio",
                output_path_template="dummy.%(ext)s",
            )
