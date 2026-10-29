"""Automated Test Suite for KON Search 1 Rei ML Architecture and Google Drive Storage Adapter."""

import json
from pathlib import Path
import pytest
from kon_search.dataset_factory import DatasetFactory, introduce_realistic_typos
from kon_search.features.extractor import RankingFeatureExtractor
from kon_search.gdrive.auth import GoogleDriveAuthManager
from kon_search.gdrive.mock_client import MockGoogleDriveAdapter
from kon_search.loop.experiment_loop import BoundedImprovementLoop
from kon_search.models.baseline import LexicalBaselineRanker
from kon_search.models.evaluation import SearchEvaluator, dcg_at_k, mrr_score, ndcg_at_k, precision_at_k, recall_at_k
from kon_search.models.persistence import ModelPersistenceManager
from kon_search.models.ranker_rei1 import KONSearch1ReiModel
from kon_search.schema import CandidateRecord, LabeledExample, ProvenanceType, QueryRecord, RelevanceGrade
from kon_search.validation import DatasetValidator


def test_schema_and_relevance_grades():
    q = QueryRecord(query_id="q1", raw_query="Titanic", normalized_query="titanic", media_type="audio")
    c = CandidateRecord(candidate_id="c1", title="Celine Dion - My Heart Will Go On", artist_or_uploader="Celine Dion")
    ex = LabeledExample(
        example_id="ex1",
        query=q,
        candidate=c,
        grade=RelevanceGrade.EXACT_MATCH,
        provenance=ProvenanceType.VERIFIED_CANONICAL,
        group_id="cluster_titanic",
    )
    d = ex.to_dict()
    assert d["grade"] == 3
    assert d["provenance"] == "verified_canonical"

    restored = LabeledExample.from_dict(d)
    assert restored.grade == RelevanceGrade.EXACT_MATCH
    assert restored.query.raw_query == "Titanic"


def test_dataset_factory_and_validation():
    factory = DatasetFactory()
    assert len(factory.raw_records) > 0

    pilot = factory.generate_pilot_dataset(target_clusters=10)
    assert len(pilot) > 50

    validator = DatasetValidator()
    clean = validator.validate_and_deduplicate_batch(pilot)
    assert len(clean) > 0
    assert len(clean) <= len(pilot)

    # Verify all records conform to schema
    for ex in clean:
        valid, reason = validator.validate_example(ex)
        assert valid, f"Validation failed: {reason}"


def test_zero_leakage_group_split():
    factory = DatasetFactory()
    examples = factory.generate_pilot_dataset(target_clusters=25)
    validator = DatasetValidator()
    clean = validator.validate_and_deduplicate_batch(examples)

    train, val, test = validator.split_by_group(clean, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15)
    assert len(train) > 0
    assert len(val) > 0
    assert len(test) > 0

    train_groups = set(ex.group_id for ex in train)
    val_groups = set(ex.group_id for ex in val)
    test_groups = set(ex.group_id for ex in test)

    # Strictly disjoint group sets
    assert len(train_groups & val_groups) == 0
    assert len(train_groups & test_groups) == 0
    assert len(val_groups & test_groups) == 0


def test_feature_extractor_values():
    extractor = RankingFeatureExtractor()
    q = QueryRecord(query_id="q1", raw_query="Titanic", normalized_query="titanic", media_type="audio")
    c_song = CandidateRecord(candidate_id="c1", title="Celine Dion - My Heart Will Go On", artist_or_uploader="Celine Dion", media_type="audio")
    c_clip = CandidateRecord(candidate_id="c2", title="Titanic 1997 Movie Clip Ending Scene", artist_or_uploader="Film Vault", media_type="video")

    feats_song = extractor.extract_features(q, c_song)
    feats_clip = extractor.extract_features(q, c_clip)

    assert feats_song["media_type_audio_match"] == 1.0
    assert feats_song["non_music_clip_penalty"] == 0.0

    assert feats_clip["non_music_clip_penalty"] == 1.0
    assert feats_clip["exact_title_match"] == 1.0  # Word 'titanic' appears, but clip penalty flags it


def test_lexical_baseline_and_ml_model_training(tmp_path):
    factory = DatasetFactory()
    raw = factory.generate_pilot_dataset(target_clusters=20)
    validator = DatasetValidator()
    clean = validator.validate_and_deduplicate_batch(raw)
    train, val, test = validator.split_by_group(clean, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15)

    # 1. Baseline
    baseline = LexicalBaselineRanker()
    corpus = [ex.query.raw_query for ex in train] + [ex.candidate.title for ex in train]
    baseline.fit(corpus)

    # 2. ML Model
    model = KONSearch1ReiModel(max_iter=60, random_state=42)
    model.fit(train, val_examples=val)
    assert model.is_trained
    assert model.metadata is not None

    # Predict test candidate
    test_q = test[0].query
    test_c = test[0].candidate
    score = model.predict_score(test_q, test_c)
    assert 0.0 <= score <= 3.0

    # 3. Evaluation
    evaluator = SearchEvaluator()
    comparison = evaluator.compare_models(baseline, model, test)
    assert "baseline" in comparison
    assert "kon_search_1_rei" in comparison
    assert "delta" in comparison
    assert comparison["kon_search_1_rei"]["latency_ms"] < 25.0


