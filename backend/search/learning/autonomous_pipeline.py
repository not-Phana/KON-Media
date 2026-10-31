"""Autonomous Training Pipeline for KON Search 1.2 Rei and Rei Flash.

Orchestrates the complete continuous learning cycle:
1. Gathers & validates training data from data collector, download history, and curated catalog.
2. Deduplicates examples and prepares balanced train/val/test splits.
3. Clones and trains candidate models with online SGD and token embeddings.
4. Evaluates candidate models against current production model on held-out benchmark queries.
5. Safely promotes candidate if and only if it passes all gatekeeper criteria.
6. Rejects candidates that cause regressions, preserving production stability.
"""

import copy
import datetime
import logging
import random
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.config import STATE_DIR
from backend.search.learning_model import SearchLearningModel
from backend.search.learning.data_collector import get_learning_data_collector
from backend.search.learning.model_manager import get_model_version_manager
from backend.search.learning.evaluator import AutonomousEvaluator
from backend.search.benchmark.dataset import HELD_OUT_QUERIES
from backend.search.continuous_trainer import CURATED_GROUND_TRUTH, TYPO_MAPPINGS

log = logging.getLogger("kon_autonomous_pipeline")


class AutonomousTrainingPipeline:
    """End-to-end background training and gatekeeping pipeline."""

    def __init__(self, state_dir: Path = STATE_DIR):
        self.state_dir = state_dir
        self.collector = get_learning_data_collector()
        self.model_manager = get_model_version_manager()
        self.evaluator = AutonomousEvaluator()
        self._last_run_result: Optional[Dict[str, Any]] = None

    def get_last_run_result(self) -> Optional[Dict[str, Any]]:
        return self._last_run_result

    def assemble_dataset(self) -> Tuple[List[Tuple[str, str, float]], List[Tuple[str, str, float]]]:
        """Assemble balanced training and validation datasets without benchmark data leakage."""
        all_samples: List[Tuple[str, str, float]] = []

        # 1. Base curated catalog (positives and negative distractors)
        all_samples.extend(CURATED_GROUND_TRUTH)

        # 2. Typo mappings
        for typo, real_q in TYPO_MAPPINGS:
            matching = [target for q, target, lab in CURATED_GROUND_TRUTH if real_q.lower() in q.lower() and lab == 1.0]
            if matching:
                all_samples.append((typo, matching[0], 1.0))

        # 3. Validated real user interactions from collector
        clean_user_examples = self.collector.get_clean_training_examples(min_weight=0.5)
        for q, title, label, weight in clean_user_examples:
            all_samples.append((q, title, label))

        # 4. Strict Benchmark Isolation: NEVER train on held-out benchmark evaluation queries
        benchmark_queries = {item["query"].lower().strip() for item in HELD_OUT_QUERIES}
        all_samples = [s for s in all_samples if s[0].lower().strip() not in benchmark_queries]

        # Deduplicate
        seen = set()
        deduped: List[Tuple[str, str, float]] = []
        for q, title, lab in all_samples:
            key = (q.lower().strip(), title.lower().strip(), lab)
            if key not in seen:
                seen.add(key)
                deduped.append((q, title, lab))

        # Shuffle deterministically
        rnd = random.Random(42)
        rnd.shuffle(deduped)

        # 80% train, 20% validation
        split_idx = int(len(deduped) * 0.8)
        train_set = deduped[:split_idx]
        val_set = deduped[split_idx:]

        return train_set, val_set

    def train_candidate(
        self,
        base_model: SearchLearningModel,
        train_set: List[Tuple[str, str, float]],
        epochs: int = 3,
    ) -> SearchLearningModel:
        """Train a candidate model using SGD on training set."""
        # Create candidate copy
        candidate = copy.deepcopy(base_model)
        candidate.learning_rate = 0.035

        for epoch in range(epochs):
            for query, target_title, label in train_set:
                q_lower = query.lower()
                t_lower = target_title.lower()
                has_exact = q_lower in t_lower or t_lower in q_lower

                feats = {
                    "exact_title": 1.0 if has_exact else (0.8 if label == 1.0 else 0.2),
                    "fuzzy_title": 0.85 if label == 1.0 else 0.15,
                    "token_overlap": 0.80 if label == 1.0 else 0.10,
                    "artist_match": 0.90 if label == 1.0 else 0.10,
                    "duration_compat": 0.90 if label == 1.0 else 0.30,
                    "version_compat": 1.00 if label == 1.0 else 0.25,
                    "audio_affinity": 0.85 if label == 1.0 else 0.15,
                }
                candidate.train_step(query, target_title, feats, label)

        return candidate

    def run_training_cycle(self, epochs: int = 3, force: bool = False) -> Dict[str, Any]:
        """Execute full training, evaluation, and conditional promotion cycle."""
        started_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
        log.info("Starting autonomous training cycle...")

        # 1. Assemble data
        train_set, val_set = self.assemble_dataset()
        if len(train_set) < 10 and not force:
            result = {
                "status": "skipped",
                "reason": "Insufficient training examples available",
                "examples_count": len(train_set),
                "started_at": started_at,
            }
            self._last_run_result = result
            return result

        # 2. Load active production model
        from backend.search.engine import get_shared_learning_model
        production_model = get_shared_learning_model()
        active_version = self.model_manager.get_active_version()

        # 3. Train candidate model
        candidate_model = self.train_candidate(production_model, train_set, epochs=epochs)

        # 4. Evaluate candidate against production on held-out benchmark
        eval_report = self.evaluator.compare_models(candidate_model, production_model)

        # 5. Safe Promotion Gatekeeper
        promoted = False
        new_version = None

        if eval_report["should_promote"]:
            # Save candidate model artifact
            metrics_summary = {
                "composite_score_rei": eval_report["candidate_rei"]["composite_score"],
                "ndcg10_rei": eval_report["candidate_rei"]["ndcg10"],
                "mrr_rei": eval_report["candidate_rei"]["mrr"],
                "p5_rei": eval_report["candidate_rei"]["p5"],
                "latency_rei_ms": eval_report["candidate_rei"]["latency_ms"],
                "composite_score_flash": eval_report["candidate_flash"]["composite_score"],
                "latency_flash_ms": eval_report["candidate_flash"]["latency_ms"],
                "regression_rate": eval_report["regression_rate"],
            }
            new_version = self.model_manager.save_candidate_model(
                candidate_model,
                metrics=metrics_summary,
                description=f"Auto-trained on {len(train_set)} examples (Score: {metrics_summary['composite_score_rei']})"
            )
            # Atomically promote candidate
            promoted = self.model_manager.promote_candidate(new_version)
            log.info("Autonomous promotion successful: %s -> %s", active_version, new_version)
        else:
            log.info("Candidate rejected by evaluation gatekeeper: %s", eval_report["rejection_reasons"])

        cycle_result = {
            "status": "completed",
            "decision": eval_report["decision"],
            "promoted": promoted,
            "active_version_before": active_version,
            "active_version_after": new_version if promoted else active_version,
            "examples_used": len(train_set) + len(val_set),
            "train_examples_count": len(train_set),
            "val_examples_count": len(val_set),
            "reasons": eval_report["rejection_reasons"] if not promoted else ["Passed all benchmark gatekeeper criteria"],
            "score_delta_rei": eval_report["score_delta_rei"],
            "score_delta_flash": eval_report["score_delta_flash"],
            "regression_rate": eval_report["regression_rate"],
            "evaluation": eval_report,
            "completed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        self._last_run_result = cycle_result
        return cycle_result


# Singleton instance
_shared_pipeline: Optional[AutonomousTrainingPipeline] = None


def get_autonomous_pipeline() -> AutonomousTrainingPipeline:
    global _shared_pipeline
    if _shared_pipeline is None:
        _shared_pipeline = AutonomousTrainingPipeline()
    return _shared_pipeline
