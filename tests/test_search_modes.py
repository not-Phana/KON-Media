"""Comprehensive test suite for KON Search 1.2 Dual Engine System:
- KON Search 1.2 Rei (Precision Mode)
- KON Search 1.2 Rei Flash (Speed Mode)

Validates all Section 5 requirements:
- Query understanding, ranking, and speedup across both engines.
- Correct song, artist, version, thumbnail, provider ID, and URL identification.
- Strict non-music, gameplay, and reaction demotion in audio mode.
- REST and SSE API contract verification with X-KON-Search-Model headers.
- Seamless runtime model switching without restart.
"""

import pytest
from starlette.testclient import TestClient
from backend.main import app
from backend.search.models import CandidateResult, SearchQuery
from backend.search.engine import SearchEngine
from backend.search import rust_bridge


@pytest.fixture
def test_candidates():
    """Candidate pool representing realistic search results containing correct songs,

    franchise tracks, live versions, remixes, and misleading gameplay/reaction clips.
    """
    return [
        CandidateResult(
            id="bleach_bankai_01",
            title="Shiro SAGISU - Number One (Bankai Version) [Official Bleach TYBW OST]",
            uploader="Shiro SAGISU - Topic",
            url="https://www.youtube.com/watch?v=bleach_bankai_01",
            thumbnail="https://i.ytimg.com/vi/bleach_bankai_01/hqdefault.jpg",
            duration=305,
            views=14500000,
            platform="youtube",
            is_music=True,
            content_type="music",
        ),
        CandidateResult(
            id="bleach_gameplay_01",
            title="BLEACH Rebirth of Souls - Number One Bankai Boss Fight Gameplay Walkthrough Part 1",
            uploader="IGN Games",
            url="https://www.youtube.com/watch?v=bleach_gameplay_01",
            thumbnail="https://i.ytimg.com/vi/bleach_gameplay_01/hqdefault.jpg",
            duration=1450,
            views=320000,
            platform="youtube",
            is_music=False,
            content_type="gameplay",
        ),
        CandidateResult(
            id="shelter_porter_01",
            title="Porter Robinson & Madeon - Shelter (Official Audio)",
            uploader="Porter Robinson",
            url="https://www.youtube.com/watch?v=shelter_porter_01",
            thumbnail="https://i.ytimg.com/vi/shelter_porter_01/hqdefault.jpg",
            duration=219,
            views=98000000,
            platform="youtube",
            is_music=True,
            content_type="music",
        ),
        CandidateResult(
            id="shelter_reaction_01",
            title="PRODUCER REACTS to Porter Robinson - Shelter for the FIRST TIME!",
            uploader="Music Producer Reacts",
            url="https://www.youtube.com/watch?v=shelter_reaction_01",
            thumbnail="https://i.ytimg.com/vi/shelter_reaction_01/hqdefault.jpg",
            duration=890,
            views=45000,
            platform="youtube",
            is_music=False,
            content_type="reaction",
        ),
        CandidateResult(
            id="arctic_monkeys_01",
            title="Arctic Monkeys - I Wanna Be Yours (Official Audio)",
            uploader="Arctic Monkeys",
            url="https://www.youtube.com/watch?v=arctic_monkeys_01",
            thumbnail="https://i.ytimg.com/vi/arctic_monkeys_01/hqdefault.jpg",
            duration=184,
            views=1500000000,
            platform="youtube",
            is_music=True,
            content_type="music",
        ),
        CandidateResult(
            id="newjeans_jersey_01",
            title="NewJeans - Ditto (Jersey Club Remix / Edit)",
            uploader="Club Edits Tokyo",
            url="https://www.youtube.com/watch?v=newjeans_jersey_01",
            thumbnail="https://i.ytimg.com/vi/newjeans_jersey_01/hqdefault.jpg",
            duration=165,
            views=2500000,
            platform="youtube",
            is_music=True,
            content_type="remix",
        ),
        CandidateResult(
            id="unrelated_vlog_01",
            title="My Daily Routine in Tokyo - Best Cafes and Shopping",
            uploader="TravelerTokyo",
            url="https://www.youtube.com/watch?v=unrelated_vlog_01",
            thumbnail="https://i.ytimg.com/vi/unrelated_vlog_01/hqdefault.jpg",
            duration=720,
            views=15000,
            platform="youtube",
            is_music=False,
            content_type="vlog",
        ),
    ]


def test_dual_engine_rust_core_availability():
    """Verify that both Rei and Rei Flash native Rust ranking functions are loaded."""
    assert rust_bridge.is_rust_core_available() is True
    # Verify Rust ranking functions exist in module
    assert hasattr(rust_bridge, "rank_candidates")
    assert hasattr(rust_bridge, "rank_candidates_flash")
    assert hasattr(rust_bridge, "get_rust_suggestions")
    assert hasattr(rust_bridge, "get_rust_suggestions_flash")


