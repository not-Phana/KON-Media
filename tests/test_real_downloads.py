"""Automated real-world download verification, socket guard, redirect protection, and cleanup tests."""

import os
import socket
import pytest
from pathlib import Path
from unittest.mock import MagicMock

from backend.engine.media_engine import (
    execute_download,
    MediaEngineError,
    DownloadCancelledError,
)
from backend.security.url_guard import (
    socket_guard_scope,
    validate_media_url,
    SecurityValidationError,
)
from backend.storage.file_manager import cleanup_partial_files


# =====================================================================
# 1. Connect-Time Socket Guard & SSRF Redirect Tests
# =====================================================================

def test_socket_guard_scope_blocks_private_destinations():
    """Verify socket_guard_scope filters loopback, RFC1918, and metadata IP addresses."""
    # Outside the scope, standard loopback address resolution operates
    normal_res = socket.getaddrinfo("127.0.0.1", 80)
    assert len(normal_res) > 0

    # Inside socket_guard_scope, connecting to internal destinations is strictly blocked
    with socket_guard_scope():
        with pytest.raises(socket.gaierror, match="Refusing to connect to non-global"):
            socket.getaddrinfo("127.0.0.1", 80)

        with pytest.raises(socket.gaierror, match="Refusing to connect to non-global"):
            socket.getaddrinfo("169.254.169.254", 80)

        with pytest.raises(socket.gaierror, match="Refusing to connect to non-global"):
            socket.getaddrinfo("10.0.0.1", 80)

    # After exiting the scope, resolution is restored
    restored_res = socket.getaddrinfo("127.0.0.1", 80)
    assert len(restored_res) > 0


def test_redirect_handler_guard_blocks_ssrf_redirects():
    """Verify urllib and yt-dlp redirect handlers intercept redirects to internal destinations."""
    import yt_dlp.networking._urllib as ytdlp_urllib

    handler = ytdlp_urllib.RedirectHandler()
    mock_req = MagicMock()
    mock_req.get_method.return_value = "GET"
    mock_req.headers = {}
    mock_req.origin_req_host = "example.com"
    mock_req.data = None

    # Redirecting to loopback must raise SecurityValidationError
    with pytest.raises(SecurityValidationError, match="restricted local or private range"):
        handler.redirect_request(mock_req, None, 302, "Found", {}, "http://127.0.0.1:8899/admin")

    # Redirecting to cloud metadata must raise SecurityValidationError
    with pytest.raises(SecurityValidationError, match="restricted local or private range"):
        handler.redirect_request(mock_req, None, 302, "Found", {}, "http://169.254.169.254/latest/meta-data")

    # Redirecting to file scheme must be rejected
    with pytest.raises(SecurityValidationError, match="Only HTTP and HTTPS are permitted"):
        handler.redirect_request(mock_req, None, 302, "Found", {}, "file:///etc/passwd")


# =====================================================================
# 2. Partial File Cleanup Verification
# =====================================================================

def test_cleanup_partial_files_removes_intermediate_and_parts(tmp_path):
    """Verify cleanup_partial_files purges both intermediate outputs and .part files for a job."""
    task_id = "test_cleanup_job_123"

    # Create task files that should be cleaned up
    intermediate_media = tmp_path / f"{task_id}.mp4"
    intermediate_media.write_bytes(b"sample intermediate video data")

    partial_file = tmp_path / f"{task_id}.mp4.part"
    partial_file.write_bytes(b"sample partial bytes")

    temp_marker = tmp_path / f"{task_id}.temp"
    temp_marker.write_bytes(b"temp marker")

    # Create an unrelated file that MUST be preserved
    unrelated_file = tmp_path / "other_download.mp4"
    unrelated_file.write_bytes(b"unrelated safe user file")

    assert intermediate_media.exists()
    assert partial_file.exists()
    assert temp_marker.exists()
    assert unrelated_file.exists()

    cleanup_partial_files(task_id, tmp_path)

    # Job files must be deleted
    assert not intermediate_media.exists()
    assert not partial_file.exists()
    assert not temp_marker.exists()

    # Unrelated user file must be preserved
    assert unrelated_file.exists()
    assert unrelated_file.read_bytes() == b"unrelated safe user file"


# =====================================================================
# 3. Real-World Live Network Download Verification
# =====================================================================

@pytest.mark.network
def test_real_live_download_direct_audio(tmp_path):
    """Verify real end-to-end download of an authorized public-domain audio file without FFmpeg."""
    # Archive.org public-domain test MP3 (198 KB)
    test_audio_url = "https://archive.org/download/testmp3testfile/mpthreetest.mp3"
    out_template = str(tmp_path / "real_audio.%(ext)s")

    res = execute_download(
        url=test_audio_url,
        format_selector="bestaudio/best",
        media_type="audio",
        output_path_template=out_template,
        audio_bitrate="original",
        ffmpeg_location=None,
    )

    assert res["success"] is True

    downloaded_file = tmp_path / "real_audio.mp3"
    assert downloaded_file.exists(), "Downloaded audio file was not written to disk"
    file_size = downloaded_file.stat().st_size
    assert file_size > 150_000, f"File size unexpectedly small: {file_size}"

    # Verify audio content: Read MPEG-1 Layer 3 audio frame header (sync word)
    with open(downloaded_file, "rb") as f:
        header_bytes = f.read(4)

    # MPEG-1 Audio Layer III frame sync starts with 0xFF followed by high 3 bits set (e.g. 0xFA, 0xFB)
    is_mpeg_audio = header_bytes[0] == 0xFF and (header_bytes[1] & 0xE0) == 0xE0
    is_id3 = header_bytes[:3] == b"ID3"
    assert is_mpeg_audio or is_id3, f"Downloaded file does not have valid MP3/ID3 header: {header_bytes!r}"
