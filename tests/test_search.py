"""Comprehensive tests for KON Media search engine, normalization, multi-signal ranking, and feedback."""

import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, MagicMock
from backend.main import app
from backend.search.models import CandidateResult, RankerConfig, SearchQuery
from backend.search.normalization import (
    normalize_text,
    strip_media_noise,
    detect_version_hint,
    parse_query_intent,
    ngram_similarity,
    token_overlap_ratio,
)
from backend.search.ranking import (
    rank_candidates,
    score_artist_affinity,
    score_version_compatibility,
    score_duration_compatibility,
)
from backend.search.feedback import SearchFeedbackStore, tune_weights_on_evidence
from backend.search.engine import SearchEngine


def test_normalization_and_unicode_handling():
    # Accented Latin diacritics
    assert normalize_text("ROSALÍA - DESPECHÁ") == "rosalia despecha"
    # Preserves Japanese characters
    assert normalize_text("宇多田ヒカル First Love") == "宇多田ヒカル first love"
    # Strips media noise
    raw = "Queen - Bohemian Rhapsody [Official Music Video HD Remastered]"
    cleaned = strip_media_noise(raw)
    assert "[Official Music Video HD Remastered]" not in cleaned
    assert "Bohemian Rhapsody" in cleaned


def test_query_intent_and_version_detection():
    # Detects version hints
    q_remix = parse_query_intent("The Weeknd Blinding Lights Chromatics remix")
    assert q_remix.version_hint == "remix"

    q_live = parse_query_intent("Queen Bohemian Rhapsody Live Aid 1985")
    assert q_live.version_hint == "live"

    q_inst = parse_query_intent("Daft Punk Get Lucky instrumental")
    assert q_inst.version_hint == "instrumental"

    # Detects artist - title split
    q_split = parse_query_intent("Eminem - Lose Yourself")
    assert q_split.detected_artist == "Eminem"
    assert q_split.detected_title == "Lose Yourself"


def test_typo_tolerance_and_ngram_similarity():
    # Incomplete & misspelled queries
    sim_3g = ngram_similarity("bohemain rhapsdy", "bohemian rhapsody", n=3)
    assert sim_3g > 0.35

    sim_2g = ngram_similarity("bohemain rhapsdy", "bohemian rhapsody", n=2)
    assert sim_2g > 0.50

    overlap = token_overlap_ratio("blindin lites weeknd", "the weeknd blinding lights")
    assert overlap >= 0.33


def test_ranking_parody_penalty_and_artist_affinity():
    query = parse_query_intent("Daft Punk Get Lucky")
    candidates = [
        CandidateResult(id="parody", title="Daft Punk - Get Lucky Minecraft Parody", uploader="BlockTunes", duration=240.0),
        CandidateResult(id="official", title="Daft Punk - Get Lucky (Official Audio)", uploader="DaftPunkVEVO", duration=248.0),
    ]

    ranked = rank_candidates(query, candidates)
    # The official release must rank above the parody
    assert ranked[0].id == "official"
    assert ranked[0].score > ranked[1].score
    assert ranked[0].confidence == "high"


def test_ranking_version_match_when_remix_requested():
    query = parse_query_intent("The Weeknd Blinding Lights Chromatics remix")
    candidates = [
        CandidateResult(id="studio", title="The Weeknd - Blinding Lights (Official Audio)", uploader="TheWeekndVEVO", duration=202.0),
        CandidateResult(id="chromatics", title="The Weeknd - Blinding Lights (Chromatics Remix)", uploader="TheWeekndVEVO", duration=261.0),
    ]

    ranked = rank_candidates(query, candidates)
    # The remix must rank above the studio version because remix was explicitly requested
    assert ranked[0].id == "chromatics"
    assert ranked[0].score > ranked[1].score


