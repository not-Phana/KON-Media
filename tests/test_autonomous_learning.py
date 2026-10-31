"""Test Suite for KON Search 1.2 Rei & Rei Flash Continuous Autonomous Learning System:
- Phase 2: Learning Data Collector & Weighted Consensus Scoring
- Phase 3 & 6: Autonomous Training Pipeline, SGD, and Strict Benchmark Isolation
- Phase 4: Autonomous Evaluator, NDCG@10, MRR, Latency & Gatekeeper Promotion Policy
- Phase 5: Model Version Manager, Atomic Promotion, and 1-Click Rollback
- Phase 7: Background Learning Scheduler Lifecycle & Controls
- Phase 8: Search Engine Live Learned Scoring Bridge & Latency Budgets
- Phase 9 & REST API: Full Endpoint Contracts & Telemetry
"""

import os
import json
import time
import pytest
from pathlib import Path
from starlette.testclient import TestClient

from backend.main import app
from backend.search.learning.data_collector import LearningDataCollector
from backend.search.learning.model_manager import ModelVersionManager
from backend.search.learning.evaluator import AutonomousEvaluator, compute_dcg, compute_ndcg
from backend.search.benchmark.dataset import HELD_OUT_QUERIES
from backend.search.learning.autonomous_pipeline import AutonomousTrainingPipeline
from backend.search.learning.scheduler import LearningScheduler
from backend.search.learning_model import SearchLearningModel
from backend.search.engine import SearchEngine
from backend.search.models import CandidateResult


@pytest.fixture
def temp_learning_env(tmp_path):
    """Isolated environment fixture for learning models, storage, and benchmarks."""
    collector = LearningDataCollector(state_dir=tmp_path)
    manager = ModelVersionManager(state_dir=tmp_path)
    pipeline = AutonomousTrainingPipeline(state_dir=tmp_path)
    evaluator = AutonomousEvaluator()
    scheduler = LearningScheduler(pipeline=pipeline, check_interval_seconds=60)
    
    return {
        "tmp_path": tmp_path,
        "collector": collector,
        "manager": manager,
        "pipeline": pipeline,
        "evaluator": evaluator,
        "scheduler": scheduler,
    }


# ============================================================================
# Phase 2: Data Collector & Consensus Scoring Tests
# ============================================================================

def test_collector_records_positive_signals(temp_learning_env):
    """Verify collector records positive signals (preview, listen, favorite, download)."""
    collector = temp_learning_env["collector"]

    # 1. Preview signal
    e1 = collector.record_event(
        query="yoasobi idol",
        candidate_id="yt_123",
        candidate_title="YOASOBI - Idol Official Music Video",
        event_type="preview",
        engine_mode="rei",
    )
    assert e1 is not None
    assert e1["label"] == 1.0
    assert e1["weight"] >= 0.8

    # 2. Listen signal with dwell time (>30s)
    e2 = collector.record_event(
        query="yoasobi idol",
        candidate_id="yt_123",
        candidate_title="YOASOBI - Idol Official Music Video",
        event_type="listen",
        listen_duration=45.0,
        track_duration=210.0,
        engine_mode="rei",
    )
    assert e2["label"] == 1.0
    assert e2["weight"] >= 1.0

    # 3. Favorite signal
    e3 = collector.record_event(
        query="yoasobi idol",
        candidate_id="yt_123",
        candidate_title="YOASOBI - Idol Official Music Video",
        event_type="favorite",
        engine_mode="rei",
    )
    assert e3["label"] == 1.0
    assert e3["weight"] >= 1.0

    # 4. Download signal (strongest positive signal)
    e4 = collector.record_event(
        query="yoasobi idol",
        candidate_id="yt_123",
        candidate_title="YOASOBI - Idol Official Music Video",
        event_type="download",
        engine_mode="rei",
    )
    assert e4["label"] == 1.0
    assert e4["weight"] >= 1.0

    # Verify consensus aggregation
    clean_examples = collector.get_clean_training_examples()
    assert len(clean_examples) >= 1
    q, title, consensus_label, tot_w = clean_examples[0]
    assert q == "yoasobi idol"
    assert consensus_label == 1.0
    assert tot_w >= 3.0


def test_collector_records_negative_signals_and_suppression(temp_learning_env):
    """Verify collector records negative signals (quick skip, mismatch) and suppresses noise."""
    collector = temp_learning_env["collector"]

    # Explicit mismatch report
    e_mis = collector.record_event(
        query="bleach number one",
        candidate_id="bad_1",
        candidate_title="Random Roblox Gameplay",
        event_type="mismatch",
        reason="Not the music track",
    )
    assert e_mis["label"] == 0.0
    assert e_mis["weight"] >= 1.0

    # Short skip on rank 1 (< 5 seconds)
    e_skip = collector.record_event(
        query="bleach number one",
        candidate_id="bad_1",
        candidate_title="Random Roblox Gameplay",
        event_type="skip",
        listen_duration=2.5,
        position_rank=1,
    )
    assert e_skip["label"] == 0.0

    # Long skip on rank 10 (>5 seconds) should be ignored as non-negative
    e_neutral = collector.record_event(
        query="bleach number one",
        candidate_id="ok_1",
        candidate_title="Bleach Soundtrack",
        event_type="skip",
        listen_duration=25.0,
        position_rank=10,
    )
    assert e_neutral is None


