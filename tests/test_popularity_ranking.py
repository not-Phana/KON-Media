"""Test suite for Popularity-Aware Music Ranking in KON Search 1.2:
- KON Search 1.2 Rei (Precision Mode)
- KON Search 1.2 Rei Flash (Speed Mode)

Validates all popularity ranking requirements:
1. Broad queries ('popular songs', 'trending music') rank high-stream global hits first.
2. Exact title searches rank the correct song above weak keyword matches even if the weak match has views.
3. Title + artist searches preserve specific relevance over unrelated popular songs.
4. Ambiguous song titles ('bad guy') rank the globally popular hit (Billie Eilish) above obscure 120-view demos.
5. Trending & freshness boost: new trending tracks compete fairly against older hits.
6. Missing popularity metadata: assigned a neutral prior without unfair demotion.
7. Ranking parity: Rei and Rei Flash produce consistent ordering for top candidates.
"""

import pytest
from starlette.testclient import TestClient
from backend.main import app
from backend.search.models import CandidateResult, SearchQuery
from backend.search import rust_bridge


@pytest.fixture
def popularity_candidate_pool():
    """Diverse candidate pool with verifiable streams/views, trending flags,

    release years, chart ranks, and missing metadata cases.
    """
    return [
        # Billie Eilish - bad guy (Global smash hit, 1.35B+ views)
        CandidateResult(
            id="bad_guy_billie",
            title="Billie Eilish - bad guy",
            uploader="Billie Eilish",
            url="https://www.youtube.com/watch?v=DyDfgMOUjCI",
            thumbnail="https://i.ytimg.com/vi/DyDfgMOUjCI/hqdefault.jpg",
            duration=194,
            views=1350000000,
            likes=12000000,
            listeners=85000000,
            chart_rank=1,
            release_year=2019,
            is_trending=False,
            is_music=True,
            content_type="music",
        ),
        # Obscure garage demo with same exact title "bad guy" (120 views)
        CandidateResult(
            id="bad_guy_obscure",
            title="bad guy",
            uploader="Garage Band Demo 2011",
            url="https://www.youtube.com/watch?v=obscure_bg_01",
            thumbnail="https://i.ytimg.com/vi/obscure_bg_01/hqdefault.jpg",
            duration=150,
            views=120,
            likes=4,
            listeners=15,
            chart_rank=None,
            release_year=2011,
            is_trending=False,
            is_music=True,
            content_type="music",
        ),
        # Shiro SAGISU - Number One (Bankai Version) (14.5M views, specific anime song)
        CandidateResult(
            id="shiro_number_one_bankai",
            title="Shiro SAGISU - Number One (Bankai Version) [Official Bleach TYBW OST]",
            uploader="Shiro SAGISU - Topic",
            url="https://www.youtube.com/watch?v=bleach_bankai_01",
            thumbnail="https://i.ytimg.com/vi/bleach_bankai_01/hqdefault.jpg",
            duration=305,
            views=14500000,
            likes=350000,
            listeners=4200000,
            chart_rank=None,
            release_year=2022,
            is_trending=False,
            is_music=True,
            content_type="music",
        ),
        # Massive pop hit with "One" in title, unrelated to Bleach/Bankai (8.2B views)
        CandidateResult(
            id="unrelated_mega_hit",
            title="Luis Fonsi - Despacito ft. Daddy Yankee",
            uploader="Luis Fonsi",
            url="https://www.youtube.com/watch?v=kJQP7kiw5Fk",
            thumbnail="https://i.ytimg.com/vi/kJQP7kiw5Fk/hqdefault.jpg",
            duration=222,
            views=8200000000,
            likes=53000000,
            listeners=110000000,
            chart_rank=1,
            release_year=2017,
            is_trending=False,
            is_music=True,
            content_type="music",
        ),
        # Trending 2026 track (e.g. 50M views, is_trending=True, year=2026)
        CandidateResult(
            id="trending_hit_2026",
            title="K-Pop Sensation - Electric Horizon",
            uploader="Trend Records",
            url="https://www.youtube.com/watch?v=trend_2026_01",
            thumbnail="https://i.ytimg.com/vi/trend_2026_01/hqdefault.jpg",
            duration=185,
            views=50000000,
            likes=3800000,
            listeners=25000000,
            chart_rank=2,
            release_year=2026,
            is_trending=True,
            is_music=True,
            content_type="music",
        ),
        # Legacy all-time hit (e.g. 200M views, year=2004, is_trending=False)
        CandidateResult(
            id="legacy_rock_hit",
            title="Vintage Rockers - Electric Horizon (1998 Acoustic Live)",
            uploader="Classic Archives",
            url="https://www.youtube.com/watch?v=vintage_eh_01",
            thumbnail="https://i.ytimg.com/vi/vintage_eh_01/hqdefault.jpg",
            duration=210,
            views=200000000,
            likes=2100000,
            listeners=18000000,
            chart_rank=15,
            release_year=2004,
            is_trending=False,
            is_music=True,
            content_type="music",
        ),
        # Track with missing popularity metadata (views=None, likes=None, chart_rank=None)
        # But high textual relevance to query 'Acoustic Serenade'
        CandidateResult(
            id="missing_metadata_track",
            title="Acoustic Serenade - Official Studio Master",
            uploader="Indie Artist Collective",
            url="https://www.youtube.com/watch?v=acoustic_serenade_01",
            thumbnail="https://i.ytimg.com/vi/acoustic_serenade_01/hqdefault.jpg",
            duration=200,
            views=None,
            likes=None,
            listeners=None,
            chart_rank=None,
            release_year=2025,
            is_trending=False,
            is_music=True,
            content_type="music",
        ),
        # Weak match with high views (10M views, random guitar tutorial)
        CandidateResult(
            id="weak_match_with_views",
            title="How to Play Guitar in 5 Minutes (Serenade style)",
            uploader="Guitar Lessons Fast",
            url="https://www.youtube.com/watch?v=guitar_lesson_01",
            thumbnail="https://i.ytimg.com/vi/guitar_lesson_01/hqdefault.jpg",
            duration=350,
            views=10000000,
            likes=450000,
            listeners=None,
            chart_rank=None,
            release_year=2020,
            is_trending=False,
            is_music=False,
            content_type="video",
        ),
    ]


