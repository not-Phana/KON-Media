"""Complete Pipeline Runner for KON Search 1 Rei.

Executes:
1. Dataset Factory Generation (Pilot & Expanded Labeled Data)
2. Quality Validation & Group-Based Leakage-Free Splitting
3. Local Manifest & Checksum Generation
4. Google Drive Integration (Uploads manifests & datasets to private layout)
5. Lexical Baseline vs KON Search 1 Rei ML Training
6. Multi-Metric Evaluation (NDCG@10, MRR, P@5, Recall@10, Latency)
7. Bounded Self-Improvement Loop (max 3 iterations)
8. Artifact Persistence & Release-Readiness Certification
"""

import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("run_rei1_pipeline")

from kon_search.dataset_factory import DatasetFactory
from kon_search.validation import DatasetValidator
from kon_search.features.extractor import RankingFeatureExtractor
from kon_search.models.baseline import LexicalBaselineRanker
from kon_search.models.ranker_rei1 import KONSearch1ReiModel
from kon_search.models.evaluation import SearchEvaluator
from kon_search.models.persistence import ModelPersistenceManager
from kon_search.loop.experiment_loop import BoundedImprovementLoop
from kon_search.gdrive.auth import GoogleDriveAuthManager
from kon_search.gdrive.client import GoogleDriveClient
from kon_search.gdrive.mock_client import MockGoogleDriveAdapter