def test_feedback_store_and_verified_match_boost(tmp_path):
    store = SearchFeedbackStore(state_dir=tmp_path)
    store.record_selection(
        query="Queen Bohemian Rhapsody Live",
        selected_id="live_wembley",
        selected_title="Queen - Bohemian Rhapsody (Live at Wembley)",
        selected_url="https://youtube.com/watch?v=sample1",
        is_mismatch=False,
    )

    lookup = store.get_verified_lookup()
    assert lookup.get("queen bohemian rhapsody live") == "live_wembley"

    # Verify ranker utilizes feedback lookup to boost the verified item
    query = parse_query_intent("Queen Bohemian Rhapsody Live")
    candidates = [
        CandidateResult(id="live_other", title="Queen - Bohemian Rhapsody (Live at Montreal)", uploader="Queen Official"),
        CandidateResult(id="live_wembley", title="Queen - Bohemian Rhapsody (Live at Wembley)", uploader="Queen Official"),
    ]

    ranked = rank_candidates(query, candidates, feedback_lookup=lookup)
    assert ranked[0].id == "live_wembley"
    assert "Verified user match from historical feedback" in ranked[0].explanation


def test_evidence_driven_weight_tuning():
    from backend.search.benchmark.dataset import TUNING_QUERIES

    best_cfg, best_mrr = tune_weights_on_evidence(
        TUNING_QUERIES[:5],
        lambda q, c, cfg: rank_candidates(parse_query_intent(q.raw_query), c, cfg),
    )
    assert isinstance(best_cfg, RankerConfig)
    assert best_mrr > 0.0


@pytest.mark.asyncio
async def test_api_search_endpoint_validation_and_results():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Empty query returns 400
        resp = await client.get("/api/search?q=")
        assert resp.status_code == 400

        # Valid query returns structured candidates
        mock_candidates = [
            CandidateResult(id="mock_1", title="Mock Queen Song", uploader="Queen", duration=200.0, url="https://youtube.com/watch?v=mock1"),
        ]
        with patch.object(SearchEngine, "search", return_value=[mock_candidates[0].to_dict()]):
            resp = await client.get("/api/search?q=Queen")
            assert resp.status_code == 200
            data = resp.json()
            assert data["query"] == "Queen"
            assert data["count"] == 1
            assert data["results"][0]["id"] == "mock_1"


@pytest.mark.asyncio
async def test_api_search_feedback_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "query": "Rick Astley Never Gonna Give You Up",
            "selected_id": "yt_rick_astley",
            "selected_title": "Rick Astley - Never Gonna Give You Up",
            "selected_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "is_mismatch": False,
            "provider": "youtube",
        }
        resp = await client.post("/api/search/feedback", json=payload)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "recorded"
        assert data["entry"]["selected_id"] == "yt_rick_astley"


def test_search_learning_model_online_sgd_and_associations(tmp_path):
    from backend.search.learning_model import SearchLearningModel

    model = SearchLearningModel(state_dir=tmp_path)
    initial_stats = model.get_stats()
    assert initial_stats["total_updates"] == 0

    # Step 1: Positive feedback pair training
    feats = {
        "exact_title": 0.5,
        "fuzzy_title": 0.4,
        "token_overlap": 0.3,
        "artist_match": 0.8,
        "duration_compat": 0.9,
        "version_compat": 1.0,
        "audio_affinity": 0.8,
    }
    loss_pos = model.train_step("titanic", "Celine Dion - My Heart Will Go On", feats, label=1.0)
    assert loss_pos > 0.0
    assert model.metadata["total_updates"] == 1
    assert "titanic" in model.associations
    assert "heart" in model.associations["titanic"]
    assert model.associations["titanic"]["heart"] > 0.0

    # Step 2: Negative feedback mismatch penalty
    loss_neg = model.train_step("titanic", "Random Meme Parody", feats, label=0.0)
    assert loss_neg > 0.0
    assert model.metadata["total_updates"] == 2

    # Step 3: Semantic similarity calculation
    sim_match = model.compute_semantic_similarity("titanic", "Celine Dion - My Heart Will Go On")
    assert sim_match > 0.4

    # Step 4: Batch self-training over feedback and history
    feedback_entries = [
        {"query": "cyberpunk song", "selected_title": "Rosa Walton - I Really Want to Stay at Your House", "is_mismatch": False},
        {"query": "cyberpunk song", "selected_title": "Fake Documentary Trailer", "is_mismatch": True},
    ]
    download_history = [
        {"title": "Daft Punk - Get Lucky (Official Audio)"},
        {"title": "Queen - Bohemian Rhapsody (Official Video)"},
    ]
    train_res = model.self_train(feedback_entries, download_history, epochs=3)
    assert train_res["status"] == "trained"
    assert train_res["epochs"] == 3
    assert train_res["total_steps"] > 0
    assert model.metadata["training_epochs"] >= 3

    # Step 5: Test persistence and reload
    reloaded_model = SearchLearningModel(state_dir=tmp_path)
    assert reloaded_model.metadata["training_epochs"] == model.metadata["training_epochs"]
    assert "cyberpunk" in reloaded_model.associations


