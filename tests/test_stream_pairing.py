"""Tests for smart stream pairing, automatic merging, format accuracy, and FFmpeg remuxing."""

import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.engine.media_engine import (
    clean_codec_name,
    determine_stream_kind,
    validate_stream_pair,
    extract_media_info,
    execute_download,
    MediaEngineError,
)
from backend.tasks.task_manager import TaskManager
from backend.storage.storage import HistoryStore, SettingsStore


def test_clean_codec_name():
    """Verify raw codec strings are normalized into human-readable labels."""
    assert clean_codec_name("avc1.64002A") == "H.264 (AVC)"
    assert clean_codec_name("h264") == "H.264 (AVC)"
    assert clean_codec_name("vp09.00.41.08") == "VP9"
    assert clean_codec_name("vp9") == "VP9"
    assert clean_codec_name("av01.0.08M.08") == "AV1"
    assert clean_codec_name("hvc1.1.6.L93.B0") == "H.265 (HEVC)"
    assert clean_codec_name("mp4a.40.2") == "AAC"
    assert clean_codec_name("opus") == "Opus"
    assert clean_codec_name("vorbis") == "Vorbis"
    assert clean_codec_name("mp3") == "MP3"
    assert clean_codec_name("none") is None
    assert clean_codec_name(None) is None


def test_determine_stream_kind():
    """Verify streams are accurately classified as video_only, audio_only, combined, or unknown."""
    assert determine_stream_kind("avc1", "mp4a") == "combined"
    assert determine_stream_kind("avc1", "none") == "video_only"
    assert determine_stream_kind("avc1", None) == "video_only"
    assert determine_stream_kind("none", "mp4a") == "audio_only"
    assert determine_stream_kind(None, "opus") == "audio_only"
    assert determine_stream_kind("none", "none") == "unknown"
    assert determine_stream_kind(None, None) == "unknown"


def test_validate_stream_pair_compatible_mp4():
    """Pairing H.264/AVC video in MP4 and AAC audio in M4A produces lossless MP4 copy."""
    video = {
        "format_id": "137",
        "ext": "mp4",
        "vcodec": "avc1.64002a",
        "acodec": "none",
        "stream_kind": "video_only",
    }
    audio = {
        "format_id": "140",
        "ext": "m4a",
        "vcodec": "none",
        "acodec": "mp4a.40.2",
        "stream_kind": "audio_only",
    }
    res = validate_stream_pair(video, audio)
    assert res["compatible"] is True
    assert res["requires_merge"] is True
    assert res["target_container"] == "mp4"
    assert res["lossless"] is True
    assert res["format_selector"] == "137+140"
    assert "lossless stream copy" in res["message"]


def test_validate_stream_pair_compatible_webm():
    """Pairing VP9 video in WebM and Opus audio in WebM produces lossless WebM copy."""
    video = {
        "format_id": "303",
        "ext": "webm",
        "vcodec": "vp09.00.41.08",
        "acodec": "none",
        "stream_kind": "video_only",
    }
    audio = {
        "format_id": "251",
        "ext": "webm",
        "vcodec": "none",
        "acodec": "opus",
        "stream_kind": "audio_only",
    }
    res = validate_stream_pair(video, audio)
    assert res["compatible"] is True
    assert res["requires_merge"] is True
    assert res["target_container"] == "webm"
    assert res["lossless"] is True
    assert res["format_selector"] == "303+251"
    assert "lossless stream copy" in res["message"]


def test_validate_stream_pair_cross_container():
    """Pairing VP9 WebM video with AAC MP4 audio results in MP4 remux target."""
    video = {
        "format_id": "303",
        "ext": "webm",
        "vcodec": "vp9",
        "acodec": "none",
        "stream_kind": "video_only",
    }
    audio = {
        "format_id": "140",
        "ext": "m4a",
        "vcodec": "none",
        "acodec": "mp4a.40.2",
        "stream_kind": "audio_only",
    }
    res = validate_stream_pair(video, audio)
    assert res["compatible"] is True
    assert res["requires_merge"] is True
    assert res["target_container"] == "mp4"
    assert res["lossless"] is False
    assert res["format_selector"] == "303+140"


