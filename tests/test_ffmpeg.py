"""Tests for FFmpeg detection, custom path configuration, validation, and workflow integration."""

import subprocess
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.engine.ffmpeg_manager import validate_ffmpeg_path
from backend.engine.media_engine import (
    extract_media_info,
    execute_download,
    MediaEngineError,
)
from backend.storage.storage import SettingsStore


def test_ffmpeg_auto_detection_found():
    """Verify validate_ffmpeg_path discovers system binary when custom_path is empty."""
    with patch("shutil.which", return_value="C:\\tools\\ffmpeg.exe"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["C:\\tools\\ffmpeg.exe", "-version"],
                returncode=0,
                stdout="ffmpeg version 7.1-full_build Copyright (c) 2000-2024\nbuilt with gcc...",
                stderr="",
            )
            res = validate_ffmpeg_path("")
            assert res["available"] is True
            assert res["source"] == "path"
            assert res["path"] == "C:\\tools\\ffmpeg.exe"
            assert "ffmpeg version 7.1" in res["version"]
            assert res["error"] is None


def test_ffmpeg_auto_detection_not_found():
    """Verify validate_ffmpeg_path reports clear error when not on system PATH and no bundled binary."""
    with patch("shutil.which", return_value=None), patch("backend.engine.ffmpeg_manager._find_bundled_ffmpeg", return_value=None):
        res = validate_ffmpeg_path(None)
        assert res["available"] is False
        assert res["source"] == "none"
        assert res["path"] is None
        assert "not found in system PATH" in res["error"]


def test_ffmpeg_auto_detection_bundled():
    """Verify validate_ffmpeg_path discovers bundled package binary when not on system PATH."""
    with patch("shutil.which", return_value=None), patch("backend.engine.ffmpeg_manager._find_bundled_ffmpeg", return_value="E:\\tools\\bundled_ffmpeg.exe"):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = subprocess.CompletedProcess(
                args=["E:\\tools\\bundled_ffmpeg.exe", "-version"],
                returncode=0,
                stdout="ffmpeg version 7.1-bundled\n",
                stderr="",
            )
            res = validate_ffmpeg_path(None)
            assert res["available"] is True
            assert res["source"] == "bundled"
            assert res["path"] == "E:\\tools\\bundled_ffmpeg.exe"
            assert res["version"] == "ffmpeg version 7.1-bundled"
            assert res["error"] is None


def test_ffmpeg_custom_path_nonexistent():
    """Verify non-existent custom path is rejected gracefully."""
    fake_path = "E:\\Code\\fake_dir\\bin\\ffmpeg.exe"
    res = validate_ffmpeg_path(fake_path)
    assert res["available"] is False
    assert res["source"] == "custom"
    assert "does not exist" in res["error"]


def test_ffmpeg_custom_path_dir_missing_exe(tmp_path):
    """Verify directory without ffmpeg.exe is flagged."""
    res = validate_ffmpeg_path(str(tmp_path))
    assert res["available"] is False
    assert res["source"] == "custom"
    assert "no 'ffmpeg.exe' or 'ffmpeg' was found" in res["error"]


def test_ffmpeg_custom_path_dir_with_exe(tmp_path):
    """Verify directory containing ffmpeg.exe resolves properly."""
    fake_exe = tmp_path / "ffmpeg.exe"
    fake_exe.write_text("binary placeholder")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[str(fake_exe), "-version"],
            returncode=0,
            stdout="ffmpeg version 6.0\nbuilt...",
            stderr="",
        )
        res = validate_ffmpeg_path(str(tmp_path))
        assert res["available"] is True
        assert res["source"] == "custom"
        assert res["path"] == str(fake_exe)
        assert res["version"] == "ffmpeg version 6.0"


def test_ffmpeg_custom_path_direct_exe(tmp_path):
    """Verify direct path to ffmpeg.exe is validated."""
    fake_exe = tmp_path / "custom_ffmpeg.exe"
    fake_exe.write_text("binary placeholder")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[str(fake_exe), "-version"],
            returncode=0,
            stdout="ffmpeg version 5.1-custom\n",
            stderr="",
        )
        res = validate_ffmpeg_path(str(fake_exe))
        assert res["available"] is True
        assert res["source"] == "custom"
        assert res["path"] == str(fake_exe)
        assert res["version"] == "ffmpeg version 5.1-custom"


def test_ffmpeg_execution_timeout(tmp_path):
    """Verify timeout when executing binary is handled."""
    fake_exe = tmp_path / "ffmpeg.exe"
    fake_exe.write_text("binary placeholder")

    with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd=[str(fake_exe)], timeout=5)):
        res = validate_ffmpeg_path(str(fake_exe))
        assert res["available"] is False
        assert "timed out" in res["error"].lower()


def test_ffmpeg_execution_permission_error(tmp_path):
    """Verify permission denied error is captured gracefully."""
    fake_exe = tmp_path / "ffmpeg.exe"
    fake_exe.write_text("binary placeholder")

    with patch("subprocess.run", side_effect=PermissionError("Access denied")):
        res = validate_ffmpeg_path(str(fake_exe))
        assert res["available"] is False
        assert "permission denied" in res["error"].lower()


def test_ffmpeg_execution_nonzero_exit(tmp_path):
    """Verify non-zero returncode results in available=False."""
    fake_exe = tmp_path / "ffmpeg.exe"
    fake_exe.write_text("binary placeholder")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=[str(fake_exe), "-version"],
            returncode=127,
            stdout="",
            stderr="Missing DLL dependencies",
        )
        res = validate_ffmpeg_path(str(fake_exe))
        assert res["available"] is False
        assert "Missing DLL dependencies" in res["error"]


