"""Comprehensive IR and Learning-to-Rank Evaluation Engine for KON Search 1 Rei.

Computes:
- NDCG@10 (Normalized Discounted Cumulative Gain)
- Mean Reciprocal Rank (MRR)
- Precision@5
- Recall@10
- Inference Latency (ms)
- Comparative Delta vs Lexical Baseline
"""

import math
import time
from typing import Any, Dict, List, Tuple
from collections import defaultdict
from kon_search.schema import CandidateRecord, LabeledExample, QueryRecord, RelevanceGrade


def dcg_at_k(relevances: List[float], k: int = 10) -> float:
    """Compute Discounted Cumulative Gain at K using exponential gain formula."""
    relevances = relevances[:k]
    dcg = 0.0
    for i, rel in enumerate(relevances, 1):
        gain = (2.0**rel) - 1.0
        discount = math.log2(i + 1)
        dcg += gain / discount
    return dcg


def ndcg_at_k(predicted_relevances: List[float], ideal_relevances: List[float], k: int = 10) -> float:
    """Compute Normalized Discounted Cumulative Gain at K."""
    idcg = dcg_at_k(sorted(ideal_relevances, reverse=True), k=k)
    if idcg <= 0.0:
        return 1.0 if not any(r > 0 for r in ideal_relevances) else 0.0
    actual_dcg = dcg_at_k(predicted_relevances, k=k)
    return round(min(1.0, max(0.0, actual_dcg / idcg)), 4)


def mrr_score(relevances: List[float], threshold: float = 2.0) -> float:
    """Compute Reciprocal Rank: 1 / rank of first candidate meeting relevance threshold."""
    for i, rel in enumerate(relevances, 1):
        if rel >= threshold:
            return round(1.0 / i, 4)
    return 0.0


def precision_at_k(relevances: List[float], k: int = 5, threshold: float = 2.0) -> float:
    """Compute Precision@K."""
    top_k = relevances[:k]
    if not top_k:
        return 0.0
    num_relevant = sum(1 for r in top_k if r >= threshold)
    return round(num_relevant / len(top_k), 4)


def recall_at_k(relevances: List[float], total_relevant: int, k: int = 10, threshold: float = 2.0) -> float:
    """Compute Recall@K against total known relevant items for the query."""
    if total_relevant <= 0:
        return 1.0
    top_k = relevances[:k]
    num_retrieved = sum(1 for r in top_k if r >= threshold)
    return round(min(1.0, num_retrieved / total_relevant), 4)


class SearchEvaluator:
    """Evaluates rankers against held-out test query batches."""

    @staticmethod
    def group_examples_by_query(
        examples: List[LabeledExample],
    ) -> Dict[str, Tuple[QueryRecord, List[Tuple[CandidateRecord, float]]]]:
        """Group labeled examples by query text."""
        query_map: Dict[str, Tuple[QueryRecord, List[Tuple[CandidateRecord, float]]]] = {}
        for ex in examples:
            qid = ex.query.raw_query
            if qid not in query_map:
                query_map[qid] = (ex.query, [])
            query_map[qid][1].append((ex.candidate, float(ex.grade)))
        return query_map

    def evaluate_ranker(
        self,
        ranker: Any,
        test_examples: List[LabeledExample],
        k: int = 10,
    ) -> Dict[str, float]:
        """Evaluate a ranker (baseline or ML model) across all test queries."""
        query_groups = self.group_examples_by_query(test_examples)
        if not query_groups:
            return {"ndcg@10": 0.0, "mrr": 0.0, "p@5": 0.0, "recall@10": 0.0, "latency_ms": 0.0}

        ndcg_list = []
        mrr_list = []
        p5_list = []
        recall10_list = []
        latencies = []

        for q_text, (query_obj, cand_pairs) in query_groups.items():
            candidates = [c for c, _ in cand_pairs]
            ground_truth_map = {c.candidate_id: g for c, g in cand_pairs}
            total_relevant = sum(1 for _, g in cand_pairs if g >= 2.0)

            # Benchmark scoring latency
            t0 = time.perf_counter()
            ranked_results = ranker.score_candidates(query_obj, candidates)
            latency_ms = (time.perf_counter() - t0) * 1000.0
            latencies.append(latency_ms)

            # Extract ground-truth grades ordered by the ranker's output
            predicted_grades = [ground_truth_map[c.candidate_id] for c, _ in ranked_results]
            ideal_grades = [g for _, g in cand_pairs]

            ndcg_list.append(ndcg_at_k(predicted_grades, ideal_grades, k=k))
            mrr_list.append(mrr_score(predicted_grades, threshold=2.0))
            p5_list.append(precision_at_k(predicted_grades, k=5, threshold=2.0))
            recall10_list.append(recall_at_k(predicted_grades, total_relevant, k=k, threshold=2.0))

        return {
            "ndcg@10": round(float(sum(ndcg_list) / len(ndcg_list)), 4),
            "mrr": round(float(sum(mrr_list) / len(mrr_list)), 4),
            "p@5": round(float(sum(p5_list) / len(p5_list)), 4),
            "recall@10": round(float(sum(recall10_list) / len(recall10_list)), 4),
            "latency_ms": round(float(sum(latencies) / len(latencies)), 3),
            "evaluated_queries": len(query_groups),
        }

    def compare_models(
        self,
        baseline_ranker: Any,
        ml_model: Any,
        test_examples: List[LabeledExample],
    ) -> Dict[str, Any]:
        """Compute side-by-side evaluation and delta gains."""
        baseline_metrics = self.evaluate_ranker(baseline_ranker, test_examples)
        ml_metrics = self.evaluate_ranker(ml_model, test_examples)

        delta = {
            "ndcg@10_gain": round(ml_metrics["ndcg@10"] - baseline_metrics["ndcg@10"], 4),
            "mrr_gain": round(ml_metrics["mrr"] - baseline_metrics["mrr"], 4),
            "p@5_gain": round(ml_metrics["p@5"] - baseline_metrics["p@5"], 4),
            "recall@10_gain": round(ml_metrics["recall@10"] - baseline_metrics["recall@10"], 4),
            "latency_delta_ms": round(ml_metrics["latency_ms"] - baseline_metrics["latency_ms"], 3),
        }

        # Acceptance check: ML model must outperform baseline on NDCG@10 and MRR without extreme latency
        is_accepted = (
            delta["ndcg@10_gain"] >= 0.05
            and delta["mrr_gain"] >= 0.0
            and ml_metrics["latency_ms"] < 20.0
        )

        return {
            "baseline": baseline_metrics,
            "kon_search_1_rei": ml_metrics,
            "delta": delta,
            "acceptance_decision": "ACCEPTED" if is_accepted else "REJECTED",
        }