def run_pipeline() -> Dict[str, Any]:
    log.info("================================================================================")
    log.info("KON Search 1 Rei - Complete ML Training, Dataset Factory & Storage Pipeline")
    log.info("================================================================================")

    t_start = time.time()
    data_dir = PROJECT_ROOT / "data" / "datasets" / "rei1"
    data_dir.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # STAGE 1: Dataset Generation
    # -------------------------------------------------------------------------
    log.info("\n--- STAGE 1: DATASET GENERATION ---")
    factory = DatasetFactory()
    raw_examples = factory.generate_expanded_dataset(target_clusters=120)
    log.info("Generated %d raw labeled examples across canonical clusters.", len(raw_examples))

    # -------------------------------------------------------------------------
    # STAGE 2: Validation, Deduplication & Leakage-Free Group Splitting
    # -------------------------------------------------------------------------
    log.info("\n--- STAGE 2: QUALITY VALIDATION & SPLITTING ---")
    validator = DatasetValidator()
    clean_examples = validator.validate_and_deduplicate_batch(raw_examples)
    rejections = dict(validator.rejection_reasons)
    log.info("Validated examples: %d (Rejections: %s)", len(clean_examples), rejections)

    train_data, val_data, test_data = validator.split_by_group(
        clean_examples, train_ratio=0.70, val_ratio=0.15, test_ratio=0.15, seed=42
    )
    log.info("Split partitions: Train=%d, Val=%d, Test=%d (Zero Group Overlap)", len(train_data), len(val_data), len(test_data))

    timestamp_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    manifest = validator.build_manifest(
        dataset_version="v1.0.0",
        train_data=train_data,
        val_data=val_data,
        test_data=test_data,
        created_at=timestamp_str,
        extra_metadata={"model_target": "KON Search 1 Rei"},
    )

    # Save local versioned files
    dataset_file = data_dir / "rei1_dataset_v1.0.0.json"
    manifest_file = data_dir / "manifest_v1.0.0.json"

    with open(dataset_file, "w", encoding="utf-8") as f:
        json.dump([ex.to_dict() for ex in clean_examples], f, indent=2)

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest.to_dict(), f, indent=2)

    log.info("Saved local dataset to: %s (%d bytes)", dataset_file, dataset_file.stat().st_size)
    log.info("Saved manifest to: %s (SHA256: %s)", manifest_file, manifest.sha256_checksum)

    # -------------------------------------------------------------------------
    # STAGE 3: Google Drive Sync & Storage Layout Verification
    # -------------------------------------------------------------------------
    log.info("\n--- STAGE 3: GOOGLE DRIVE STORAGE ADAPTER ---")
    auth_mgr = GoogleDriveAuthManager()
    auth_status = auth_mgr.get_auth_status()
    log.info("Auth Status: %s", auth_status)

    gdrive_report: Dict[str, Any] = {
        "status": "unauthenticated",
        "real_upload_succeeded": False,
        "mock_upload_succeeded": False,
        "client_secrets_found": auth_status["has_client_secrets"],
        "token_found": auth_status["has_token"],
    }

    # Test with Mock Adapter first to verify layout & checksum logic
    mock_drive = MockGoogleDriveAdapter()
    mock_drive.ensure_rei1_hierarchy()
    mock_upload = mock_drive.upload_file(dataset_file, remote_subfolder="datasets")
    mock_manifest_upload = mock_drive.upload_file(manifest_file, remote_subfolder="manifests")
    gdrive_report["mock_upload_succeeded"] = bool(mock_upload.get("file_id"))
    log.info("Verified Drive layout & chunked upload on Mock Drive: %s", mock_upload)

    if auth_status["authenticated"]:
        try:
            real_drive = GoogleDriveClient(auth_manager=auth_mgr)
            real_drive.ensure_rei1_hierarchy()
            real_res = real_drive.upload_file(dataset_file, remote_subfolder="datasets")
            real_drive.upload_file(manifest_file, remote_subfolder="manifests")
            gdrive_report["status"] = "connected"
            gdrive_report["real_upload_succeeded"] = True
            gdrive_report["real_file_id"] = real_res.get("file_id")
            log.info("Successfully uploaded dataset to real Google Drive! File ID: %s", real_res.get("file_id"))
        except Exception as e:
            log.warning("Real Google Drive upload failed or expired: %s", e)
            gdrive_report["status"] = f"error: {e}"
    else:
        log.info("Google Drive requires interactive browser authorization. OAuth client ready in kon_search/gdrive/.")

    # -------------------------------------------------------------------------
    # STAGE 4: Baseline vs Initial Model Training
    # -------------------------------------------------------------------------
    log.info("\n--- STAGE 4: BASELINE & MODEL TRAINING ---")
    # 1. Lexical Baseline
    baseline = LexicalBaselineRanker()
    all_train_corpus = [ex.query.raw_query for ex in train_data] + [ex.candidate.title for ex in train_data]
    baseline.fit(all_train_corpus)

    # 2. KON Search 1 Rei Initial Model
    initial_model = KONSearch1ReiModel(
        learning_rate=0.08,
        max_iter=120,
        max_depth=5,
        random_state=42,
    )
    initial_model.fit(
        train_examples=train_data,
        val_examples=val_data,
        dataset_version=manifest.dataset_version,
        dataset_sha256=manifest.sha256_checksum,
    )

    # -------------------------------------------------------------------------
    # STAGE 5: Fair Comparative Evaluation on Held-Out Test Set
    # -------------------------------------------------------------------------
    log.info("\n--- STAGE 5: FAIR EVALUATION ON FIXED HELD-OUT TEST SET ---")
    evaluator = SearchEvaluator()
    comparison_initial = evaluator.compare_models(baseline, initial_model, test_data)
    log.info("Baseline Metrics: %s", comparison_initial["baseline"])
    log.info("Initial Rei 1 Metrics: %s", comparison_initial["kon_search_1_rei"])
    log.info("Delta Gains: %s", comparison_initial["delta"])

    # -------------------------------------------------------------------------
    # STAGE 6: Bounded Improvement Loop (Max 3 iterations)
    # -------------------------------------------------------------------------
    log.info("\n--- STAGE 6: BOUNDED IMPROVEMENT LOOP ---")
    loop = BoundedImprovementLoop(max_iterations=3, min_ndcg_gain=0.003, max_latency_ms=15.0)
    best_model, loop_summary = loop.run_loop(
        initial_model=initial_model,
        initial_train_data=train_data,
        val_data=val_data,
        fixed_test_data=test_data,
    )

    # Final evaluation against baseline
    final_comparison = evaluator.compare_models(baseline, best_model, test_data)
    feature_importances = best_model.compute_feature_importances(test_data)
    log.info("Final Comparison: %s", final_comparison)
    log.info("Top Feature Importances: %s", list(feature_importances.items())[:5])

    # -------------------------------------------------------------------------
    # STAGE 7: Model Artifact Persistence & Checkpoint
    # -------------------------------------------------------------------------
    log.info("\n--- STAGE 7: MODEL PERSISTENCE ---")
    persistence = ModelPersistenceManager()
    best_model.metadata.metrics_baseline = final_comparison["baseline"]
    best_model.metadata.metrics_model = final_comparison["kon_search_1_rei"]
    best_model.metadata.status = final_comparison["acceptance_decision"].lower()

    model_path, meta_path, model_sha256 = persistence.save_model(
        best_model, version_tag="1.0.0", metadata=best_model.metadata
    )

    # Upload checkpoint to Drive (Mock and Real if authenticated)
    mock_drive.upload_file(model_path, remote_subfolder="checkpoints")
    mock_drive.upload_file(meta_path, remote_subfolder="manifests")
    if gdrive_report["real_upload_succeeded"]:
        try:
            real_drive = GoogleDriveClient(auth_manager=auth_mgr)
            real_drive.upload_file(model_path, remote_subfolder="checkpoints")
            real_drive.upload_file(meta_path, remote_subfolder="manifests")
        except Exception:
            pass

    total_pipeline_time = round(time.time() - t_start, 2)
    log.info("Pipeline completed in %.2fs.", total_pipeline_time)

    # -------------------------------------------------------------------------
    # STAGE 8: Build Comprehensive Release Report
    # -------------------------------------------------------------------------
    release_report = {
        "model_name": "KON Search 1 Rei",
        "model_version": "1.0.0",
        "pipeline_duration_seconds": total_pipeline_time,
        "dataset": {
            "version": manifest.dataset_version,
            "sha256": manifest.sha256_checksum,
            "raw_examples": len(raw_examples),
            "valid_examples": len(clean_examples),
            "train_samples": len(train_data),
            "val_samples": len(val_data),
            "test_samples": len(test_data),
            "grade_distribution": manifest.grade_distribution,
            "rejections": rejections,
            "local_path": str(dataset_file),
        },
        "gdrive_storage": gdrive_report,
        "metrics": {
            "baseline": final_comparison["baseline"],
            "kon_search_1_rei": final_comparison["kon_search_1_rei"],
            "delta": final_comparison["delta"],
            "decision": final_comparison["acceptance_decision"],
        },
        "improvement_loop": loop_summary,
        "feature_importances": feature_importances,
        "artifacts": {
            "model_joblib": str(model_path),
            "metadata_json": str(meta_path),
            "model_sha256": model_sha256,
        },
    }

    report_path = data_dir / "release_report_rei1.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(release_report, f, indent=2)

    log.info("Saved release report to: %s", report_path)
    return release_report


if __name__ == "__main__":
    run_pipeline()
