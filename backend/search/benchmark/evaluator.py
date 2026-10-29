"""Evaluator computing Precision@1, Precision@5, MRR, NDCG@5, Latency, and Error rates."""

import math
import time
from typing import Any, Callable, Dict, List, Optional
from backend.search.models import CandidateResult, SearchQuery


def compute_dcg(grades: List[int], k: int = 5) -> float:
    """Compute Discounted Cumulative Gain at rank k."""
    dcg = 0.0
    for i, rel in enumerate(grades[:k]):
        if rel > 0:
            dcg += (math.pow(2, rel) - 1.0) / math.log2(i + 2)
    return dcg


def compute_ndcg(ranked_ids: List[str], relevance_grades: Dict[str, int], k: int = 5) -> float:
    """Compute Normalized Discounted Cumulative Gain at rank k."""
    actual_grades = [relevance_grades.get(cid, 0) for cid in ranked_ids[:k]]
    actual_dcg = compute_dcg(actual_grades, k)

    # Ideal DCG: sort all available pool grades descending
    ideal_grades = sorted(relevance_grades.values(), reverse=True)
    ideal_dcg = compute_dcg(ideal_grades, k)

    if ideal_dcg == 0.0:
        return 1.0 if actual_dcg == 0.0 else 0.0
    return actual_dcg / ideal_dcg


class BenchmarkEvaluator:
    """Evaluates search and ranking algorithms against labeled benchmark queries."""

    def __init__(self, dataset: List[Dict[str, Any]]):
        self.dataset = dataset

    def evaluate(
        self,
        rank_fn: Callable[[SearchQuery, List[CandidateResult]], List[CandidateResult]],
        name: str = "Candidate Version",
    ) -> Dict[str, Any]:
        """Run benchmark queries through rank_fn and compute comprehensive metrics."""
        total_queries = len(self.dataset)
        p1_list: List[float] = []
        p5_list: List[float] = []
        mrr_list: List[float] = []
        ndcg5_list: List[float] = []
        latencies_ms: List[float] = []
        empty_count = 0
        error_count = 0

        category_metrics: Dict[str, Dict[str, List[float]]] = {}
        per_query_results: List[Dict[str, Any]] = []

        for item in self.dataset:
            qid = item["query_id"]
            query_str = item["query"]
            cat = item["category"]
            expected_ids = set(item.get("expected_relevant_ids", []))
            relevance_grades = item.get("relevance_grades", {})
            candidate_pool = [
                # Clone candidates so rankers don't mutate the original benchmark instances
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

            t0 = time.perf_counter()
            try:
                ranked = rank_fn(search_query, candidate_pool)
            except Exception as e:
                error_count += 1
                ranked = []
            latency = (time.perf_counter() - t0) * 1000.0
            latencies_ms.append(latency)

            ranked_ids = [c.id for c in ranked]

            if not ranked_ids:
                empty_count += 1

            # Handle negative / unanswerable queries vs positive queries
            is_negative_query = len(expected_ids) == 0

            if is_negative_query:
                # If negative query: perfect if no high-confidence result returned (empty or top item has low confidence)
                # If ranker returned candidates with high confidence or falsely marked relevant, it's a false positive
                has_confident_match = len(ranked) > 0 and getattr(ranked[0], "confidence", "low") == "high"
                p1 = 0.0 if has_confident_match else 1.0
                p5 = 0.0 if has_confident_match else 1.0
                mrr = 1.0 if not has_confident_match else 0.0
                ndcg = 1.0 if not has_confident_match else 0.0
            else:
                # Top-1 precision
                p1 = 1.0 if (len(ranked_ids) > 0 and ranked_ids[0] in expected_ids) else 0.0
                # Top-5 precision (is any of top 5 relevant?)
                p5 = 1.0 if any(cid in expected_ids for cid in ranked_ids[:5]) else 0.0

                # MRR
                rr = 0.0
                for rank_idx, cid in enumerate(ranked_ids):
                    if cid in expected_ids:
                        rr = 1.0 / (rank_idx + 1)
                        break
                mrr = rr

                # NDCG@5
                ndcg = compute_ndcg(ranked_ids, relevance_grades, k=5)

            p1_list.append(p1)
            p5_list.append(p5)
            mrr_list.append(mrr)
            ndcg5_list.append(ndcg)

            # Record category aggregates
            if cat not in category_metrics:
                category_metrics[cat] = {"p1": [], "mrr": [], "ndcg": []}
            category_metrics[cat]["p1"].append(p1)
            category_metrics[cat]["mrr"].append(mrr)
            category_metrics[cat]["ndcg"].append(ndcg)

            per_query_results.append({
                "query_id": qid,
                "category": cat,
                "query": query_str,
                "top_result": ranked_ids[0] if ranked_ids else None,
                "top_title": ranked[0].title if ranked else None,
                "p1": p1,
                "mrr": mrr,
                "ndcg": ndcg,
                "success": p1 > 0.0 or (is_negative_query and p1 == 1.0),
            })

        mean_p1 = sum(p1_list) / total_queries if total_queries else 0.0
        mean_p5 = sum(p5_list) / total_queries if total_queries else 0.0
        mean_mrr = sum(mrr_list) / total_queries if total_queries else 0.0
        mean_ndcg = sum(ndcg5_list) / total_queries if total_queries else 0.0
        avg_latency = sum(latencies_ms) / total_queries if total_queries else 0.0

        cat_summary = {}
        for cat, scores in category_metrics.items():
            cat_summary[cat] = {
                "count": len(scores["p1"]),
                "p1": round(sum(scores["p1"]) / len(scores["p1"]), 4),
                "mrr": round(sum(scores["mrr"]) / len(scores["mrr"]), 4),
                "ndcg": round(sum(scores["ndcg"]) / len(scores["ndcg"]), 4),
            }

        return {
            "name": name,
            "total_queries": total_queries,
            "precision@1": round(mean_p1, 4),
            "precision@5": round(mean_p5, 4),
            "mrr": round(mean_mrr, 4),
            "ndcg@5": round(mean_ndcg, 4),
            "avg_latency_ms": round(avg_latency, 3),
            "empty_rate": round(empty_count / total_queries, 4) if total_queries else 0.0,
            "error_rate": round(error_count / total_queries, 4) if total_queries else 0.0,
            "categories": cat_summary,
            "details": per_query_results,
        }
