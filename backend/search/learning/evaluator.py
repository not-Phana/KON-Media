"""Autonomous Evaluation System for KON Search 1.2 Rei and Rei Flash.

Key principles:
1. Isolated Held-out Benchmarks: Evaluates models against preserved held-out test sets.
   Never trains on evaluation queries or leaks test labels.
2. Multi-Metric Scoring: Computes NDCG@10, MRR, Precision@5, Recall@10, Exact Match Accuracy,
   and Search Latency for both Rei (Precision) and Rei Flash (Speed).
3. Regression Detection: Tracks per-query rankings to prevent regressions where previously
   correct results degrade.
4. Gatekeeper Promotion Decision: Approves or rejects candidate models objectively.
"""

import datetime
import math
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from backend.search.models import CandidateResult, SearchQuery
from backend.search.benchmark.dataset import HELD_OUT_QUERIES
from backend.search.learning_model import SearchLearningModel
import backend.search.rust_bridge as rust_bridge

log = logging = __import__("logging").getLogger("kon_evaluator")


def compute_dcg(grades: List[int], k: int = 10) -> float:
    """Compute Discounted Cumulative Gain at rank k."""
    dcg = 0.0
    for i, rel in enumerate(grades[:k]):
        if rel > 0:
            dcg += (math.pow(2, rel) - 1.0) / math.log2(i + 2)
    return dcg


def compute_ndcg(ranked_ids: List[str], relevance_grades: Dict[str, int], k: int = 10) -> float:
    """Compute Normalized Discounted Cumulative Gain at rank k."""
    actual_grades = [relevance_grades.get(cid, 0) for cid in ranked_ids[:k]]
    actual_dcg = compute_dcg(actual_grades, k)

    ideal_grades = sorted(relevance_grades.values(), reverse=True)
    ideal_dcg = compute_dcg(ideal_grades, k)

    if ideal_dcg <= 0.0:
        return 1.0 if actual_dcg <= 0.0 else 0.0
    return round(actual_dcg / ideal_dcg, 4)