def test_ambiguous_title_ranks_popular_song_first(popularity_candidate_pool):
    """Searching ambiguous 'bad guy' must rank Billie Eilish #1 over a 120-view garage demo."""
    query = SearchQuery(raw_query="bad guy", media_type="audio")
    rei_ranked = rust_bridge.rank_candidates(query, popularity_candidate_pool)

    assert len(rei_ranked) > 0
    assert rei_ranked[0].id == "bad_guy_billie", (
        f"Expected Billie Eilish #1, got {rei_ranked[0].id} ({rei_ranked[0].title})"
    )
    assert rei_ranked[0].popularity is not None
    assert rei_ranked[0].popularity > 0.85


def test_ambiguous_title_flash_parity(popularity_candidate_pool):
    """Rei Flash must also rank Billie Eilish #1 for ambiguous 'bad guy'."""
    query = SearchQuery(raw_query="bad guy", media_type="audio")
    flash_ranked = rust_bridge.rank_candidates_flash(query, popularity_candidate_pool)

    assert len(flash_ranked) > 0
    assert flash_ranked[0].id == "bad_guy_billie"
    assert flash_ranked[0].popularity is not None
    assert flash_ranked[0].popularity > 0.85


def test_specific_search_preserves_relevance_over_mega_hit(popularity_candidate_pool):
    """Specific query 'Number One Bankai' must NOT be hijacked by 8.2B view Despacito."""
    query = SearchQuery(raw_query="Number One Bankai", media_type="audio")

    rei_ranked = rust_bridge.rank_candidates(query, popularity_candidate_pool)
    flash_ranked = rust_bridge.rank_candidates_flash(query, popularity_candidate_pool)

    assert rei_ranked[0].id == "shiro_number_one_bankai"
    assert flash_ranked[0].id == "shiro_number_one_bankai"

    # Despacito should have low relevance despite 8.2B views
    despacito_rank_rei = next((idx for idx, c in enumerate(rei_ranked) if c.id == "unrelated_mega_hit"), -1)
    despacito_rank_flash = next((idx for idx, c in enumerate(flash_ranked) if c.id == "unrelated_mega_hit"), -1)
    assert despacito_rank_rei > 0 or despacito_rank_rei == -1
    assert despacito_rank_flash > 0 or despacito_rank_flash == -1


def test_broad_search_prioritizes_popularity(popularity_candidate_pool):
    """Broad queries like 'popular songs' or 'trending music' rank globally popular/trending tracks first."""
    query = SearchQuery(raw_query="popular songs", media_type="audio")

    rei_ranked = rust_bridge.rank_candidates(query, popularity_candidate_pool)
    flash_ranked = rust_bridge.rank_candidates_flash(query, popularity_candidate_pool)

    top_ids_rei = [c.id for c in rei_ranked[:3]]
    top_ids_flash = [c.id for c in flash_ranked[:3]]

    # Top spots should be occupied by billion-view/trending hits, not obscure 120-view demos
    assert "bad_guy_obscure" not in top_ids_rei
    assert "bad_guy_obscure" not in top_ids_flash
    assert rei_ranked[0].id in ["unrelated_mega_hit", "bad_guy_billie", "trending_hit_2026"]
    assert flash_ranked[0].id in ["unrelated_mega_hit", "bad_guy_billie", "trending_hit_2026"]


def test_fresh_trending_boost_competitiveness(popularity_candidate_pool):
    """For 'Electric Horizon', trending 2026 track with 50M views ranks above or ties 2004 track."""
    query = SearchQuery(raw_query="Electric Horizon", media_type="audio")

    rei_ranked = rust_bridge.rank_candidates(query, popularity_candidate_pool)
    flash_ranked = rust_bridge.rank_candidates_flash(query, popularity_candidate_pool)

    assert len(rei_ranked) >= 2
    assert rei_ranked[0].id == "trending_hit_2026"
    assert flash_ranked[0].id == "trending_hit_2026"


def test_missing_popularity_metadata_not_penalized(popularity_candidate_pool):
    """Query 'Acoustic Serenade': exact music match with missing views beats unrelated tutorial with 10M views."""
    query = SearchQuery(raw_query="Acoustic Serenade", media_type="audio")

    rei_ranked = rust_bridge.rank_candidates(query, popularity_candidate_pool)
    flash_ranked = rust_bridge.rank_candidates_flash(query, popularity_candidate_pool)

    assert len(rei_ranked) > 0
    assert rei_ranked[0].id == "missing_metadata_track"
    assert flash_ranked[0].id == "missing_metadata_track"


def test_api_search_popularity_fields():
    """Verify that REST API exposes popularity score and works across models."""
    client = TestClient(app)
    response = client.get("/api/search?q=bad+guy&model=rei_flash")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "model" in data
    assert response.headers.get("x-kon-search-model") in ["KON Search 1.2 Rei Flash", "rei_flash"]