def test_ranking_integration_with_learning_model(tmp_path):
    from backend.search.learning_model import SearchLearningModel

    model = SearchLearningModel(state_dir=tmp_path)
    # Train the model to associate "space cowboy" with "Jamiroquai"
    feats = {"exact_title": 0.5, "artist_match": 0.8, "duration_compat": 0.9, "version_compat": 1.0, "audio_affinity": 0.8}
    for _ in range(5):
        model.train_step("space cowboy", "Jamiroquai - Space Cowboy", feats, label=1.0)

    query = parse_query_intent("space cowboy")
    candidates = [
        CandidateResult(id="unrelated", title="How to Be an Astronaut - Documentary", uploader="NASA"),
        CandidateResult(id="match", title="Jamiroquai - Space Cowboy (Remastered)", uploader="Jamiroquai"),
    ]

    ranked = rank_candidates(query, candidates, learning_model=model)
    assert ranked[0].id == "match"
    assert ranked[0].score > ranked[1].score
    assert "semantic_similarity" in ranked[0].features


@pytest.mark.asyncio
async def test_api_search_train_and_model_stats_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check GET /api/search/model-stats
        resp = await client.get("/api/search/model-stats")
        assert resp.status_code == 200
        stats = resp.json()
        assert "weights" in stats
        assert "learned_tokens_count" in stats

        # Check POST /api/search/train
        train_resp = await client.post("/api/search/train", json={"epochs": 2})
        assert train_resp.status_code == 200
        train_data = train_resp.json()
        assert train_data["status"] in ("trained", "no_data")


def test_doc_learner_parsing_and_training(tmp_path):
    from backend.search.learning_model import SearchLearningModel
    from backend.search.doc_learner import DocumentLearner, parse_knowledge_pairs

    content = """
    # Google Doc Notes
    Titanic -> Celine Dion - My Heart Will Go On
    Interstellar: Hans Zimmer - Cornfield Chase
    | Film | Song Title | Artist |
    | Cyberpunk 2077 | I Really Want to Stay at Your House | Rosa Walton |
    Bohemian Rhapsody by Queen
    """
    pairs = parse_knowledge_pairs(content)
    assert len(pairs) >= 4

    model = SearchLearningModel(state_dir=tmp_path)
    learner = DocumentLearner(model=model)
    res = learner.learn_from_text(content, epochs=3, source_name="Test Doc")
    assert res["status"] == "success"
    assert res["extracted_count"] >= 4
    assert "titanic" in model.associations
    assert "heart" in model.associations["titanic"]


@pytest.mark.asyncio
async def test_api_learn_from_doc_and_gdrive_status_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Check GET /api/search/gdrive-status
        status_resp = await client.get("/api/search/gdrive-status")
        assert status_resp.status_code == 200
        status_data = status_resp.json()
        assert "gdrive_installed" in status_data
        assert "authenticated" in status_data

        # Check POST /api/search/learn-doc with valid content
        doc_payload = {
            "content": "Gladiator -> Hans Zimmer - Now We Are Free\nInception: Hans Zimmer - Time",
            "epochs": 2,
        }
        learn_resp = await client.post("/api/search/learn-doc", json=doc_payload)
        assert learn_resp.status_code == 200
        learn_data = learn_resp.json()
        assert learn_data["status"] == "success"
        assert learn_data["extracted_count"] == 2

        # Check POST /api/search/learn-doc with empty content
        empty_resp = await client.post("/api/search/learn-doc", json={"content": ""})
        assert empty_resp.status_code == 400