def test_collector_controls_toggle_and_clear(temp_learning_env):
    """Verify toggle disable, clear, and export on data collector."""
    collector = temp_learning_env["collector"]

    collector.record_event(
        query="test query",
        candidate_id="test_id",
        candidate_title="Test Title",
        event_type="select",
    )
    assert len(collector.get_all()) == 1

    # Disable collector
    collector.set_enabled(False)
    assert collector.is_enabled is False

    # Event while disabled must be rejected
    e_disabled = collector.record_event(
        query="test query 2",
        candidate_id="test_id_2",
        candidate_title="Test Title 2",
        event_type="select",
    )
    assert e_disabled is None
    assert len(collector.get_all()) == 1

    # Export
    exp = collector.export_data()
    assert exp["count"] == 1
    assert len(exp["interactions"]) == 1

    # Re-enable and clear
    collector.set_enabled(True)
    collector.clear()
    assert len(collector.get_all()) == 0


# ============================================================================
# Phase 3 & 4: Dataset Assembly & Strict Benchmark Isolation
# ============================================================================

def test_dataset_assembly_and_benchmark_isolation(temp_learning_env):
    """Verify training dataset assembly and strictly prevent leakage of held-out benchmark queries."""
    pipeline = temp_learning_env["pipeline"]
    collector = temp_learning_env["collector"]

    # Seed an interaction
    collector.record_event(
        query="yoasobi idol anime oshi no ko",
        candidate_id="yoasobi_1",
        candidate_title="YOASOBI Idol Theme",
        event_type="download",
    )

    train_data, val_data = pipeline.assemble_dataset()
    assert len(train_data) > 0
    assert len(val_data) > 0

    # Strict isolation check: NONE of the benchmark queries should appear in train or val data
    benchmark_queries = {item["query"].lower().strip() for item in HELD_OUT_QUERIES}
    for query, title, label in train_data:
        assert query.lower().strip() not in benchmark_queries, f"Test leak detected! Query '{query}' in training set."
    for query, title, label in val_data:
        assert query.lower().strip() not in benchmark_queries, f"Test leak detected! Query '{query}' in validation set."


def test_train_candidate_model_updates_weights(temp_learning_env):
    """Verify candidate training updates model weights via SGD without crashing."""
    pipeline = temp_learning_env["pipeline"]
    base_model = SearchLearningModel(state_dir=temp_learning_env["tmp_path"])
    train_set, _ = pipeline.assemble_dataset()

    candidate = pipeline.train_candidate(base_model, train_set[:20], epochs=2)
    assert candidate is not None
    assert len(candidate.associations) >= len(base_model.associations)


# ============================================================================
# Phase 4: Autonomous Evaluation & Gatekeeper Policy
# ============================================================================

def test_autonomous_evaluator_and_gatekeeper_decision(temp_learning_env):
    """Verify evaluator benchmarks candidate vs production and computes NDCG@10, MRR, P@5."""
    evaluator = temp_learning_env["evaluator"]
    prod_model = SearchLearningModel(state_dir=temp_learning_env["tmp_path"])
    cand_model = SearchLearningModel(state_dir=temp_learning_env["tmp_path"])

    # Evaluate candidate vs production
    eval_results = evaluator.compare_models(cand_model, prod_model)

    assert "candidate_rei" in eval_results
    assert "production_rei" in eval_results
    assert "candidate_flash" in eval_results
    assert "production_flash" in eval_results
    assert "decision" in eval_results
    assert "should_promote" in eval_results

    # Check metrics
    for mode in ("candidate_rei", "candidate_flash"):
        m = eval_results[mode]
        assert "ndcg10" in m
        assert "mrr" in m
        assert "p5" in m
        assert "latency_ms" in m
        assert m["ndcg10"] >= 0.0
        assert m["mrr"] >= 0.0

    # Rei Flash latency budget (< 8.0ms)
    assert eval_results["candidate_flash"]["latency_ms"] < 8.0, "Rei Flash exceeded 8.0ms latency threshold!"


