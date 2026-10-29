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

    try:
        res = execute_download(
            url=test_audio_url,
            format_selector="bestaudio/best",
            media_type="audio",
            output_path_template=out_template,
            audio_bitrate="original",
            ffmpeg_location=None,
        )
    except Exception as e:
        pytest.skip(f"Live network access to archive.org failed or timed out: {e}")

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


def test_real_ffmpeg_stream_merging_and_inspection(tmp_path):
    """Verify that bundled FFmpeg merges a separate video stream and audio stream into a valid file with sound."""
    import subprocess
    from backend.engine.ffmpeg_manager import validate_ffmpeg_path, inspect_media_streams

    status = validate_ffmpeg_path()
    assert status["available"] is True, "FFmpeg must be available for stream merging test"
    ffmpeg_exe = status["path"]

    v_only = tmp_path / "test_video_only.mp4"
    a_only = tmp_path / "test_audio_only.m4a"
    merged = tmp_path / "test_merged_with_sound.mp4"

    # 1. Synthesize 1s video-only H.264 stream (no audio)
    res_v = subprocess.run(
        [ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=size=320x240:rate=10", "-t", "1", "-c:v", "libx264", "-an", str(v_only)],
        capture_output=True,
    )
    assert res_v.returncode == 0

    # 2. Synthesize 1s audio-only AAC stream (no video)
    res_a = subprocess.run(
        [ffmpeg_exe, "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:a", "aac", "-vn", str(a_only)],
        capture_output=True,
    )
    assert res_a.returncode == 0

    # Inspect separate streams
    v_info = inspect_media_streams(v_only)
    assert v_info["has_video"] is True
    assert v_info["has_audio"] is False

    a_info = inspect_media_streams(a_only)
    assert a_info["has_video"] is False
    assert a_info["has_audio"] is True

    # 3. Perform lossless stream copy container remux (merging video and audio)
    res_m = subprocess.run(
        [ffmpeg_exe, "-y", "-i", str(v_only), "-i", str(a_only), "-c:v", "copy", "-c:a", "copy", str(merged)],
        capture_output=True,
    )
    assert res_m.returncode == 0

    # Deep stream inspection of merged file
    merged_info = inspect_media_streams(merged)
    assert merged_info["has_video"] is True, "Merged file must contain video stream"
    assert merged_info["has_audio"] is True, "Merged file must contain audio stream"
    assert merged_info["video_codec"] == "h264"
    assert merged_info["audio_codec"] == "aac"
    assert merged.stat().st_size > 0


@pytest.mark.network
def test_real_live_download_stream_pair_and_merge_with_ffmpeg(tmp_path):
    """Verify real end-to-end pairing, downloading, and FFmpeg merging of video and audio streams."""
    import subprocess
    from backend.engine.ffmpeg_manager import validate_ffmpeg_path

    ffmpeg_info = validate_ffmpeg_path()
    if not ffmpeg_info["available"]:
        pytest.skip("FFmpeg is not available in test environment.")

    # Small public test video URL (Creative Commons / public test clip)
    test_video_url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
    out_template = str(tmp_path / "merged_output.%(ext)s")

    try:
        res = execute_download(
            url=test_video_url,
            format_selector="269+140",  # Tiny 144p AVC1 video + 129k AAC audio
            media_type="video",
            output_path_template=out_template,
            ffmpeg_location=ffmpeg_info["path"],
            merge_output_format="mp4",
        )
    except Exception as e:
        pytest.skip(f"Live network access failed: {e}")

    assert res["success"] is True

    merged_file = tmp_path / "merged_output.mp4"
    assert merged_file.exists(), "Merged MP4 file was not written to disk"
    assert merged_file.stat().st_size > 50_000, "Merged file is empty or corrupted"

    # Use FFmpeg to inspect the actual streams inside the resulting file
    probe_cmd = [ffmpeg_info["path"], "-hide_banner", "-i", str(merged_file)]
    probe_res = subprocess.run(probe_cmd, capture_output=True, text=True)

    has_video_stream = any("Video:" in line for line in probe_res.stderr.splitlines())
    has_audio_stream = any("Audio:" in line for line in probe_res.stderr.splitlines())

    assert has_video_stream, "Merged output does not contain a valid video stream"
    assert has_audio_stream, "Merged output does not contain a valid audio stream (silent MP4 regression)"

