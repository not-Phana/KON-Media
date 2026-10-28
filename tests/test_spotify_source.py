"""Tests for Spotify source recognition, DRM stream handling, and audio workflow support."""

import pytest
from unittest.mock import MagicMock, patch
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.security.url_guard import (
    is_spotify_hostname,
    detect_spotify_source,
    validate_media_url,
    SecurityValidationError,
)
from backend.engine.media_engine import (
    extract_media_info,
    execute_download,
    MediaEngineError,
)


# =====================================================================
# 1. Hostname and Deceptive URL Protection Tests
# =====================================================================

def test_spotify_hostname_legitimate():
    """Verify legitimate Spotify hostnames are recognized."""
    assert is_spotify_hostname("open.spotify.com") is True
    assert is_spotify_hostname("play.spotify.com") is True
    assert is_spotify_hostname("spotify.com") is True
    assert is_spotify_hostname("www.spotify.com") is True
    assert is_spotify_hostname("spotify.link") is True
    assert is_spotify_hostname("app.spotify.link") is True


def test_spotify_hostname_deceptive_and_spoofed():
    """Verify deceptive hostnames containing 'spotify' are strictly rejected."""
    deceptive_hosts = [
        "open.spotify.com.attacker.com",
        "spotify.com.malicious.net",
        "not-spotify.com",
        "fake-spotify.com",
        "myspotify.com",
        "spotify.org",
        "spotify.co",
        "attacker-spotify.com",
        "spotify.phishing.io",
        "sub.spotify.com.fake.com",
        "",
        None,
    ]
    for host in deceptive_hosts:
        assert is_spotify_hostname(host) is False, f"Failed for deceptive host: {host}"


# =====================================================================
# 2. Content Type Parsing & Canonicalization Tests
# =====================================================================

def test_detect_spotify_source_track():
    """Verify Spotify track URL is parsed with canonical URL."""
    url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT?si=123abc456"
    res = detect_spotify_source(url)
    assert res is not None
    assert res["is_spotify"] is True
    assert res["source"] == "spotify"
    assert res["content_type"] == "track"
    assert res["content_id"] == "4cOdK2wGLETKBW3PvgPWqT"
    assert res["title"] == "Spotify Track"
    assert res["canonical_url"] == "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"


def test_detect_spotify_source_album():
    """Verify Spotify album URL classification."""
    url = "https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3"
    res = detect_spotify_source(url)
    assert res is not None
    assert res["content_type"] == "album"
    assert res["content_id"] == "1DFixLWuPkv3KT3TnV35m3"
    assert res["title"] == "Spotify Album"


def test_detect_spotify_source_playlist():
    """Verify Spotify playlist URLs (standard and user-nested)."""
    # Standard playlist
    url1 = "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"
    res1 = detect_spotify_source(url1)
    assert res1 is not None
    assert res1["content_type"] == "playlist"
    assert res1["content_id"] == "37i9dQZF1DXcBWIGoYBM5M"

    # User playlist
    url2 = "https://open.spotify.com/user/spotify_fan_42/playlist/6yP2it6a9wxLM5Rh0E1Lio"
    res2 = detect_spotify_source(url2)
    assert res2 is not None
    assert res2["content_type"] == "playlist"
    assert res2["content_id"] == "6yP2it6a9wxLM5Rh0E1Lio"


def test_detect_spotify_source_other_content():
    """Verify artist, episode, show, localized paths, and spotify.link shortlinks."""
    # Artist
    res_artist = detect_spotify_source("https://open.spotify.com/artist/06HL4z0CvFAxyc27GXpf02")
    assert res_artist["content_type"] == "artist"

    # Episode
    res_ep = detect_spotify_source("https://open.spotify.com/episode/5as7c6G2fW")
    assert res_ep["content_type"] == "episode"

    # Show
    res_show = detect_spotify_source("https://open.spotify.com/show/4rOoJ6Egrf")
    assert res_show["content_type"] == "show"

    # Localized path (/intl-de/track/...)
    res_intl = detect_spotify_source("https://open.spotify.com/intl-de/track/4cOdK2wGLETKBW3PvgPWqT")
    assert res_intl["content_type"] == "track"
    assert res_intl["content_id"] == "4cOdK2wGLETKBW3PvgPWqT"

    # spotify.link shortlink
    res_link = detect_spotify_source("https://spotify.link/AbCdEf123")
    assert res_link["content_type"] == "shared_link"
    assert res_link["content_id"] == "AbCdEf123"


def test_detect_spotify_source_rejection_of_deceptive_urls():
    """Verify deceptive URLs return None."""
    deceptive_urls = [
        "https://open.spotify.com.attacker.com/track/123",
        "https://fake-spotify.com/album/456",
        "https://not-spotify.com/playlist/789",
        "http://attacker.com/?q=https://open.spotify.com/track/123",
        "file:///E:/Code/spotify.mp3",
        "ftp://open.spotify.com/track/123",
    ]
    for url in deceptive_urls:
        assert detect_spotify_source(url) is None, f"Should reject deceptive URL: {url}"


# =====================================================================
# 3. Media Engine Extraction & Download Protection Tests
# =====================================================================

def test_extract_media_info_spotify_source():
    """Verify extract_media_info intercepts Spotify URLs without calling yt-dlp."""
    spotify_url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"

    # We do NOT mock yt_dlp here to prove yt-dlp is never called
    res = extract_media_info(spotify_url)
    assert res["supported"] is False
    assert res["is_unsupported_source"] is True
    assert res["source"] == "spotify"
    assert res["content_type"] == "track"
    assert res["title"] in ("Spotify Track", "Never Gonna Give You Up")
    assert "Digital Rights Management" in res["message"] or "DRM" in res["message"]
    assert "official Spotify" in res["guidance"]
    assert res["open_in_spotify_url"] == "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
    assert res["video_formats"] == []
    assert res["audio_formats"] == []