def test_validate_stream_pair_incompatible_two_videos():
    """Pairing two video streams is rejected with an informative error."""
    video1 = {"format_id": "137", "stream_kind": "video_only", "vcodec": "avc1", "acodec": "none"}
    video2 = {"format_id": "303", "stream_kind": "video_only", "vcodec": "vp9", "acodec": "none"}
    res = validate_stream_pair(video1, video2)
    assert res["compatible"] is False
    assert "Pairing two video streams is not an audio-merging solution" in res["error"]


def test_validate_stream_pair_incompatible_two_audios():
    """Selecting an audio stream under video category is rejected."""
    audio1 = {"format_id": "140", "stream_kind": "audio_only", "vcodec": "none", "acodec": "mp4a"}
    audio2 = {"format_id": "251", "stream_kind": "audio_only", "vcodec": "none", "acodec": "opus"}
    res = validate_stream_pair(audio1, audio2)
    assert res["compatible"] is False
    assert "audio-only" in res["error"]


def test_validate_stream_pair_combined_video_standalone():
    """Selecting a combined stream alone indicates direct download without merging."""
    combined = {
        "format_id": "22",
        "ext": "mp4",
        "vcodec": "avc1",
        "acodec": "mp4a",
        "stream_kind": "combined",
    }
    res = validate_stream_pair(combined, None)
    assert res["compatible"] is True
    assert res["requires_merge"] is False
    assert res["is_combined_direct"] is True
    assert res["target_container"] == "mp4"


def test_format_accuracy_and_stream_manifest_extraction():
    """Verify that video-only formats are tagged requires_ffmpeg=True, and streams are classified."""
    mock_info = {
        "title": "Stream Manifest Test",
        "uploader": "Test Uploader",
        "duration": 90,
        "thumbnail": "https://example.com/thumb.jpg",
        "extractor": "Generic",
        "webpage_url": "https://example.com/test",
        "formats": [
            # Video only MP4 (acodec is None)
            {"format_id": "137", "height": 1080, "ext": "mp4", "vcodec": "avc1.64002a", "acodec": None, "tbr": 3000},
            # Audio only WebM (Opus)
            {"format_id": "251", "height": None, "ext": "webm", "vcodec": "none", "acodec": "opus", "tbr": 160},
            # Audio only M4A (AAC)
            {"format_id": "140", "height": None, "ext": "m4a", "vcodec": "none", "acodec": "mp4a.40.2", "tbr": 128},
        ],
    }

    with patch("backend.engine.media_engine.yt_dlp.YoutubeDL") as MockYDL:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = mock_info
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.__exit__.return_value = None
        MockYDL.return_value = mock_instance

        info = extract_media_info("https://example.com/test")

        # 1. 1080p must require FFmpeg to merge with audio (NOT marked direct)
        assert len(info["video_formats"]) == 1
        vf = info["video_formats"][0]
        assert vf["height"] == 1080
        assert vf["requires_ffmpeg"] is True
        assert vf["format_id"] == "137+bestaudio/best"
        assert "(Direct)" not in vf["label"]

        # 2. Native audio stream options must NOT claim to be MP3
        direct_audios = [a for a in info["audio_formats"] if a.get("bitrate") == "original"]
        assert len(direct_audios) >= 1
        for da in direct_audios:
            assert da["ext"] in ("m4a", "webm")
            # If WebM, label must not say MP3
            if da["ext"] == "webm":
                assert "WEBM" in da["label"] or "Opus" in da["label"]
            elif da["ext"] == "m4a":
                assert "M4A" in da["label"] or "AAC" in da["label"]

        # 3. Available individual streams manifest must be populated
        assert "available_streams" in info
        assert "available_video_streams" in info
        assert "available_audio_streams" in info
        assert len(info["available_video_streams"]) == 1
        assert len(info["available_audio_streams"]) == 2
        assert info["available_video_streams"][0]["stream_kind"] == "video_only"
        assert info["available_audio_streams"][0]["stream_kind"] == "audio_only"


def test_execute_download_merging_blocks_when_missing_ffmpeg():
    """Attempting multi-stream merging without FFmpeg raises a clear user-facing error."""
    with patch("backend.engine.media_engine.validate_ffmpeg_path") as mock_validate:
        mock_validate.return_value = {"available": False, "path": None, "version": None, "error": "Not installed"}
        with pytest.raises(MediaEngineError) as exc_info:
            execute_download(
                url="https://example.com/video",
                format_selector="137+140",
                media_type="video",
                output_path_template="test.%(ext)s",
                merge_output_format="mp4",
            )
        assert "requires merging separate video and audio streams with FFmpeg" in str(exc_info.value)


