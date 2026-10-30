"""Benchmark comparing candidate ranking throughput and latency across candidate pool sizes (20, 60, 100)."""

import copy
import json
import random
import time
from typing import Any, Dict, List
import backend.search.rust_bridge as rust_bridge
from backend.search.models import CandidateResult, SearchQuery
from backend.search.relevance_engine import rank_candidates as py_rank_candidates


def generate_synthetic_pool(size: int) -> List[CandidateResult]:
    """Generate a realistic pool of candidates with varying titles, uploaders, and durations."""
    artists = ["Queen", "Linkin Park", "Shiro Sagisu", "The Weeknd", "Daft Punk", "Eminem", "Ed Sheeran"]
    modifiers = ["Official Audio", "Official Video", "Remix", "Live at Wembley", "Parody", "Acoustic", "Instrumental", "Reaction"]

    pool: List[CandidateResult] = []
    for i in range(size):
        artist = random.choice(artists)
        mod = random.choice(modifiers)
        cid = f"cand_{size}_{i}"
        title = f"{artist} - Track #{i} ({mod})"
        pool.append(
            CandidateResult(
                id=cid,
                title=title,
                uploader=f"{artist} Official" if "Official" in mod else "RandomUploader",
                duration=float(random.randint(120, 380)),
                views=random.randint(1000, 50_000_000),
                platform="youtube",
                url=f"https://youtube.com/watch?v=mock_{cid}",
            )
        )
    return pool


def run_benchmark(iterations: int = 200) -> Dict[str, Any]:
    """Run benchmark across candidate pool sizes."""
    sizes = [20, 60, 100]
    query = SearchQuery(raw_query="Linkin Park Official Audio", media_type="audio")

    report: Dict[str, Any] = {
        "iterations": iterations,
        "active_engine": rust_bridge.get_active_engine_name(),
        "is_rust_active": rust_bridge.is_rust_available(),
        "results": {},
    }

    # Warmup
    for sz in sizes:
        pool = generate_synthetic_pool(sz)
        for _ in range(10):
            _ = py_rank_candidates(query, pool[:])

    for sz in sizes:
        pool = generate_synthetic_pool(sz)
        py_latencies: List[float] = []

        for _ in range(iterations):
            cand_copy = [copy.copy(c) for c in pool]
            t0 = time.perf_counter()
            _ = py_rank_candidates(query, cand_copy)
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            py_latencies.append(elapsed_ms)

        py_latencies.sort()
        p50 = py_latencies[len(py_latencies) // 2]
        p95_idx = int(0.95 * len(py_latencies)) - 1
        p95 = py_latencies[max(0, p95_idx)]
        throughput_qps = 1000.0 / (sum(py_latencies) / len(py_latencies))

        report["results"][f"pool_{sz}"] = {
            "pool_size": sz,
            "engine": "python-fallback/1.1.0",
            "median_latency_ms": round(p50, 4),
            "p95_latency_ms": round(p95, 4),
            "mean_latency_ms": round(sum(py_latencies) / len(py_latencies), 4),
            "throughput_qps": round(throughput_qps, 1),
        }

    return report


if __name__ == "__main__":
    rep = run_benchmark()
    print("=== KON SEARCH 1.1.0 REI BENCHMARK RESULTS ===")
    print(f"Active Engine: {rep['active_engine']}")
    for k, v in rep["results"].items():
        print(f"Pool Size {v['pool_size']:3d}: Median={v['median_latency_ms']:.3f}ms | P95={v['p95_latency_ms']:.3f}ms | Throughput={v['throughput_qps']:.1f} queries/sec")