def test_execute_download_spotify_rejected():
    """Verify execute_download immediately raises MediaEngineError on Spotify URLs."""
    spotify_url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"

    with pytest.raises(MediaEngineError, match="Spotify music streams are protected by Digital Rights Management"):
        execute_download(
            url=spotify_url,
            format_selector="bestaudio/best",
            media_type="audio",
            output_path_template="dummy.%(ext)s",
        )


# =====================================================================
# 4. API Endpoints: /api/analyze, /api/download, and /api/open-url
# =====================================================================

@pytest.mark.asyncio
async def test_api_analyze_spotify_returns_structured_guidance():
    """Verify POST /api/analyze returns informative unsupported-source response."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/analyze",
            json={"url": "https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["supported"] is False
        assert data["is_unsupported_source"] is True
        assert data["source"] == "spotify"
        assert data["content_type"] == "playlist"
        assert "open_in_spotify_url" in data
        assert "official Spotify" in data["guidance"]


@pytest.mark.asyncio
async def test_api_download_spotify_rejected_with_400():
    """Verify POST /api/download rejects Spotify URLs with clear HTTP 400 error."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/download",
            json={
                "url": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT",
                "media_type": "audio",
                "format_id": "bestaudio/best",
            },
        )
        assert resp.status_code == 400
        detail = resp.json()["detail"]
        assert "DRM" in detail or "Digital Rights Management" in detail
        assert "official Spotify" in detail


@pytest.mark.asyncio
async def test_api_open_url_spotify_success():
    """Verify POST /api/open-url safely validates and opens Spotify URL in system browser."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("webbrowser.open", return_value=True) as mock_open:
            resp = await client.post(
                "/api/open-url",
                json={"url": "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "opened"
            assert data["url"] == "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
            mock_open.assert_called_once_with("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT")


@pytest.mark.asyncio
async def test_api_open_url_rejects_unauthorized_and_deceptive():
    """Verify POST /api/open-url rejects deceptive or arbitrary external URLs."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Deceptive Spotify URL
        resp = await client.post(
            "/api/open-url",
            json={"url": "https://open.spotify.com.attacker.com/track/123"},
        )
        assert resp.status_code == 400

        # Arbitrary non-Spotify URL
        resp = await client.post(
            "/api/open-url",
            json={"url": "https://example.com/exploit"},
        )
        assert resp.status_code == 400
        assert "Only recognized external service URLs" in resp.json()["detail"]


# =====================================================================
# 5. Legitimate Audio Downloads Retention Tests
# =====================================================================

def test_extract_media_info_direct_audio_format_available():
    """Verify direct audio files offer 'Original Audio (Direct)' without requiring FFmpeg."""
    mock_audio_info = {
        "title": "Public Domain Classical Recording",
        "uploader": "Archive Audio",
        "duration": 240,
        "thumbnail": None,
        "extractor": "Generic",
        "webpage_url": "https://archive.org/sample.mp3",
        "ext": "mp3",
        "vcodec": "none",
        "acodec": "mp3",
        "formats": [
            {"format_id": "mp3_direct", "vcodec": "none", "acodec": "mp3", "ext": "mp3", "tbr": 192}
        ],
    }

    with patch("backend.engine.media_engine.yt_dlp.YoutubeDL") as MockYDL:
        mock_instance = MagicMock()
        mock_instance.extract_info.return_value = mock_audio_info
        mock_instance.__enter__.return_value = mock_instance
        mock_instance.__exit__.return_value = None
        MockYDL.return_value = mock_instance

        # Even with FFmpeg unavailable, direct audio stream is labeled requires_ffmpeg=False
        with patch("backend.engine.media_engine.validate_ffmpeg_path", return_value={"available": False, "path": None}):
            res = extract_media_info("https://archive.org/sample.mp3")
            assert len(res["audio_formats"]) >= 1
            direct_audio = next((f for f in res["audio_formats"] if f["bitrate"] == "original"), None)
            assert direct_audio is not None
            assert direct_audio["requires_ffmpeg"] is False
            assert "Direct" in direct_audio["label"]


def test_execute_download_direct_audio_without_ffmpeg():
    """Verify downloading a direct audio stream with bitrate='original' succeeds without FFmpeg."""
    captured_opts = {}

    def mock_ydl_init(opts):
        captured_opts.update(opts)
        mock_ydl = MagicMock()
        mock_ydl.download.return_value = 0
        mock_ydl.__enter__.return_value = mock_ydl
        mock_ydl.__exit__.return_value = None
        return mock_ydl

    # FFmpeg unavailable
    with patch("backend.engine.media_engine.validate_ffmpeg_path", return_value={"available": False, "path": None}):
        with patch("backend.engine.media_engine.yt_dlp.YoutubeDL", side_effect=mock_ydl_init):
            res = execute_download(
                url="https://archive.org/recording.mp3",
                format_selector="bestaudio/best",
                media_type="audio",
                audio_bitrate="original",
                output_path_template="dummy.%(ext)s",
                ffmpeg_location=None,
            )
            assert res["success"] is True
            assert captured_opts["format"] == "bestaudio/best"
            # Postprocessors must NOT be attached when direct audio is downloaded without FFmpeg
            assert "postprocessors" not in captured_opts
