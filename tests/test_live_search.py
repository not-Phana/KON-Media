"""Tests for KON Search 1.1.0 Rei Live Search, query intent, word order, and streaming events."""

import json
import pytest
from httpx import AsyncClient, ASGITransport

from backend.main import app
from backend.search.models import CandidateResult, SearchQuery
from backend.search.normalization import parse_query_intent, detect_version_hint
from backend.search.relevance_engine import (
    compute_word_order_score,
    extract_features,
    score_candidate,
    deduplicate_candidates,
)
from backend.search.engine import SearchEngine


def test_required_query_intent_examples():
    """Verify query understanding on all required user regression examples."""
    # 1. Exact title query
    q1 = parse_query_intent("I Wanna Be Yours")
    assert q1.detected_title == "I Wanna Be Yours"
    assert q1.detected_artist is None
    assert q1.version_hint is None

    # 2. Title and artist combined query
    q2 = parse_query_intent("I Wanna Be Yours Arctic Monkeys")
    assert q2.detected_title == "I Wanna Be Yours"
    assert q2.detected_artist == "Arctic Monkeys"

    # 3. Artist, title, and version label in parenthetical
    q3 = parse_query_intent("NewJeans - Jersey Club (Version)")
    assert q3.detected_artist == "NewJeans"
    assert q3.detected_title == "Jersey Club"
    assert q3.version_hint == "remix"
    assert q3.qualifier == "jersey club"
    assert q3.edition == "version"

    # 4. Soundtrack / franchise query
    q4 = parse_query_intent("Number One - Bankai")
    assert q4.detected_artist == "Number One"
    assert q4.detected_title == "Bankai"

    # 5. Multi-artist collaborative title
    q5 = parse_query_intent("Shelter Porter Robinson Madeon")
    assert q5.detected_title == "Shelter"
    assert q5.detected_artist == "Porter Robinson Madeon"

    # 6. Title with trailing live qualifier
    q6 = parse_query_intent("Bohemian Rhapsody live")
    assert q6.detected_title == "Bohemian Rhapsody"
    assert q6.version_hint == "live"

    # 7. Title with trailing remix qualifier
    q7 = parse_query_intent("Blinding Lights remix")
    assert q7.detected_title == "Blinding Lights"
    assert q7.version_hint == "remix"


def test_word_order_scoring():
    """Word order score must reward preserved token order and penalize scrambled order."""
    query_tokens = ["i", "wanna", "be", "yours"]

    # Perfect order
    cand_perfect = ["arctic", "monkeys", "i", "wanna", "be", "yours", "official"]
    score_perfect = compute_word_order_score(query_tokens, cand_perfect)
    assert score_perfect == 1.0

    # Inverted order: "yours be wanna i"
    cand_inverted = ["yours", "be", "wanna", "i"]
    score_inverted = compute_word_order_score(query_tokens, cand_inverted)
    assert score_inverted == 0.0

    # Partial / scrambled order: "wanna i yours be"
    cand_scrambled = ["wanna", "i", "yours", "be"]
    score_scrambled = compute_word_order_score(query_tokens, cand_scrambled)
    assert score_scrambled < 0.70


def test_metadata_quality_feature():
    """Candidates with complete metadata must receive higher metadata quality scores."""
    query = parse_query_intent("Daft Punk - Get Lucky")

    cand_complete = CandidateResult(
        id="c1",
        title="Daft Punk - Get Lucky (Official Audio)",
        uploader="DaftPunkVEVO",
        duration=248.0,
        thumbnail="https://i.ytimg.com/vi/5NV6Rdv1a3I/hqdefault.jpg",
    )
    feat_complete = extract_features(query, cand_complete)
    assert feat_complete["metadata_quality"] >= 0.85

    cand_sparse = CandidateResult(
        id="c2",
        title="Daft Punk - Get Lucky",
        uploader="",
        duration=None,
        thumbnail="",
    )
    feat_sparse = extract_features(query, cand_sparse)
    assert feat_sparse["metadata_quality"] < 0.60


def test_version_and_platform_aware_deduplication():
    """Deduplication must never collapse distinct versions or distinct platforms."""
    candidates = [
        # Same URL duplicate
        CandidateResult(id="1", title="Shelter", uploader="Madeon", url="https://www.youtube.com/watch?v=123", platform="youtube", duration=219.0),
        CandidateResult(id="2", title="Shelter", uploader="Madeon", url="https://youtu.be/123", platform="youtube", duration=219.0),

        # Distinct platform (SoundCloud)
        CandidateResult(id="3", title="Shelter", uploader="Madeon", url="https://soundcloud.com/madeon/shelter", platform="soundcloud", duration=219.0),

        # Distinct version (Remix)
        CandidateResult(id="4", title="Shelter (Remix)", uploader="Madeon", url="https://www.youtube.com/watch?v=456", platform="youtube", duration=240.0),
    ]

    deduped = deduplicate_candidates(candidates)
    assert len(deduped) == 3
    # ID 2 should be eliminated as duplicate of ID 1
    ids = [c.id for c in deduped]
    assert "1" in ids
    assert "2" not in ids
    assert "3" in ids
    assert "4" in ids


@pytest.mark.asyncio
async def test_search_live_sse_streaming_stages():
    """Verify /api/search/live streams authentic SSE events including understanding, searching, and completed."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        async with client.stream("GET", "/api/search/live?q=Queen%20Bohemian%20Rhapsody&limit=5") as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers["content-type"]
            assert resp.headers.get("X-KON-Search-Engine") is not None

            stages_received = []
            results_received = []

            async for line in resp.aiter_lines():
                line = line.strip()
                if line.startswith("data: "):
                    event = json.loads(line[6:])
                    stage = event.get("stage")
                    stages_received.append(stage)
                    if "results" in event:
                        results_received = event["results"]

            assert "understanding" in stages_received
            assert "searching" in stages_received
            assert any(s in ("completed", "partial_results", "updating") for s in stages_received)
            assert len(results_received) > 0
