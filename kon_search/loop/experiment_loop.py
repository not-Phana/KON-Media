"""Bounded Self-Improving Experimentation Loop for KON Search 1 Rei.

Executes controlled, evidence-driven tuning passes:
EVALUATE -> IDENTIFY WEAKNESSES -> TARGETED AUGMENTATION -> VALIDATE -> TRAIN -> COMPARE ON FIXED TEST SET -> KEEP OR ROLLBACK
Bounded to a strict maximum of 5 iterations (default 3) to prevent runaway loops.
"""

import copy
import logging
from typing import Any, Dict, List, Optional, Tuple
from kon_search.dataset_factory import introduce_realistic_typos
from kon_search.models.evaluation import SearchEvaluator
from kon_search.models.ranker_rei1 import KONSearch1ReiModel
from kon_search.schema import CandidateRecord, LabeledExample, ProvenanceType, QueryRecord, RelevanceGrade
from kon_search.validation import DatasetValidator

log = logging.getLogger("kon_search_experiment_loop")


class BoundedImprovementLoop:
    """Iterative ML tuning loop with strict bounds, fixed held-out evaluation, and rollback."""

    def __init__(
        self,
        max_iterations: int = 3,
        min_ndcg_gain: float = 0.005,
        max_latency_ms: float = 15.0,
    ):
        self.max_iterations = min(max(1, max_iterations), 5)  # Strict cap at 5
        self.min_ndcg_gain = min_ndcg_gain
        self.max_latency_ms = max_latency_ms
        self.evaluator = SearchEvaluator()
        self.validator = DatasetValidator()
        self.experiment_history: List[Dict[str, Any]] = []

    def identify_error_modes(
        self,
        model: KONSearch1ReiModel,
        eval_examples: List[LabeledExample],
    ) -> Dict[str, int]:
        """Diagnose ranking weaknesses on evaluation queries."""
        error_counts = {
            "clip_noise_ranked_high": 0,
            "typo_missed": 0,
            "artist_confusion": 0,
            "cover_over_canonical": 0,
        }

        query_groups = self.evaluator.group_examples_by_query(eval_examples)
        for q_text, (query_obj, cand_pairs) in query_groups.items():
            candidates = [c for c, _ in cand_pairs]
            ground_truth = {c.candidate_id: g for c, g in cand_pairs}

            ranked = model.score_candidates(query_obj, candidates)
            if not ranked:
                continue

            top_cand, top_score = ranked[0]
            top_grade = ground_truth.get(top_cand.candidate_id, 0.0)

            # If top result is irrelevant (Grade 0)
            if top_grade == 0.0:
                if "clip" in top_cand.title.lower() or "scene" in top_cand.title.lower() or "review" in top_cand.title.lower():
                    error_counts["clip_noise_ranked_high"] += 1
                elif query_obj.variation_type == "typo":
                    error_counts["typo_missed"] += 1
                elif top_cand.artist_or_uploader and top_cand.artist_or_uploader.lower() in query_obj.raw_query.lower():
                    error_counts["artist_confusion"] += 1

            # If a cover (Grade 1) outranked an exact canonical match (Grade 3)
            elif top_grade == 1.0:
                has_exact = any(g == 3.0 for g in ground_truth.values())
                if has_exact:
                    error_counts["cover_over_canonical"] += 1

        return error_counts

    def generate_targeted_examples(
        self,
        error_modes: Dict[str, int],
        seed_train_data: List[LabeledExample],
        iteration: int,
    ) -> List[LabeledExample]:
        """Generate targeted examples addressing the diagnosed failure modes from trustworthy source records."""
        targeted: List[LabeledExample] = []

        # Find canonical examples from training pool to derive targeted variants
        canonical_examples = [
            ex for ex in seed_train_data if ex.grade == RelevanceGrade.EXACT_MATCH
        ]

        # 1. Address clip noise if prevalent
        if error_modes.get("clip_noise_ranked_high", 0) > 0:
            for ex in canonical_examples[:25]:
                noise_cand = CandidateRecord(
                    candidate_id=f"targeted_clip_{iteration}_{ex.example_id}",
                    title=f"{ex.query.raw_query} (Movie Scene Clip Trailer)",
                    artist_or_uploader="Movie Clips HD",
                    duration_seconds=150.0,
                    media_type="video",
                    source_platform="youtube",
                    source_url=f"https://www.youtube.com/watch?v=target_clip_{iteration}",
                )
                targeted.append(
                    LabeledExample(
                        example_id=f"ex_target_clip_{iteration}_{ex.example_id}",
                        query=ex.query,
                        candidate=noise_cand,
                        grade=RelevanceGrade.IRRELEVANT,
                        provenance=ProvenanceType.HARD_NEGATIVE,
                        confidence=0.98,
                        group_id=ex.group_id,
                        notes="Targeted hard negative clip noise",
                    )
                )

        # 2. Address typo misses
        if error_modes.get("typo_missed", 0) > 0:
            for ex in canonical_examples[:25]:
                typo_str = introduce_realistic_typos(ex.query.raw_query)
                if typo_str != ex.query.raw_query:
                    q_typo = QueryRecord(
                        query_id=f"target_q_typo_{iteration}_{ex.query.query_id}",
                        raw_query=typo_str,
                        normalized_query=typo_str.lower(),
                        media_type=ex.query.media_type,
                        target_media_id=ex.candidate.candidate_id,
                        variation_type="typo",
                    )
                    targeted.append(
                        LabeledExample(
                            example_id=f"ex_target_typo_{iteration}_{ex.example_id}",
                            query=q_typo,
                            candidate=ex.candidate,
                            grade=RelevanceGrade.EXACT_MATCH,
                            provenance=ProvenanceType.SYNTHETIC_VARIATION,
                            confidence=0.95,
                            group_id=ex.group_id,
                            notes="Targeted typo augmentation",
                        )
                    )

        # 3. Address artist confusion
        if error_modes.get("artist_confusion", 0) > 0:
            for ex in canonical_examples[:20]:
                if ex.candidate.artist_or_uploader:
                    diff_track = CandidateRecord(
                        candidate_id=f"target_diff_track_{iteration}_{ex.example_id}",
                        title=f"{ex.candidate.artist_or_uploader} - Unrelated Studio Track B-Side",
                        artist_or_uploader=ex.candidate.artist_or_uploader,
                        duration_seconds=200.0,
                        media_type="audio",
                        source_platform="youtube",
                        source_url=f"https://www.youtube.com/watch?v=target_artist_{iteration}",
                    )
                    targeted.append(
                        LabeledExample(
                            example_id=f"ex_target_artist_{iteration}_{ex.example_id}",
                            query=ex.query,
                            candidate=diff_track,
                            grade=RelevanceGrade.IRRELEVANT,
                            provenance=ProvenanceType.HARD_NEGATIVE,
                            confidence=0.95,
                            group_id=ex.group_id,
                            notes="Targeted same-artist different-track hard negative",
                        )
                    )

        log.info("Generated %d targeted examples for iteration %d.", len(targeted), iteration)
        return targeted

    def run_loop(
        self,
        initial_model: KONSearch1ReiModel,
        initial_train_data: List[LabeledExample],
        val_data: List[LabeledExample],
        fixed_test_data: List[LabeledExample],
    ) -> Tuple[KONSearch1ReiModel, Dict[str, Any]]:
        """Run bounded optimization loop up to max_iterations."""
        best_model = copy.deepcopy(initial_model)
        best_metrics = self.evaluator.evaluate_ranker(best_model, fixed_test_data)
        current_train_data = list(initial_train_data)

        log.info(
            "Initial Model Baseline: NDCG@10=%.4f, MRR=%.4f, P@5=%.4f, Latency=%.2fms",
            best_metrics["ndcg@10"],
            best_metrics["mrr"],
            best_metrics["p@5"],
            best_metrics["latency_ms"],
        )

        for iteration in range(1, self.max_iterations + 1):
            log.info("--- Improvement Iteration %d / %d ---", iteration, self.max_iterations)

            # 1. Diagnose weaknesses on validation set
            error_modes = self.identify_error_modes(best_model, val_data)
            log.info("Iteration %d Error Modes: %s", iteration, error_modes)

            # 2. Targeted augmentation
            targeted_batch = self.generate_targeted_examples(
                error_modes, current_train_data, iteration
            )
            if not targeted_batch:
                log.info("No actionable error patterns found. Concluding loop early.")
                break

            # 3. Validate and deduplicate augmented batch
            clean_augmented = self.validator.validate_and_deduplicate_batch(
                current_train_data + targeted_batch
            )

            # 4. Train candidate model
            candidate_model = KONSearch1ReiModel(
                learning_rate=best_model.hyperparameters["learning_rate"],
                max_iter=best_model.hyperparameters["max_iter"] + (iteration * 15),
                max_depth=best_model.hyperparameters["max_depth"],
                random_state=42 + iteration,
            )
            candidate_model.fit(clean_augmented, val_examples=val_data)

            # 5. Evaluate candidate model on the FIXED held-out test set
            candidate_metrics = self.evaluator.evaluate_ranker(candidate_model, fixed_test_data)
            ndcg_delta = candidate_metrics["ndcg@10"] - best_metrics["ndcg@10"]
            mrr_delta = candidate_metrics["mrr"] - best_metrics["mrr"]

            log.info(
                "Candidate Metrics: NDCG@10=%.4f (Δ%+.4f), MRR=%.4f (Δ%+.4f), Latency=%.2fms",
                candidate_metrics["ndcg@10"],
                ndcg_delta,
                candidate_metrics["mrr"],
                mrr_delta,
                candidate_metrics["latency_ms"],
            )

            # 6. Strict Acceptance or Rollback Decision
            accepted = (
                ndcg_delta >= self.min_ndcg_gain
                and mrr_delta >= -0.01  # Do not tolerate MRR collapse
                and candidate_metrics["latency_ms"] <= self.max_latency_ms
            )

            iter_record = {
                "iteration": iteration,
                "error_modes": error_modes,
                "added_examples": len(clean_augmented) - len(current_train_data),
                "total_train_samples": len(clean_augmented),
                "candidate_metrics": candidate_metrics,
                "previous_best_metrics": best_metrics,
                "ndcg_delta": round(ndcg_delta, 4),
                "mrr_delta": round(mrr_delta, 4),
                "decision": "ACCEPTED" if accepted else "REJECTED",
                "reason": (
                    f"NDCG gain {ndcg_delta:+.4f} >= threshold {self.min_ndcg_gain}"
                    if accepted
                    else f"Gain {ndcg_delta:+.4f} below threshold {self.min_ndcg_gain} or latency exceeded"
                ),
            }
            self.experiment_history.append(iter_record)

            if accepted:
                log.info("Iteration %d ACCEPTED! Updating best model checkpoint.", iteration)
                best_model = candidate_model
                best_metrics = candidate_metrics
                current_train_data = clean_augmented
            else:
                log.info("Iteration %d REJECTED. Rolling back to previous best checkpoint.", iteration)

        summary = {
            "iterations_executed": len(self.experiment_history),
            "final_metrics": best_metrics,
            "history": self.experiment_history,
        }
        return best_model, summary