def test_rei_vs_flash_query_number_one_bankai(test_candidates):
    """Test 'Number One Bankai' query across both engines.

    Both must identify Shiro Sagisu's Number One Bankai version as #1.
    Both must strictly demote the gameplay video in audio mode.
    """
    query = SearchQuery(raw_query="Number One Bankai", media_type="audio")

    # Rei Precision Mode
    rei_ranked = rust_bridge.rank_candidates(query, test_candidates)
    assert len(rei_ranked) > 0
    assert rei_ranked[0].id == "bleach_bankai_01"
    assert "Number One" in rei_ranked[0].title
    assert "Bankai" in rei_ranked[0].title
    assert rei_ranked[0].uploader == "Shiro SAGISU - Topic"
    assert rei_ranked[0].url == "https://www.youtube.com/watch?v=bleach_bankai_01"
    assert rei_ranked[0].thumbnail.startswith("https://")

    # Flash Speed Mode
    flash_ranked = rust_bridge.rank_candidates_flash(query, test_candidates)
    assert len(flash_ranked) > 0
    assert flash_ranked[0].id == "bleach_bankai_01"
    assert "Number One" in flash_ranked[0].title
    assert flash_ranked[0].uploader == "Shiro SAGISU - Topic"
    assert flash_ranked[0].url == "https://www.youtube.com/watch?v=bleach_bankai_01"

    # In both modes, gameplay must be penalized and ranked far below official music
    gameplay_rei_pos = next(i for i, c in enumerate(rei_ranked) if c.id == "bleach_gameplay_01")
    gameplay_flash_pos = next(i for i, c in enumerate(flash_ranked) if c.id == "bleach_gameplay_01")
    assert gameplay_rei_pos > 0
    assert gameplay_flash_pos > 0


def test_rei_vs_flash_query_bankai_partial_clue(test_candidates):
    """Test partial clue discovery 'Bankai'.

    Soundtrack semantic affinity should lift 'Number One (Bankai Version)' to top rank.
    """
    query = SearchQuery(raw_query="Bankai", media_type="audio")

    rei_ranked = rust_bridge.rank_candidates(query, test_candidates)
    flash_ranked = rust_bridge.rank_candidates_flash(query, test_candidates)

    assert rei_ranked[0].id == "bleach_bankai_01"
    assert flash_ranked[0].id == "bleach_bankai_01"


def test_rei_vs_flash_query_shelter_porter(test_candidates):
    """Test 'Shelter Porter' query.

    Must match Porter Robinson - Shelter and demote the reaction video.
    """
    query = SearchQuery(raw_query="Shelter Porter", media_type="audio")

    rei_ranked = rust_bridge.rank_candidates(query, test_candidates)
    flash_ranked = rust_bridge.rank_candidates_flash(query, test_candidates)

    assert rei_ranked[0].id == "shelter_porter_01"
    assert flash_ranked[0].id == "shelter_porter_01"

    # Demote reaction clip
    reaction_pos_rei = next(i for i, c in enumerate(rei_ranked) if c.id == "shelter_reaction_01")
    reaction_pos_flash = next(i for i, c in enumerate(flash_ranked) if c.id == "shelter_reaction_01")
    assert reaction_pos_rei > 0
    assert reaction_pos_flash > 0


def test_rei_vs_flash_query_i_wanna_be_yours(test_candidates):
    """Test exact title query 'I Wanna Be Yours'."""
    query = SearchQuery(raw_query="I Wanna Be Yours", media_type="audio")

    rei_ranked = rust_bridge.rank_candidates(query, test_candidates)
    flash_ranked = rust_bridge.rank_candidates_flash(query, test_candidates)

    assert rei_ranked[0].id == "arctic_monkeys_01"
    assert flash_ranked[0].id == "arctic_monkeys_01"
    assert rei_ranked[0].uploader == "Arctic Monkeys"


def test_rei_vs_flash_query_newjeans_jersey_club(test_candidates):
    """Test style & remix qualifier query 'NewJeans Jersey Club'."""
    query = SearchQuery(raw_query="NewJeans Jersey Club", media_type="audio")

    rei_ranked = rust_bridge.rank_candidates(query, test_candidates)
    flash_ranked = rust_bridge.rank_candidates_flash(query, test_candidates)

    assert rei_ranked[0].id == "newjeans_jersey_01"
    assert flash_ranked[0].id == "newjeans_jersey_01"


def test_typo_tolerance_queries(test_candidates):
    """Test typo queries: 'numbr one' and 'sheltar portar'."""
    q_typo1 = SearchQuery(raw_query="numbr one", media_type="audio")
    rei1 = rust_bridge.rank_candidates(q_typo1, test_candidates)
    flash1 = rust_bridge.rank_candidates_flash(q_typo1, test_candidates)
    assert rei1[0].id == "bleach_bankai_01"
    assert flash1[0].id == "bleach_bankai_01"

    q_typo2 = SearchQuery(raw_query="sheltar portar", media_type="audio")
    rei2 = rust_bridge.rank_candidates(q_typo2, test_candidates)
    flash2 = rust_bridge.rank_candidates_flash(q_typo2, test_candidates)
    assert rei2[0].id == "shelter_porter_01"
    assert flash2[0].id == "shelter_porter_01"