def test_extract_media_info_format_requires_ffmpeg_tagging():
    """Verify video formats correctly differentiate between direct and FFmpeg-required formats."""
    mock_info = {
        "title": "Dual Stream Media",
        "uploader": "Tester",
        "duration": 60,
        "thumbnail": None,
        "extractor": "Test",
        "webpage_url": "https://example.com/stream",
        "formats": [
            # Direct pre-merged format (acodec present)
            {"format_id": "18", "height": 360, "vcodec": "avc1", "acodec": "mp4a", "tbr": 400},
            # DASH video-only format (acodec is none) -> requires FFmpeg merge
            {"format_id": "137", "height": 1080, "vcodec": "avc1", "acodec": "none", "tbr": 2500},
        ],
    }

    with patch("backend.engine.media_engine.yt_dlp.YoutubeDL") as MockYDL:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = mock_info
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.__exit__.return_value = None
        MockYDL.return_value = mock_instance

        # Case 1: FFmpeg unavailable
        with patch("backend.engine.media_engine.validate_ffmpeg_path", return_value={"available": False, "path": None}):
            res = extract_media_info("https://example.com/stream")
            formats = res["video_formats"]
            # 1080p is DASH video-only
            fmt_1080 = next(f for f in formats if f["height"] == 1080)
            assert fmt_1080["requires_ffmpeg"] is True
            assert "+" in fmt_1080["format_id"]

            # 360p is pre-merged direct
            fmt_360 = next(f for f in formats if f["height"] == 360)
            assert fmt_360["requires_ffmpeg"] is False
            assert "(Direct)" in fmt_360["label"]
            assert fmt_360["format_id"] == "18"

            # All audio extractions require FFmpeg
            for af in res["audio_formats"]:
                assert af["requires_ffmpeg"] is True


def test_execute_download_ffmpeg_location_passed():
    """Verify configured FFmpeg location is passed to yt-dlp ydl_opts['ffmpeg_location']."""
    captured_opts = {}

    def mock_ydl_init(opts):
        captured_opts.update(opts)
        mock_ydl = MagicMock()
        mock_ydl.download.return_value = 0
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.__exit__.return_value = None
        return mock_ydl

    custom_ffmpeg = "E:\\tools\\ffmpeg\\bin\\ffmpeg.exe"
    with patch("backend.engine.media_engine.validate_ffmpeg_path", return_value={"available": True, "path": custom_ffmpeg}):
        with patch("backend.engine.media_engine.yt_dlp.YoutubeDL", side_effect=mock_ydl_init):
            execute_download(
                url="https://example.com/video",
                format_selector="137+bestaudio/best",
                media_type="video",
                output_path_template="dummy.%(ext)s",
                ffmpeg_location=custom_ffmpeg,
            )
            assert captured_opts.get("ffmpeg_location") == custom_ffmpeg
            assert captured_opts.get("merge_output_format") == "mp4"


def test_execute_download_blocks_merge_when_missing_ffmpeg():
    """Verify attempting multi-stream merge when FFmpeg is missing raises friendly MediaEngineError."""
    with patch("backend.engine.media_engine.validate_ffmpeg_path", return_value={"available": False, "path": None}):
        with pytest.raises(MediaEngineError, match="merging separate video and audio streams with FFmpeg"):
            execute_download(
                url="https://example.com/video",
                format_selector="137+bestaudio/best",
                media_type="video",
                output_path_template="dummy.%(ext)s",
                ffmpeg_location=None,
            )


@pytest.mark.asyncio
async def test_api_validate_ffmpeg_endpoint():
    """Verify the /api/settings/validate-ffmpeg endpoint returns validation response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Invalid / missing path
        resp = await client.post("/api/settings/validate-ffmpeg", json={"ffmpeg_path": "E:\\nonexistent_dir\\ffmpeg.exe"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["available"] is False
        assert "does not exist" in data["error"]

        # Mocked valid custom path
        with patch("backend.api.router.validate_ffmpeg_path", return_value={
            "available": True,
            "path": "E:\\tools\\ffmpeg.exe",
            "version": "ffmpeg version 7.1",
            "source": "custom",
            "error": None,
        }):
            resp = await client.post("/api/settings/validate-ffmpeg", json={"ffmpeg_path": "E:\\tools\\ffmpeg.exe"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["available"] is True
            assert data["path"] == "E:\\tools\\ffmpeg.exe"
            assert data["version"] == "ffmpeg version 7.1"


@pytest.mark.asyncio
async def test_api_health_includes_ffmpeg_details():
    """Verify /api/health returns engine FFmpeg status fields."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "engine" in data
        assert "ffmpeg_available" in data["engine"]
        assert "ffmpeg_path" in data["engine"]
        assert "ffmpeg_version" in data["engine"]
        assert "ffmpeg_source" in data["engine"]


def test_settings_store_handles_ffmpeg_path(tmp_path):
    """Verify SettingsStore loads, stores, and updates ffmpeg_path setting."""
    store = SettingsStore(state_dir=tmp_path)

    # Initial default should contain empty ffmpeg_path
    settings = store.get_settings()
    assert "ffmpeg_path" in settings
    assert settings["ffmpeg_path"] == ""

    # Update with custom path
    updated = store.update_settings({"ffmpeg_path": "E:\\tools\\ffmpeg\\bin\\ffmpeg.exe"})
    assert updated["ffmpeg_path"] == "E:\\tools\\ffmpeg\\bin\\ffmpeg.exe"

    # Reload from disk to verify atomic persistence
    reloaded_store = SettingsStore(state_dir=tmp_path)
    assert reloaded_store.get_settings()["ffmpeg_path"] == "E:\\tools\\ffmpeg\\bin\\ffmpeg.exe"
