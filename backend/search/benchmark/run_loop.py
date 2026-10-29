"""Execute baseline evaluation and record initial benchmark metrics."""

import json
from pathlib import Path
from backend.search.benchmark.runner import run_benchmark, print_comparison_table
from backend.search.models import SearchQuery, CandidateResult

def baseline_ranker(query: SearchQuery, candidates: list[CandidateResult]):
    # Naive baseline: leaves candidate order untouched
    return list(candidates)

if __name__ == "__main__":
    res_baseline = run_benchmark(baseline_ranker, name="Iteration 0 (Baseline)")
    print_comparison_table([res_baseline])

    print("TUNING CATEGORIES BREAKDOWN:")
    for cat, vals in res_baseline["tuning"]["categories"].items():
        print(f"  {cat:<25}: P@1={vals['p1']:.3f}, MRR={vals['mrr']:.3f}, NDCG={vals['ndcg']:.3f}")

    print("\nHELD-OUT CATEGORIES BREAKDOWN:")
    for cat, vals in res_baseline["held_out"]["categories"].items():
        print(f"  {cat:<25}: P@1={vals['p1']:.3f}, MRR={vals['mrr']:.3f}, NDCG={vals['ndcg']:.3f}")

    # Save baseline to disk
    out_path = Path("backend/search/benchmark/baseline_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(res_baseline, f, indent=2)
    print(f"\nSaved baseline results to {out_path}")