@pytest.mark.asyncio
async def test_api_validate_stream_pair_endpoint():
    """Test POST /api/streams/validate-pair endpoint returns validation status."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        video = {"format_id": "137", "ext": "mp4", "vcodec": "avc1", "acodec": "none", "stream_kind": "video_only"}
        audio = {"format_id": "140", "ext": "m4a", "vcodec": "none", "acodec": "mp4a", "stream_kind": "audio_only"}

        resp = await client.post(
            "/api/streams/validate-pair",
            json={"video_stream": video, "audio_stream": audio},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["compatible"] is True
        assert data["requires_merge"] is True
        assert data["target_container"] == "mp4"


@pytest.mark.asyncio
async def test_api_download_stream_pair_queued():
    """Test POST /api/download queues a paired video+audio merge task."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/download",
            json={
                "url": "https://example.com/video",
                "title": "Paired Stream Video",
                "video_format_id": "312",
                "audio_format_id": "140",
                "merge_output_format": "mp4",
                "is_merge_operation": True,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "task_id" in data
        assert data["status"] == "queued"


def test_stream_pair_merge_and_media_inspection(tmp_path):
    """Verify stream pairing, FFmpeg lossless merging, and media stream verification.

    Tests that:
    1. A video-only stream contains no audio.
    2. An audio-only stream contains no video.
    3. Merging them produces an MP4 containing both valid video and audio streams.
    """
    import subprocess
    from backend.engine.ffmpeg_manager import validate_ffmpeg_path

    ffmpeg_info = validate_ffmpeg_path()
    if not ffmpeg_info["available"]:
        pytest.skip("FFmpeg is not available in test environment.")

    ffmpeg_exe = ffmpeg_info["path"]
    v_file = tmp_path / "stream_v.mp4"
    a_file = tmp_path / "stream_a.m4a"
    merged_file = tmp_path / "merged_final.mp4"

    # 1. Generate 1s silent video stream (H.264/AVC, strictly no audio)
    subprocess.run(
        [ffmpeg_exe, "-y", "-f", "lavfi", "-i", "testsrc=duration=1:size=320x240:rate=30", "-c:v", "libx264", "-an", str(v_file)],
        check=True,
        capture_output=True,
    )

    # 2. Generate 1s audio-only stream (AAC, strictly no video)
    subprocess.run(
        [ffmpeg_exe, "-y", "-f", "lavfi", "-i", "sine=duration=1:frequency=440", "-c:a", "aac", "-vn", str(a_file)],
        check=True,
        capture_output=True,
    )

    # Verify input stream properties before merging
    probe_v = subprocess.run([ffmpeg_exe, "-hide_banner", "-i", str(v_file)], capture_output=True, text=True)
    assert any("Video:" in l for l in probe_v.stderr.splitlines())
    assert not any("Audio:" in l for l in probe_v.stderr.splitlines()), "Video-only source unexpectedly has audio"

    probe_a = subprocess.run([ffmpeg_exe, "-hide_banner", "-i", str(a_file)], capture_output=True, text=True)
    assert any("Audio:" in l for l in probe_a.stderr.splitlines())
    assert not any("Video:" in l for l in probe_a.stderr.splitlines()), "Audio-only source unexpectedly has video"

    # 3. Merge both streams with stream copying (-c copy)
    subprocess.run(
        [ffmpeg_exe, "-y", "-i", str(v_file), "-i", str(a_file), "-c", "copy", str(merged_file)],
        check=True,
        capture_output=True,
    )

    assert merged_file.exists()
    assert merged_file.stat().st_size > 5_000

    # 4. Probe the merged file to confirm both audio and video streams are present
    probe_merged = subprocess.run([ffmpeg_exe, "-hide_banner", "-i", str(merged_file)], capture_output=True, text=True)
    has_video = any("Video:" in l for l in probe_merged.stderr.splitlines())
    has_audio = any("Audio:" in l for l in probe_merged.stderr.splitlines())

    assert has_video, "Merged file is missing video stream"
    assert has_audio, "Merged file is missing audio stream (missing sound regression)"