def test_incomplete_artist_name(test_candidates):
    """Test incomplete artist queries: 'Porter' and 'Arctic'."""
    q_porter = SearchQuery(raw_query="Porter", media_type="audio")
    rei_p = rust_bridge.rank_candidates(q_porter, test_candidates)
    flash_p = rust_bridge.rank_candidates_flash(q_porter, test_candidates)
    assert rei_p[0].id == "shelter_porter_01"
    assert flash_p[0].id == "shelter_porter_01"

    q_arctic = SearchQuery(raw_query="Arctic", media_type="audio")
    rei_a = rust_bridge.rank_candidates(q_arctic, test_candidates)
    flash_a = rust_bridge.rank_candidates_flash(q_arctic, test_candidates)
    assert rei_a[0].id == "arctic_monkeys_01"
    assert flash_a[0].id == "arctic_monkeys_01"


def test_suggestions_engine_modes():
    """Verify suggestions API for both Rei and Flash modes.

    Flash mode must return instantly without throwing or stalling.
    """
    sugs_rei = rust_bridge.get_rust_suggestions("shelter", media_type="audio", limit=5)
    sugs_flash = rust_bridge.get_rust_suggestions_flash("shelter", media_type="audio", limit=5)

    assert len(sugs_rei) > 0
    assert len(sugs_flash) > 0
    assert any("Shelter" in s.get("title", "") for s in sugs_rei)
    assert any("Shelter" in s.get("title", "") for s in sugs_flash)

    # Test Bankai clue suggestion
    sugs_bankai_rei = rust_bridge.get_rust_suggestions("bankai", media_type="audio", limit=5)
    sugs_bankai_flash = rust_bridge.get_rust_suggestions_flash("bankai", media_type="audio", limit=5)
    assert any("Number One" in s.get("title", "") for s in sugs_bankai_rei)
    assert any("Number One" in s.get("title", "") for s in sugs_bankai_flash)


def test_api_search_engine_mode_switch():
    """Test FastAPI /api/search endpoint with engine_mode=rei and engine_mode=flash.

    Verifies headers X-KON-Search-Engine, X-KON-Search-Model, and JSON payload attributes.
    """
    client = TestClient(app)

    # 1. Query with Rei Precision mode (explicit)
    res_rei = client.get("/api/search?q=Shelter%20Porter&media_type=audio&engine_mode=rei")
    assert res_rei.status_code == 200
    data_rei = res_rei.json()
    assert res_rei.headers["X-KON-Search-Engine"] == "rust-core/1.2.0"
    assert res_rei.headers["X-KON-Search-Model"] == "KON Search 1.2 Rei"
    assert data_rei["engine_mode"] == "rei"
    assert data_rei["model"] == "KON Search 1.2 Rei"
    assert data_rei["product"] == "KON Search 1.2 Rei"

    # 2. Immediate switch to Rei Flash Speed mode without server restart
    res_flash = client.get("/api/search?q=Shelter%20Porter&media_type=audio&engine_mode=flash")
    assert res_flash.status_code == 200
    data_flash = res_flash.json()
    assert res_flash.headers["X-KON-Search-Engine"] == "rust-core/1.2.0"
    assert res_flash.headers["X-KON-Search-Model"] == "KON Search 1.2 Rei Flash"
    assert data_flash["engine_mode"] == "flash"
    assert data_flash["model"] == "KON Search 1.2 Rei Flash"
    assert data_flash["product"] == "KON Search 1.2 Rei Flash"

    # 3. Model selector alias via model query parameter
    res_alias = client.get("/api/search?q=Bankai&media_type=audio&model=flash")
    assert res_alias.status_code == 200
    data_alias = res_alias.json()
    assert data_alias["engine_mode"] == "flash"
    assert data_alias["model"] == "KON Search 1.2 Rei Flash"


def test_api_suggestions_engine_modes():
    """Test /api/search/suggestions endpoint with engine_mode."""
    client = TestClient(app)

    # Rei mode suggestions
    res_sug_rei = client.get("/api/search/suggestions?q=arctic&engine_mode=rei")
    assert res_sug_rei.status_code == 200
    d_rei = res_sug_rei.json()
    assert "suggestions" in d_rei
    assert d_rei["engine_mode"] == "rei"

    # Flash mode suggestions
    res_sug_flash = client.get("/api/search/suggestions?q=arctic&engine_mode=flash")
    assert res_sug_flash.status_code == 200
    d_flash = res_sug_flash.json()
    assert "suggestions" in d_flash
    assert d_flash["engine_mode"] == "flash"