class AutonomousEvaluator:
    """Automated evaluation harness for ranking models and candidate comparison."""

    def __init__(self, eval_queries: Optional[List[Dict[str, Any]]] = None):
        # Strictly use held-out evaluation set
        self.eval_dataset = eval_queries or HELD_OUT_QUERIES

    def evaluate_model_pipeline(
        self,
        learning_model: SearchLearningModel,
        engine_mode: str = "rei",
    ) -> Dict[str, Any]:
        """Evaluate a model candidate in Rei or Rei Flash mode over held-out benchmark queries."""
        is_flash = engine_mode.lower() == "flash"
        sem_weight = learning_model.weights.get("semantic_embedding", 0.30)

        ndcg_scores = []
        mrr_scores = []
        p5_scores = []
        recall10_scores = []
        exact_match_hits = 0
        exact_queries_count = 0
        latencies_ms = []
        per_query_ranks: Dict[str, int] = {}

        for item in self.eval_dataset:
            qid = item["query_id"]
            query_str = item["query"]
            expected_ids = set(item.get("expected_relevant_ids", []))
            relevance_grades = item.get("relevance_grades", {})
            is_exact = item.get("category") == "exact"
            if is_exact:
                exact_queries_count += 1

            # Clone pool
            pool = [
                CandidateResult(
                    id=c.id,
                    title=c.title,
                    uploader=c.uploader,
                    url=c.url,
                    duration=c.duration,
                    platform=c.platform,
                    views=c.views,
                )
                for c in item["candidate_pool"]
            ]

            search_query = SearchQuery(
                raw_query=query_str,
                expected_artist=item.get("expected_artist"),
                expected_title=item.get("expected_title"),
                expected_duration=item.get("ideal_duration"),
            )

            # Benchmark inference latency
            t0 = time.perf_counter()

            # 1. Base ranking (Flash or Precision)
            if is_flash:
                ranked = rust_bridge.rank_candidates_flash(query=search_query, candidates=pool)
            else:
                ranked = rust_bridge.rank_candidates(query=search_query, candidates=pool)

            # 2. Apply candidate model neural semantic association
            if learning_model:
                for c in ranked:
                    try:
                        sim = learning_model.compute_semantic_similarity(query_str, c.title)
                        if sim > 0.05:
                            c.score += sem_weight * sim
                        elif sim < 0.0:
                            c.score += sim * 0.5
                    except Exception:
                        pass
                ranked.sort(key=lambda x: getattr(x, "score", 0.0), reverse=True)

            latency = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(latency)

            ranked_ids = [c.id for c in ranked]

            # Metric: NDCG@10
            ndcg = compute_ndcg(ranked_ids, relevance_grades, k=10)
            ndcg_scores.append(ndcg)

            # Metric: MRR (first relevant rank reciprocal)
            first_rank = 0
            for r_idx, cid in enumerate(ranked_ids, 1):
                if cid in expected_ids:
                    first_rank = r_idx
                    break
            reciprocal_rank = 1.0 / first_rank if first_rank > 0 else 0.0
            mrr_scores.append(reciprocal_rank)
            per_query_ranks[qid] = first_rank if first_rank > 0 else 999

            # Metric: Precision@5
            top5 = ranked_ids[:5]
            hits5 = sum(1 for cid in top5 if cid in expected_ids)
            p5 = hits5 / 5.0
            p5_scores.append(p5)

            # Metric: Recall@10
            top10 = set(ranked_ids[:10])
            hits10 = sum(1 for eid in expected_ids if eid in top10)
            recall = hits10 / len(expected_ids) if expected_ids else 1.0
            recall10_scores.append(recall)

            # Metric: Exact match accuracy
            if is_exact:
                if ranked_ids and ranked_ids[0] in expected_ids:
                    exact_match_hits += 1

        total = len(self.eval_dataset) or 1
        mean_ndcg = round(sum(ndcg_scores) / total, 4)
        mean_mrr = round(sum(mrr_scores) / total, 4)
        mean_p5 = round(sum(p5_scores) / total, 4)
        mean_recall10 = round(sum(recall10_scores) / total, 4)
        exact_acc = round(exact_match_hits / max(exact_queries_count, 1), 4)
        avg_latency = round(sum(latencies_ms) / total, 2)

        # Composite score: 40% NDCG@10 + 35% MRR + 25% P@5
        composite_score = round(0.40 * mean_ndcg + 0.35 * mean_mrr + 0.25 * mean_p5, 4)

        return {
            "engine_mode": engine_mode,
            "queries_evaluated": total,
            "ndcg10": mean_ndcg,
            "mrr": mean_mrr,
            "p5": mean_p5,
            "recall10": mean_recall10,
            "exact_match_accuracy": exact_acc,
            "latency_ms": avg_latency,
            "composite_score": composite_score,
            "per_query_ranks": per_query_ranks,
        }

    def compare_models(
        self,
        candidate_model: SearchLearningModel,
        production_model: SearchLearningModel,
    ) -> Dict[str, Any]:
        """Compare candidate model against production model on both Rei and Rei Flash.

        Enforces strict promotion policy:
        1. Composite score must not regress.
        2. Regression rate (queries where rank got worse) must be <= 5.0%.
        3. Exact match accuracy must not decrease.
        4. Latency must stay within threshold.
        """
        # Evaluate Rei (Precision Mode)
        prod_rei = self.evaluate_model_pipeline(production_model, engine_mode="rei")
        cand_rei = self.evaluate_model_pipeline(candidate_model, engine_mode="rei")

        # Evaluate Rei Flash (Speed Mode)
        prod_flash = self.evaluate_model_pipeline(production_model, engine_mode="flash")
        cand_flash = self.evaluate_model_pipeline(candidate_model, engine_mode="flash")

        # Count regressions in Rei
        regressions = 0
        improvements = 0
        for qid, prod_rank in prod_rei["per_query_ranks"].items():
            cand_rank = cand_rei["per_query_ranks"].get(qid, 999)
            if cand_rank > prod_rank:
                regressions += 1
            elif cand_rank < prod_rank:
                improvements += 1

        total_queries = len(self.eval_dataset) or 1
        regression_rate = round(regressions / total_queries, 4)

        score_delta_rei = round(cand_rei["composite_score"] - prod_rei["composite_score"], 4)
        score_delta_flash = round(cand_flash["composite_score"] - prod_flash["composite_score"], 4)

        # Promotion Gatekeeper Rules
        reasons_for_rejection: List[str] = []

        if regression_rate > 0.05:
            reasons_for_rejection.append(
                f"Regression rate too high ({round(regression_rate * 100, 1)}% > 5.0% threshold)"
            )

        if cand_rei["composite_score"] < prod_rei["composite_score"]:
            reasons_for_rejection.append(
                f"Candidate Rei score ({cand_rei['composite_score']}) is lower than production ({prod_rei['composite_score']})"
            )

        if cand_flash["composite_score"] < prod_flash["composite_score"] - 0.01:
            reasons_for_rejection.append(
                f"Candidate Flash score ({cand_flash['composite_score']}) degraded vs production ({prod_flash['composite_score']})"
            )

        if cand_rei["exact_match_accuracy"] < prod_rei["exact_match_accuracy"]:
            reasons_for_rejection.append("Exact match accuracy degraded")

        if cand_flash["latency_ms"] > 8.0:
            reasons_for_rejection.append(f"Flash latency exceeded threshold ({cand_flash['latency_ms']}ms > 8.0ms)")

        should_promote = len(reasons_for_rejection) == 0

        return {
            "should_promote": should_promote,
            "decision": "ACCEPT" if should_promote else "REJECT",
            "rejection_reasons": reasons_for_rejection,
            "regression_rate": regression_rate,
            "regressions_count": regressions,
            "improvements_count": improvements,
            "score_delta_rei": score_delta_rei,
            "score_delta_flash": score_delta_flash,
            "candidate_rei": cand_rei,
            "production_rei": prod_rei,
            "candidate_flash": cand_flash,
            "production_flash": prod_flash,
            "evaluated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
