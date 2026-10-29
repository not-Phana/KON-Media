"""Runner executing benchmark evaluations across Tuning and Held-out datasets and formatting reports."""

from typing import Callable, List, Dict, Any, Optional
from backend.search.benchmark.dataset import TUNING_QUERIES, HELD_OUT_QUERIES
from backend.search.benchmark.evaluator import BenchmarkEvaluator
from backend.search.models import CandidateResult, SearchQuery


def run_benchmark(
    rank_fn: Callable[[SearchQuery, List[CandidateResult]], List[CandidateResult]],
    name: str = "Candidate",
    include_held_out: bool = True,
) -> Dict[str, Any]:
    """Run benchmark evaluation and return detailed report."""
    tune_eval = BenchmarkEvaluator(TUNING_QUERIES)
    tune_res = tune_eval.evaluate(rank_fn, name=f"{name} (Tuning)")

    report: Dict[str, Any] = {
        "name": name,
        "tuning": tune_res,
    }

    if include_held_out:
        held_eval = BenchmarkEvaluator(HELD_OUT_QUERIES)
        held_res = held_eval.evaluate(rank_fn, name=f"{name} (Held-out)")
        report["held_out"] = held_res

    return report


def print_comparison_table(results_history: List[Dict[str, Any]]) -> None:
    """Print an ASCII comparison table across experimental iterations."""
    header = (
        f"{'Iteration / Name':<32} | {'Tuning P@1':<10} | {'Tuning MRR':<10} | {'Tuning NDCG':<11} | "
        f"{'Held-Out P@1':<12} | {'Held-Out MRR':<12} | {'Latency':<8}"
    )
    separator = "-" * len(header)
    print("\n" + separator)
    print(header)
    print(separator)

    for item in results_history:
        name = item["name"]
        tune = item.get("tuning", {})
        held = item.get("held_out", {})

        tp1 = f"{tune.get('precision@1', 0.0):.3f}"
        tmrr = f"{tune.get('mrr', 0.0):.3f}"
        tndcg = f"{tune.get('ndcg@5', 0.0):.3f}"

        hp1 = f"{held.get('precision@1', 0.0):.3f}" if held else "N/A"
        hmrr = f"{held.get('mrr', 0.0):.3f}" if held else "N/A"
        lat = f"{tune.get('avg_latency_ms', 0.0):.2f}ms"

        print(f"{name:<32} | {tp1:<10} | {tmrr:<10} | {tndcg:<11} | {hp1:<12} | {hmrr:<12} | {lat:<8}")

    print(separator + "\n")