def test_gatekeeper_rejects_intentionally_degraded_model(temp_learning_env):
    """Verify Gatekeeper rejects a degraded model that regresses performance."""
    evaluator = temp_learning_env["evaluator"]
    prod_model = SearchLearningModel(state_dir=temp_learning_env["tmp_path"])
    
    # Degraded candidate
    bad_model = SearchLearningModel(state_dir=temp_learning_env["tmp_path"])
    bad_model.weights = {"semantic_embedding": -5.0}  # Inverse weighting degrades ranking

    eval_results = evaluator.compare_models(bad_model, prod_model)

    assert eval_results["decision"] == "REJECT"
    assert eval_results["should_promote"] is False
    assert len(eval_results["rejection_reasons"]) > 0


# ============================================================================
# Phase 5: Safe Version Manager, Atomic Writes & Rollback
# ============================================================================

def test_model_version_manager_promotion_and_rollback(temp_learning_env):
    """Verify version manager saves candidate, increments version on promotion, and rolls back."""
    manager = temp_learning_env["manager"]

    initial_version = manager.get_active_version()
    assert initial_version == "v1.2.0"

    cand_model = SearchLearningModel(state_dir=temp_learning_env["tmp_path"])
    metrics = {"ndcg10": 0.96, "mrr": 0.98, "composite_score": 0.97}

    # Save candidate
    cand_version = manager.save_candidate_model(cand_model, metrics=metrics)
    assert cand_version == "v1.2.1"

    # Promote candidate to production
    promoted = manager.promote_candidate(cand_version)
    assert promoted is True
    assert manager.get_active_version() == "v1.2.1"

    # Roll back
    restored = manager.rollback()
    assert restored == "v1.2.0"
    assert manager.get_active_version() == "v1.2.0"


# ============================================================================
# Phase 7 & 8: Live Search Engine Learned Scoring Bridge & Latency
# ============================================================================

def test_engine_learned_scoring_bridge(temp_learning_env):
    """Verify SearchEngine applies learned scoring to boost confirmed music candidates."""
    model = SearchLearningModel(state_dir=temp_learning_env["tmp_path"])
    model.associations["bleach number one"] = {"bleach ost - number one": 2.5}
    engine = SearchEngine(learning_model=model)

    c1 = CandidateResult(
        id="c1",
        title="Bleach OST - Number One (Hazel Fernandes Official Audio)",
        url="https://youtube.com/watch?v=111",
        platform="youtube",
        score=0.75,
    )
    c2 = CandidateResult(
        id="c2",
        title="Bleach Anime Reaction & Gameplay Commentary Ep 1",
        url="https://youtube.com/watch?v=222",
        platform="youtube",
        score=0.74,
    )

    ranked = [c2, c1]
    boosted = engine._apply_learning_model("bleach number one", ranked)

    assert boosted[0].id == "c1"
    assert boosted[0].score > boosted[1].score


def test_scoring_latency_under_budgets(temp_learning_env):
    """Verify latency constraints for candidate ranking scoring bridge."""
    engine = SearchEngine()
    candidates = [
        CandidateResult(
            id=f"cand_{i}",
            title=f"Sample Track Title {i} Official Audio",
            url=f"https://example.com/{i}",
            platform="youtube",
            score=0.5,
        )
        for i in range(20)
    ]

    t0 = time.perf_counter()
    engine._apply_learning_model("sample query", candidates)
    latency_ms = (time.perf_counter() - t0) * 1000.0

    assert latency_ms < 5.0, f"Learned scoring latency was {latency_ms:.2f}ms (target <5.0ms)"


# ============================================================================
# Phase 9: Learning REST API Endpoints Contract
# ============================================================================

def test_learning_api_endpoints():
    """Verify REST API contracts for telemetry, event recording, scheduler, and rollback."""
    client = TestClient(app)

    # 1. Telemetry
    res = client.get("/api/learning/telemetry")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert "active_model_version" in data
    assert "collector_stats" in data

    # 2. Record event
    event_payload = {
        "query": "yoasobi idol",
        "candidate_id": "test_endpoint_1",
        "candidate_title": "YOASOBI - Idol Official Theme",
        "event_type": "preview",
        "candidate_url": "https://example.com/test",
        "engine_mode": "rei",
    }
    res_ev = client.post("/api/learning/event", json=event_payload)
    assert res_ev.status_code == 200
    assert res_ev.json()["status"] == "ok"
    assert res_ev.json()["recorded"] is True

    # 3. Pause & Resume scheduler
    res_pause = client.post("/api/learning/scheduler/pause")
    assert res_pause.status_code == 200
    assert res_pause.json()["is_paused"] is True
    assert res_pause.json()["status"] == "paused"

    res_resume = client.post("/api/learning/scheduler/resume")
    assert res_resume.status_code == 200
    assert res_resume.json()["is_paused"] is False
    assert res_resume.json()["status"] == "resumed"

    # 4. Collector toggle
    res_tog = client.post("/api/learning/collector/toggle", json={"enabled": True})
    assert res_tog.status_code == 200
    assert res_tog.json()["is_enabled"] is True
