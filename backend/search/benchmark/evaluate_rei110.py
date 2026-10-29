"""Evaluation harness for KON Search 1.1.0 Re.

Computes NDCG@10, MRR, P@5, Recall@10, and latency statistics across
regression and multi-signal fixtures with >= 8 candidates per query.
"""

import copy
import math
import time
from typing import Any, Dict, List
import backend.search.rust_bridge as rust_bridge
from backend.search.benchmark.fixtures_rei110 import EVAL_FIXTURES_REI_110


def dcg_at_k(relevances: List[int], k: int = 10) -> float:
    """Compute Discounted Cumulative Gain at rank k."""
    dcg = 0.0
    for i, rel in enumerate(relevances[:k]):
        dcg += (2.0**rel - 1.0) / math.log2(i + 2.0)
    return dcg


def ndcg_at_k(actual_rels: List[int], ideal_rels: List[int], k: int = 10) -> float:
    """Compute Normalized Discounted Cumulative Gain at rank k."""
    actual_dcg = dcg_at_k(actual_rels, k)
    idcg = dcg_at_k(sorted(ideal_rels, reverse=True), k)
    if idcg <= 0.0:
        return 0.0
    return actual_dcg / idcg


def evaluate_engine() -> Dict[str, Any]:
    """Evaluate active search engine against all Rei 1.1.0 fixtures."""
    active_engine = rust_bridge.get_active_engine_name()

    ndcg_scores: List[float] = []
    mrr_scores: List[float] = []
    p5_scores: List[float] = []
    recall10_scores: List[float] = []
    latencies_ms: List[float] = []

    case_results: List[Dict[str, Any]] = []

    # Warm-up pass
    if EVAL_FIXTURES_REI_110:
        sample = EVAL_FIXTURES_REI_110[0]
        _ = rust_bridge.rank_candidates(sample["query"], sample["candidates"][:])

    for fixture in EVAL_FIXTURES_REI_110:
        q = fixture["query"]
        candidates = [copy.copy(c) for c in fixture["candidates"]]
        ground_truth = fixture["relevance_ground_truth"]
        target_ids = fixture["target_ids"]

        t0 = time.perf_counter()
        ranked = rust_bridge.rank_candidates(q, candidates)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        latencies_ms.append(elapsed_ms)

        ranked_ids = [c.id for c in ranked]
        ranked_rels = [ground_truth.get(cid, 0) for cid in ranked_ids]
        ideal_rels = list(ground_truth.values())

        # NDCG@10
        ndcg = ndcg_at_k(ranked_rels, ideal_rels, k=10)
        ndcg_scores.append(ndcg)

        # MRR
        rr = 0.0
        for rank_idx, cid in enumerate(ranked_ids):
            if cid in target_ids:
                rr = 1.0 / (rank_idx + 1)
                break
        mrr_scores.append(rr)

        # P@5 (fraction of top 5 with relevance >= 2)
        top5_rels = ranked_rels[:5]
        p5 = sum(1 for r in top5_rels if r >= 2) / 5.0
        p5_scores.append(p5)

        # Recall@10
        total_targets = len(target_ids)
        targets_found = sum(1 for tid in target_ids if tid in ranked_ids[:10])
        recall10 = (targets_found / total_targets) if total_targets > 0 else 1.0
        recall10_scores.append(recall10)

        case_results.append({
            "fixture": fixture["name"],
            "top1_id": ranked_ids[0] if ranked_ids else None,
            "top1_title": ranked[0].title if ranked else None,
            "top1_score": ranked[0].score if ranked else 0.0,
            "top1_confidence": ranked[0].confidence if ranked else "low",
            "is_target_top1": ranked_ids[0] in target_ids if ranked_ids else False,
            "ndcg10": round(ndcg, 4),
            "rr": round(rr, 4),
            "latency_ms": round(elapsed_ms, 3),
        })

    latencies_sorted = sorted(latencies_ms)
    p50_lat = latencies_sorted[len(latencies_sorted) // 2] if latencies_sorted else 0.0
    p95_idx = int(math.ceil(0.95 * len(latencies_sorted))) - 1
    p95_lat = latencies_sorted[max(0, p95_idx)] if latencies_sorted else 0.0

    summary = {
        "engine": active_engine,
        "fixtures_count": len(EVAL_FIXTURES_REI_110),
        "mean_ndcg10": round(sum(ndcg_scores) / len(ndcg_scores), 4) if ndcg_scores else 0.0,
        "mean_mrr": round(sum(mrr_scores) / len(mrr_scores), 4) if mrr_scores else 0.0,
        "mean_p5": round(sum(p5_scores) / len(p5_scores), 4) if p5_scores else 0.0,
        "mean_recall10": round(sum(recall10_scores) / len(recall10_scores), 4) if recall10_scores else 0.0,
        "latency_p50_ms": round(p50_lat, 3),
        "latency_p95_ms": round(p95_lat, 3),
        "cases": case_results,
    }
    return summary


if __name__ == "__main__":
    results = evaluate_engine()
    print("=== KON SEARCH 1.1.0 RE EVALUATION REPORT ===")
    print(f"Active Engine: {results['engine']}")
    print(f"Mean NDCG@10: {results['mean_ndcg10']}")
    print(f"Mean MRR:     {results['mean_mrr']}")
    print(f"Mean P@5:     {results['mean_p5']}")
    print(f"Mean Recall@10: {results['mean_recall10']}")
    print(f"Median Latency: {results['latency_p50_ms']} ms")
    print(f"P95 Latency:    {results['latency_p95_ms']} ms")
    print("\nCase Breakdown:")
    for c in results["cases"]:
        print(f" - {c['fixture']}: top1={c['top1_id']} (target={c['is_target_top1']}), NDCG={c['ndcg10']}, Latency={c['latency_ms']}ms")
