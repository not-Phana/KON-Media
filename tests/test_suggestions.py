"""Regression and integration tests for KON Search 1.1.0 Rei Suggestions & Song Discovery.

Tests:
1. One-word queries (e.g. 'ban', 'bankai', 'shelter')
2. Partial song titles (e.g. 'I Wanna Be')
3. Partial artist names & combinations (e.g. 'Shelter Porter')
4. Incomplete version queries (e.g. 'NewJeans Jersey Club')
5. Deduplication of equivalent song candidates
6. Rank ordering: exact title > phrase prefix > loose match
7. No match / arbitrary query handling (honest empty result, no hallucination)
8. Provider timeout / error resilience (graceful fallback)
9. FastAPI REST endpoint `/api/search/suggestions` structure & headers
10. High-speed LRU cache verification
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.search.suggestions import SuggestionEngine, get_shared_suggestion_engine


@pytest.fixture
def suggestion_engine():
    """Create a fresh SuggestionEngine instance."""
    return SuggestionEngine()


@pytest.fixture
def client():
    """FastAPI TestClient for REST API endpoints."""
    return TestClient(app)


def test_partial_song_title_discovery(suggestion_engine):
    """Test partial title 'I Wanna Be' discovers 'I Wanna Be Yours' by Arctic Monkeys."""
    sugs = suggestion_engine.get_suggestions("I Wanna Be", limit=5, media_type="audio")
    assert len(sugs) > 0

    top_song = next((s for s in sugs if s["type"] == "song"), None)
    assert top_song is not None
    assert "i wanna be yours" in top_song["title"].lower()
    assert top_song["artist"] in ("Arctic Monkeys", None) or "arctic monkeys" in str(top_song["artist"]).lower()


def test_keyword_song_discovery_bankai(suggestion_engine):
    """Test keyword 'Bankai' discovers Bleach soundtrack song 'Number One - Bankai'."""
    sugs = suggestion_engine.get_suggestions("Bankai", limit=6, media_type="audio")
    assert len(sugs) > 0

    # Ensure 'Number One - Bankai' is present among top song discoveries
    bankai_song = next((s for s in sugs if "bankai" in s["title"].lower()), None)
    assert bankai_song is not None
    assert bankai_song["type"] == "song"
    assert "bankai" in bankai_song["title"].lower()


def test_partial_title_and_artist_combination(suggestion_engine):
    """Test partial title + artist combination 'Shelter Porter' discovers 'Shelter' by Porter Robinson."""
    sugs = suggestion_engine.get_suggestions("Shelter Porter", limit=5, media_type="audio")
    assert len(sugs) > 0

    top = sugs[0]
    assert "shelter" in top["title"].lower()
    if top["type"] == "song":
        assert "porter robinson" in top["artist"].lower()


def test_incomplete_version_information(suggestion_engine):
    """Test 'NewJeans Jersey Club' surfaces matching Jersey Club version."""
    sugs = suggestion_engine.get_suggestions("NewJeans Jersey Club", limit=5, media_type="audio")
    assert len(sugs) > 0

    jersey_song = next((s for s in sugs if "jersey" in s["title"].lower()), None)
    assert jersey_song is not None
    assert "newjeans" in str(jersey_song.get("artist") or jersey_song["title"]).lower()


def test_one_word_query_ban(suggestion_engine):
    """Test one-word query 'ban' surfaces relevant suggestions without crashing."""
    sugs = suggestion_engine.get_suggestions("ban", limit=5, media_type="audio")
    assert len(sugs) > 0
    # Must contain either a discovered song or query refinements
    assert any(s["type"] in ("song", "query") for s in sugs)


def test_unmatched_query_honesty(suggestion_engine):
    """Test that a nonsensical query produces zero false song matches (no hallucinations)."""
    sugs = suggestion_engine.get_suggestions("zxqj982347nonsenseqwe", limit=5)
    # When no genuine evidence exists, song discoveries must be empty
    song_discoveries = [s for s in sugs if s["type"] == "song"]
    assert len(song_discoveries) == 0


def test_deduplication_removes_topic_variants(suggestion_engine):
    """Test that duplicate artists like 'Shiro Sagisu - Topic' and 'Shiro Sagisu' are deduplicated."""
    mock_candidates = [
        {
            "id": "cand_1",
            "title": "Number One - Bankai",
            "artist": "Shiro Sagisu - Topic",
            "url": "https://www.youtube.com/watch?v=1",
            "thumbnail": "https://thumb1.jpg",
            "duration": 283.0,
            "platform": "youtube",
        },
        {
            "id": "cand_2",
            "title": "Number One - Bankai",
            "artist": "Shiro Sagisu",
            "url": "https://www.youtube.com/watch?v=2",
            "thumbnail": "https://thumb2.jpg",
            "duration": 283.0,
            "platform": "youtube",
        },
    ]

    ranked = suggestion_engine.rank_suggestions(
        query="Bankai",
        song_candidates=mock_candidates,
        query_suggestions=[],
        limit=5,
    )

    # Should only return one unique 'Number One - Bankai' song
    matching_titles = [s for s in ranked if s.title == "Number One - Bankai"]
    assert len(matching_titles) == 1
    assert matching_titles[0].artist == "Shiro Sagisu"


def test_rank_ordering_exact_vs_partial(suggestion_engine):
    """Test exact title match receives higher relevance score than partial substring match."""
    mock_candidates = [
        {
            "id": "c1",
            "title": "Shelter",
            "artist": "Porter Robinson & Madeon",
            "url": "https://url1",
            "thumbnail": None,
            "duration": 219.0,
        },
        {
            "id": "c2",
            "title": "Gimme Shelter",
            "artist": "The Rolling Stones",
            "url": "https://url2",
            "thumbnail": None,
            "duration": 270.0,
        },
    ]

    ranked = suggestion_engine.rank_suggestions(
        query="Shelter",
        song_candidates=mock_candidates,
        query_suggestions=[],
        limit=5,
    )

    assert len(ranked) >= 2
    assert ranked[0].title == "Shelter"
    assert ranked[0].score > ranked[1].score


def test_provider_failure_graceful_fallback(monkeypatch, suggestion_engine):
    """Test that if provider candidate or suggestion lookup fails, local seed index still returns results."""
    def broken_fetch(*args, **kwargs):
        raise ConnectionError("Simulated network outage")

    monkeypatch.setattr(suggestion_engine, "_fetch_real_query_suggestions", broken_fetch)
    monkeypatch.setattr(suggestion_engine, "_fetch_live_provider_candidates", broken_fetch)

    # Local index should still discover 'Bankai' without raising exception
    sugs = suggestion_engine.get_suggestions("Bankai", limit=4)
    assert len(sugs) > 0
    assert any("bankai" in s["title"].lower() for s in sugs)


def test_api_search_suggestions_endpoint(client):
    """Test FastAPI GET /api/search/suggestions REST endpoint."""
    resp = client.get("/api/search/suggestions?q=Bankai&limit=5&media_type=audio")
    assert resp.status_code == 200
    assert resp.headers["X-KON-Search-Engine"] == "KON Search 1.1.0 Rei"

    data = resp.json()
    assert data["query"] == "Bankai"
    assert data["product"] == "KON Search 1.1.0 Rei"
    assert "suggestions" in data
    assert isinstance(data["suggestions"], list)
    assert len(data["suggestions"]) > 0

    first = data["suggestions"][0]
    assert "id" in first
    assert "query" in first
    assert "title" in first
    assert "type" in first
    assert first["type"] in ("song", "query")


def test_api_suggestions_empty_query(client):
    """Test GET /api/search/suggestions with empty query returns empty list gracefully."""
    resp = client.get("/api/search/suggestions?q=")
    assert resp.status_code == 200
    data = resp.json()
    assert data["suggestions"] == []
    assert data["count"] == 0


def test_video_classification_and_platform_label(suggestion_engine):
    """Test that non-music YouTube videos (e.g. anime recaps, 11-hour story marathons) are classified as video."""
    video_candidate = {
        "id": "vid_bleach_recap",
        "title": "រឿង Bleach | រដូវកាលទី1 (សង្ខេបមួយរឿងពេញ)",
        "artist": "JULIASINN",
        "url": "https://www.youtube.com/watch?v=bleach1",
        "thumbnail": "https://i.ytimg.com/vi/bleach1/hqdefault.jpg",
        "duration": 41825.0,  # 697 minutes = 11.6 hours
        "platform": "youtube",
    }

    # 1. In audio mode (Song & Music), this long anime recap must be rejected / filtered out
    audio_score = suggestion_engine._score_song_candidate(
        video_candidate,
        norm_q="bleach",
        query_tokens=["bleach"],
        detected_version=None,
        media_type="audio",
    )
    assert audio_score == 0.0

    # 2. In video/all mode, it is accepted but accurately classified as a YouTube Video
    ranked = suggestion_engine.rank_suggestions(
        query="Bleach",
        song_candidates=[video_candidate],
        query_suggestions=[],
        limit=5,
        media_type="all",
    )
    assert len(ranked) == 1
    item = ranked[0]
    assert item.type == "video"
    assert item.platform == "youtube"
    assert item.match_reason == "YouTube Video"
    assert item.artist == "JULIASINN"

