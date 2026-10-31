"""Tests for lyrics extraction, synchronization parsing, caching, and API endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from starlette.testclient import TestClient

from backend.lyrics.lyrics_service import (
    LyricsService,
    LyricsCache,
    clean_music_title,
    parse_lrc,
)
from backend.main import app

client = TestClient(app)


def test_parse_lrc_standard():
    lrc_sample = """
    [00:17.44] いつも支えてくれる人達に
    [00:19.56] 日頃の想いを込めたラプソディー
    [00:22.07] アプリシエーションの気持ちよ 届け
    """
    lines = parse_lrc(lrc_sample)
    assert len(lines) == 3
    assert lines[0]["time"] == 17.44
    assert lines[0]["text"] == "いつも支えてくれる人達に"
    assert lines[1]["time"] == 19.56
    assert lines[2]["time"] == 22.07


def test_parse_lrc_multiple_timestamps_and_sorting():
    lrc_sample = """
    [00:30.00][01:00.00] Chorus line repeated
    [00:10.00] Intro line
    """
    lines = parse_lrc(lrc_sample)
    assert len(lines) == 3
    # Check lines are sorted by time
    assert lines[0]["time"] == 10.00
    assert lines[0]["text"] == "Intro line"
    assert lines[1]["time"] == 30.00
    assert lines[1]["text"] == "Chorus line repeated"
    assert lines[2]["time"] == 60.00
    assert lines[2]["text"] == "Chorus line repeated"


def test_parse_lrc_empty_or_malformed():
    assert parse_lrc("") == []
    assert parse_lrc("Just some plain text without timestamps") == []
    assert parse_lrc("   \n\n  ") == []


def test_clean_music_title():
    # YouTube video clutter removal
    t1, a1 = clean_music_title("Thank You!! [Official Video]", "HOME MADE 家族")
    assert t1 == "Thank You!!"
    assert a1 == "HOME MADE 家族"

    # Split "Artist - Title"
    t2, a2 = clean_music_title("Ed Sheeran - Shape of You (Official Music Video)")
    assert t2 == "Shape of You"
    assert a2 == "Ed Sheeran"

    # Japanese bracket clutter
    t3, a3 = clean_music_title("【MV】Lemon / 米津玄師")
    assert "Lemon" in t3 or "米津玄師" in a3


def test_lyrics_cache_storage(tmp_path):
    cache_db = tmp_path / "test_lyrics.db"
    cache = LyricsCache(db_path=cache_db)

    # Initial get should be None
    assert cache.get("Thank You!!", "HOME MADE 家族") is None

    # Insert into cache
    cache.set(
        title="Thank You!!",
        artist="HOME MADE 家族",
        track_name="Thank You!!",
        artist_name="HOME MADE 家族",
        synced=True,
        plain_lyrics="いつも支えてくれる人達に\n...",
        synced_lyrics="[00:17.44] いつも支えてくれる人達に\n[00:19.56] 日頃の想いを込めたラプソディー",
        instrumental=False,
        source="lrclib",
    )

    # Now get should return cached record
    hit = cache.get("Thank You!!", "HOME MADE 家族")
    assert hit is not None
    assert hit["found"] is True
    assert hit["synced"] is True
    assert hit["track_name"] == "Thank You!!"
    assert len(hit["lines"]) == 2
    assert hit["cached"] is True


@pytest.mark.asyncio
async def test_lyrics_service_mocked_fetch(tmp_path):
    cache_db = tmp_path / "test_svc_lyrics.db"
    service = LyricsService(cache=LyricsCache(db_path=cache_db))

    mock_lrclib_response = {
        "trackName": "Thank You!!",
        "artistName": "HOME MADE 家族",
        "syncedLyrics": "[00:17.44] いつも支えてくれる人達に\n[00:19.56] 日頃の想いを込めたラプソディー",
        "plainLyrics": "いつも支えてくれる人達に\n日頃の想いを込めたラプソディー",
        "instrumental": False,
    }

    with patch.object(service, "_fetch_from_lrclib", new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_lrclib_response

        res = await service.get_lyrics("Thank You!!", "HOME MADE 家族", duration=273.0)
        assert res["found"] is True
        assert res["synced"] is True
        assert len(res["lines"]) == 2
        assert res["cached"] is False

        # Next call should be served from cache without invoking _fetch_from_lrclib
        mock_fetch.reset_mock()
        cached_res = await service.get_lyrics("Thank You!!", "HOME MADE 家族")
        assert cached_res["found"] is True
        assert cached_res["cached"] is True
        mock_fetch.assert_not_called()


def test_api_lyrics_endpoint():
    # Test API endpoint response schema
    resp = client.get("/api/lyrics", params={"title": "Test Unknown Song 999999", "artist": "No Artist XYZ"})
    assert resp.status_code == 200
    data = resp.json()
    assert "found" in data
    assert "synced" in data
    assert "lines" in data
    assert isinstance(data["lines"], list)