def test_search_cache_lru_and_ttl_speed():
    import time
    from backend.search.cache import SearchCache

    cache = SearchCache(max_size=3, default_ttl_seconds=10.0)
    assert cache.get_stats()["size"] == 0

    key1 = cache.make_key("titanic", media_type="audio")
    key2 = cache.make_key("interstellar", media_type="audio")
    key3 = cache.make_key("cyberpunk", media_type="audio")
    key4 = cache.make_key("naruto", media_type="audio")

    cache.set(key1, [{"id": "1", "title": "Titanic Song"}])
    cache.set(key2, [{"id": "2", "title": "Cornfield Chase"}])
    cache.set(key3, [{"id": "3", "title": "Stay at Your House"}])

    assert cache.get_stats()["size"] == 3

    # Benchmark sub-millisecond retrieval
    t0 = time.perf_counter()
    res = cache.get(key1)
    dt = time.perf_counter() - t0
    assert res is not None
    assert res[0]["title"] == "Titanic Song"
    assert dt < 0.005  # Must be faster than 5 milliseconds (typically < 0.05ms)

    # Eviction test: adding key4 evicts key2 (since key1 was accessed most recently)
    cache.set(key4, [{"id": "4", "title": "Blue Bird"}])
    assert cache.get_stats()["size"] == 3
    assert cache.get(key2) is None  # Evicted
    assert cache.get(key1) is not None  # Kept


def test_normalize_media_url_preserves_identifiers():
    from backend.search.providers import normalize_media_url

    yt_url1 = "https://www.youtube.com/watch?v=dQw4w9WgXcQ&t=10s&ab_channel=RickAstley"
    yt_url2 = "https://www.youtube.com/watch?v=L_LUpnjgPso"
    sc_url = "https://soundcloud.com/artist/song?in=playlist"

    assert normalize_media_url(yt_url1) == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    assert normalize_media_url(yt_url2) == "https://www.youtube.com/watch?v=L_LUpnjgPso"
    assert normalize_media_url(sc_url) == "https://soundcloud.com/artist/song"


def test_song_mode_clip_suppression_and_neural_ranking():
    from backend.search.models import SearchQuery, CandidateResult
    from backend.search.ranking import rank_candidates
    from backend.search.learning_model import SearchLearningModel

    model = SearchLearningModel()

    q = SearchQuery(raw_query="Titanic", media_type="audio")
    candidates = [
        CandidateResult(id="1", title="Titanic Movie Clip 1997 HD (Full Scene)", duration=180),
        CandidateResult(id="2", title="Celine Dion - My Heart Will Go On (Official Music Video)", duration=280),
        CandidateResult(id="3", title="Titanic Ship Disaster Documentary Review", duration=1200),
    ]

    ranked = rank_candidates(q, candidates, learning_model=model)
    assert len(ranked) == 3
    # Song must be ranked #1
    assert ranked[0].id == "2"
    assert "Celine Dion" in ranked[0].title
    assert ranked[0].score > ranked[1].score
    # Movie clip and documentary must have version mismatch penalties
    assert any("penalty" in exp.lower() for exp in ranked[1].explanation)
    assert any("penalty" in exp.lower() for exp in ranked[2].explanation)


def test_expanded_knowledge_association_coverage():
    from backend.search.learning_model import SearchLearningModel

    model = SearchLearningModel()
    # Check that model has loaded associations across diverse domains
    stats = model.get_stats()
    assert stats["associations_count"] >= 3000

    test_queries = {
        "jujutsu kaisen": ["eve", "kaikai", "specialz", "king", "gnu"],
        "doom": ["mick", "gordon", "bfg", "division"],
        "queen": ["bohemian", "rhapsody"],
        "undertale": ["toby", "fox", "megalovania", "hopes"],
        "interstellar": ["hans", "zimmer", "cornfield", "chase"],
    }

    for query, expected_tokens in test_queries.items():
        tokens = model.get_associated_tokens(query, top_k=8)
        assert any(t in tokens for t in expected_tokens), f"Failed to associate {query} with {expected_tokens}, got {tokens}"