def test_model_persistence(tmp_path):
    factory = DatasetFactory()
    raw = factory.generate_pilot_dataset(target_clusters=15)
    validator = DatasetValidator()
    clean = validator.validate_and_deduplicate_batch(raw)
    train, _, _ = validator.split_by_group(clean)

    model = KONSearch1ReiModel(max_iter=40, random_state=42)
    model.fit(train)

    persistence = ModelPersistenceManager(models_dir=tmp_path)
    model_file, meta_file, checksum = persistence.save_model(model, version_tag="1.0.0-test")

    assert model_file.exists()
    assert meta_file.exists()
    assert len(checksum) == 64

    # Load and test inference
    loaded_model, loaded_meta = persistence.load_model(version_tag="1.0.0-test")
    assert loaded_model.is_trained
    assert loaded_meta["artifact_filename"] == "kon_search_1_rei.joblib"

    score = loaded_model.predict_score(train[0].query, train[0].candidate)
    assert 0.0 <= score <= 3.0


def test_mock_gdrive_adapter_upload_download(tmp_path):
    mock_drive = MockGoogleDriveAdapter()
    hierarchy = mock_drive.ensure_rei1_hierarchy()
    assert "datasets" in hierarchy
    assert "manifests" in hierarchy

    test_file = tmp_path / "test_data.json"
    test_file.write_text(json.dumps({"test": "value"}), encoding="utf-8")

    # Upload
    upload_res = mock_drive.upload_file(test_file, remote_subfolder="datasets")
    assert upload_res["status"] == "uploaded"
    assert upload_res["name"] == "test_data.json"
    file_id = upload_res["file_id"]

    # Duplicate detection check
    dup_res = mock_drive.upload_file(test_file, remote_subfolder="datasets")
    assert dup_res["status"] == "cached"
    assert dup_res["file_id"] == file_id

    # Download and verify sha256
    download_dest = tmp_path / "downloaded_test.json"
    mock_drive.download_file(file_id, download_dest)
    assert download_dest.exists()
    assert json.loads(download_dest.read_text(encoding="utf-8")) == {"test": "value"}


def test_mock_gdrive_network_failure_simulation(tmp_path):
    mock_drive = MockGoogleDriveAdapter(simulate_network_failure=True, fail_on_attempt=1)
    test_file = tmp_path / "fail_test.json"
    test_file.write_text("content", encoding="utf-8")

    with pytest.raises(ConnectionResetError):
        mock_drive.upload_file(test_file, remote_subfolder="datasets")


def test_gdrive_auth_manager_safe_reporting(tmp_path):
    auth_mgr = GoogleDriveAuthManager(credentials_dir=tmp_path)
    status = auth_mgr.get_auth_status()
    assert status["authenticated"] is False
    assert status["has_client_secrets"] is False
    assert status["has_token"] is False

    # Calling get_credentials(interactive=False) safely returns explanation without error
    creds, err = auth_mgr.get_credentials(interactive=False)
    assert creds is None
    assert "Missing OAuth client credentials" in err


def test_gitignore_security_rules():
    gitignore_path = Path(__file__).resolve().parent.parent / ".gitignore"
    assert gitignore_path.exists()
    content = gitignore_path.read_text(encoding="utf-8")

    # Verify secret patterns are strictly excluded
    assert "*credentials*.json" in content
    assert "*token*.json" in content
    assert ".gdrive_credentials/" in content
    assert "*.env" in content
    assert "*.secret" in content


def test_bounded_improvement_loop_bounds(tmp_path):
    factory = DatasetFactory()
    raw = factory.generate_pilot_dataset(target_clusters=20)
    validator = DatasetValidator()
    clean = validator.validate_and_deduplicate_batch(raw)
    train, val, test = validator.split_by_group(clean)

    initial_model = KONSearch1ReiModel(max_iter=30, random_state=42)
    initial_model.fit(train)

    loop = BoundedImprovementLoop(max_iterations=2, min_ndcg_gain=0.001)
    best_model, summary = loop.run_loop(initial_model, train, val, test)

    assert summary["iterations_executed"] <= 2
    assert "final_metrics" in summary
    assert "history" in summary
