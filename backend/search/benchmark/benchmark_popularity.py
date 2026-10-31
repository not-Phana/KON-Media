"""Comprehensive Benchmark Suite for Popularity-Aware Music Ranking in KON Search 1.2.

Compares:
1. Baseline (Before): Textual relevance without popularity awareness.
2. Upgraded (After): Popularity-aware ranking for KON Search 1.2 Rei and Rei Flash.

Evaluates across 7 key scenario categories:
- Broad searches: 'popular songs', 'trending music', 'top hits'
- Exact title searches
- Title + artist searches
- Ambiguous song titles ('bad guy', 'Shelter')
- New trending songs vs older hits
- Popular songs vs obscure songs with same title
- Missing popularity metadata resilience

Metrics measured:
- NDCG@10
- MRR (Mean Reciprocal Rank)
- Precision@5
- Recall@10
- Ranking Consistency (Rei vs Rei Flash)
- Search Latency (p50, p95)
"""

import copy
import json
import math
import os
import sys
import time
from typing import Any, Dict, List, Tuple

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

import backend.search.rust_bridge as rust_bridge
from backend.search.models import CandidateResult, SearchQuery


def dcg_at_k(relevances: List[int], k: int = 10) -> float:
    dcg = 0.0
    for i, rel in enumerate(relevances[:k]):
        dcg += (2.0**rel - 1.0) / math.log2(i + 2.0)
    return dcg


def ndcg_at_k(actual_rels: List[int], ideal_rels: List[int], k: int = 10) -> float:
    actual = dcg_at_k(actual_rels, k)
    ideal = dcg_at_k(sorted(ideal_rels, reverse=True), k)
    if ideal <= 0.0:
        return 0.0
    return actual / ideal


def calculate_metrics(
    ranked: List[CandidateResult],
    expected_ids: set,
    grades: Dict[str, int],
    k: int = 10,
) -> Tuple[float, float, float, float]:
    """Calculate NDCG@k, MRR, Precision@5, Recall@k."""
    # NDCG@k
    actual_grades = [grades.get(c.id, 0) for c in ranked]
    ideal_grades = list(grades.values())
    ndcg = ndcg_at_k(actual_grades, ideal_grades, k=k)

    # MRR
    mrr = 0.0
    for rank_idx, c in enumerate(ranked):
        if c.id in expected_ids:
            mrr = 1.0 / (rank_idx + 1)
            break

    # Precision@5
    top5 = ranked[:5]
    p5_hits = sum(1 for c in top5 if c.id in expected_ids)
    p5 = p5_hits / min(5, max(1, len(expected_ids)))

    # Recall@10
    top10 = ranked[:10]
    r10_hits = sum(1 for c in top10 if c.id in expected_ids)
    r10 = r10_hits / max(1, len(expected_ids))

    return ndcg, mrr, p5, r10


def build_benchmark_dataset() -> List[Dict[str, Any]]:
    return [
        # 1. Broad Searches
        {
            "query": "popular songs",
            "category": "Broad searches",
            "expected_ids": ["despacito_hit", "bad_guy_billie", "shape_of_you"],
            "grades": {
                "despacito_hit": 3,
                "shape_of_you": 3,
                "bad_guy_billie": 3,
                "trending_2026_hit": 2,
                "obscure_demo_1": 0,
                "obscure_demo_2": 0,
                "unrelated_clip": 0,
            },
            "candidates": [
                CandidateResult(
                    id="obscure_demo_1",
                    title="Popular Songs - My Acoustic Cover at Home",
                    uploader="bedroom_musician",
                    views=150,
                    likes=5,
                    release_year=2021,
                ),
                CandidateResult(
                    id="despacito_hit",
                    title="Luis Fonsi - Despacito ft. Daddy Yankee",
                    uploader="Luis Fonsi",
                    views=8200000000,
                    likes=53000000,
                    listeners=110000000,
                    chart_rank=1,
                    release_year=2017,
                ),
                CandidateResult(
                    id="shape_of_you",
                    title="Ed Sheeran - Shape of You",
                    uploader="Ed Sheeran",
                    views=6100000000,
                    likes=34000000,
                    listeners=95000000,
                    chart_rank=1,
                    release_year=2017,
                ),
                CandidateResult(
                    id="bad_guy_billie",
                    title="Billie Eilish - bad guy",
                    uploader="Billie Eilish",
                    views=1350000000,
                    likes=12000000,
                    listeners=85000000,
                    chart_rank=1,
                    release_year=2019,
                ),
                CandidateResult(
                    id="trending_2026_hit",
                    title="Nova Lights - Stellar Beats (Global Viral)",
                    uploader="Nova Sounds",
                    views=45000000,
                    likes=4200000,
                    listeners=28000000,
                    chart_rank=3,
                    is_trending=True,
                    release_year=2026,
                ),
                CandidateResult(
                    id="obscure_demo_2",
                    title="Popular Songs I Like (Guitar Practice)",
                    uploader="novice_strummer",
                    views=42,
                    likes=1,
                    release_year=2018,
                ),
                CandidateResult(
                    id="unrelated_clip",
                    title="Top 10 Most Popular Songs in Video Games (Discussion)",
                    uploader="GamerZone",
                    views=85000,
                    likes=3500,
                    is_music=False,
                    content_type="video",
                ),
            ],
        },
        {
            "query": "trending music",
            "category": "Broad searches",
            "expected_ids": ["trending_2026_hit", "viral_tiktok_2026"],
            "grades": {
                "trending_2026_hit": 3,
                "viral_tiktok_2026": 3,
                "bad_guy_billie": 2,
                "old_radio_1994": 0,
                "obscure_loop": 0,
            },
            "candidates": [
                CandidateResult(
                    id="old_radio_1994",
                    title="Trending Music from 1994 (Vintage Cassette)",
                    uploader="Tape Collector",
                    views=220,
                    release_year=1994,
                ),
                CandidateResult(
                    id="viral_tiktok_2026",
                    title="Luna Ray - Starlight Symphony",
                    uploader="Luna Ray",
                    views=88000000,
                    likes=6800000,
                    listeners=38000000,
                    chart_rank=1,
                    is_trending=True,
                    release_year=2026,
                ),
                CandidateResult(
                    id="trending_2026_hit",
                    title="Nova Lights - Stellar Beats",
                    uploader="Nova Sounds",
                    views=45000000,
                    likes=4200000,
                    listeners=28000000,
                    chart_rank=3,
                    is_trending=True,
                    release_year=2026,
                ),
                CandidateResult(
                    id="bad_guy_billie",
                    title="Billie Eilish - bad guy",
                    uploader="Billie Eilish",
                    views=1350000000,
                    release_year=2019,
                ),
                CandidateResult(
                    id="obscure_loop",
                    title="trending music beat loop 128bpm",
                    uploader="RandomBeats",
                    views=12,
                    release_year=2023,
                ),
            ],
        },
        # 2. Exact Title Searches
        {
            "query": "bad guy",
            "category": "Exact title searches",
            "expected_ids": ["bad_guy_billie"],
            "grades": {
                "bad_guy_billie": 3,
                "bad_guy_obscure": 1,
                "bad_guy_parody": 0,
                "gameplay_bad_guy": 0,
            },
            "candidates": [
                CandidateResult(
                    id="bad_guy_obscure",
                    title="bad guy",
                    uploader="Indie Jam 2012",
                    views=120,
                    likes=4,
                    release_year=2012,
                ),
                CandidateResult(
                    id="bad_guy_billie",
                    title="Billie Eilish - bad guy",
                    uploader="Billie Eilish",
                    views=1350000000,
                    likes=12000000,
                    listeners=85000000,
                    chart_rank=1,
                    release_year=2019,
                ),
                CandidateResult(
                    id="bad_guy_parody",
                    title="I'm the Bad Guy (Parody Animation)",
                    uploader="CartoonHub",
                    views=5200000,
                    likes=210000,
                    content_type="animation",
                ),
                CandidateResult(
                    id="gameplay_bad_guy",
                    title="GTA 5 Playing as Bad Guy in Heist",
                    uploader="ProGaming",
                    views=890000,
                    is_music=False,
                    content_type="gameplay",
                ),
            ],
        },
        {
            "query": "I Wanna Be Yours",
            "category": "Exact title searches",
            "expected_ids": ["arctic_monkeys_iwby"],
            "grades": {
                "arctic_monkeys_iwby": 3,
                "iwby_ukulele_cover": 1,
                "poem_reading": 0,
            },
            "candidates": [
                CandidateResult(
                    id="iwby_ukulele_cover",
                    title="I Wanna Be Yours (Ukulele Cover)",
                    uploader="Sarah Music",
                    views=1800,
                    likes=90,
                    release_year=2022,
                ),
                CandidateResult(
                    id="arctic_monkeys_iwby",
                    title="Arctic Monkeys - I Wanna Be Yours",
                    uploader="Arctic Monkeys",
                    views=1500000000,
                    likes=14000000,
                    listeners=72000000,
                    chart_rank=2,
                    release_year=2013,
                ),
                CandidateResult(
                    id="poem_reading",
                    title="John Cooper Clarke - I Wanna Be Yours (Poetry Recital)",
                    uploader="Literature Society",
                    views=45000,
                    likes=1200,
                    is_music=False,
                    content_type="recital",
                ),
            ],
        },
        # 3. Title + Artist Searches
        {
            "query": "Porter Robinson Shelter",
            "category": "Title + artist searches",
            "expected_ids": ["shelter_official"],
            "grades": {
                "shelter_official": 3,
                "shelter_acoustic_live": 2,
                "shelter_reaction": 0,
                "despacito_mega": 0,
            },
            "candidates": [
                CandidateResult(
                    id="despacito_mega",
                    title="Luis Fonsi - Despacito ft. Daddy Yankee",
                    uploader="Luis Fonsi",
                    views=8200000000,
                    likes=53000000,
                    chart_rank=1,
                ),
                CandidateResult(
                    id="shelter_official",
                    title="Porter Robinson & Madeon - Shelter (Official Audio)",
                    uploader="Porter Robinson",
                    views=98000000,
                    likes=2100000,
                    listeners=19000000,
                    release_year=2016,
                ),
                CandidateResult(
                    id="shelter_reaction",
                    title="PRODUCER REACTS to Porter Robinson Shelter!",
                    uploader="MusicReacts",
                    views=45000,
                    is_music=False,
                    content_type="reaction",
                ),
                CandidateResult(
                    id="shelter_acoustic_live",
                    title="Porter Robinson - Shelter (Piano Live)",
                    uploader="Porter Robinson Fans",
                    views=650000,
                    likes=35000,
                    release_year=2017,
                ),
            ],
        },
        {
            "query": "Shiro Sagisu Number One",
            "category": "Title + artist searches",
            "expected_ids": ["shiro_number_one_original", "shiro_number_one_bankai"],
            "grades": {
                "shiro_number_one_bankai": 3,
                "shiro_number_one_original": 3,
                "bleach_gameplay": 0,
                "random_mega_hit": 0,
            },
            "candidates": [
                CandidateResult(
                    id="random_mega_hit",
                    title="Ed Sheeran - Perfect (Official Music Video)",
                    uploader="Ed Sheeran",
                    views=3800000000,
                    likes=21000000,
                    chart_rank=1,
                ),
                CandidateResult(
                    id="shiro_number_one_bankai",
                    title="Shiro SAGISU - Number One (Bankai Version) [Official Bleach TYBW OST]",
                    uploader="Shiro SAGISU - Topic",
                    views=14500000,
                    likes=350000,
                    listeners=4200000,
                    release_year=2022,
                ),
                CandidateResult(
                    id="shiro_number_one_original",
                    title="Shiro Sagisu - Number One (Bleach OST Original)",
                    uploader="Anime Soundtracks",
                    views=22000000,
                    likes=520000,
                    release_year=2004,
                ),
                CandidateResult(
                    id="bleach_gameplay",
                    title="BLEACH Rebirth of Souls Gameplay Walkthrough",
                    uploader="IGN",
                    views=350000,
                    is_music=False,
                    content_type="gameplay",
                ),
            ],
        },
        # 4. Ambiguous Song Titles
        {
            "query": "Shelter",
            "category": "Ambiguous song titles",
            "expected_ids": ["shelter_official"],
            "grades": {
                "shelter_official": 3,
                "shelter_obscure_indie": 1,
                "emergency_shelter_vlog": 0,
            },
            "candidates": [
                CandidateResult(
                    id="shelter_obscure_indie",
                    title="Shelter",
                    uploader="High School Band 2008",
                    views=85,
                    release_year=2008,
                ),
                CandidateResult(
                    id="shelter_official",
                    title="Porter Robinson & Madeon - Shelter",
                    uploader="Porter Robinson",
                    views=98000000,
                    likes=2100000,
                    listeners=19000000,
                    release_year=2016,
                ),
                CandidateResult(
                    id="emergency_shelter_vlog",
                    title="Building an Underground Survival Shelter in 24 Hours",
                    uploader="Bushcraft Survival",
                    views=4500000,
                    is_music=False,
                    content_type="video",
                ),
            ],
        },
        # 5. New Trending Songs vs Older Hits
        {
            "query": "Electric Horizon",
            "category": "New trending vs older hits",
            "expected_ids": ["trending_horizon_2026"],
            "grades": {
                "trending_horizon_2026": 3,
                "vintage_horizon_1998": 2,
                "garage_horizon_2015": 0,
            },
            "candidates": [
                CandidateResult(
                    id="vintage_horizon_1998",
                    title="Vintage Rockers - Electric Horizon (1998 Acoustic Live)",
                    uploader="Classic Archives",
                    views=200000000,
                    likes=2100000,
                    listeners=18000000,
                    release_year=2004,
                    is_trending=False,
                ),
                CandidateResult(
                    id="trending_horizon_2026",
                    title="K-Pop Sensation - Electric Horizon",
                    uploader="Trend Records",
                    views=50000000,
                    likes=3800000,
                    listeners=25000000,
                    chart_rank=2,
                    release_year=2026,
                    is_trending=True,
                ),
                CandidateResult(
                    id="garage_horizon_2015",
                    title="Electric Horizon Band Rehearsal",
                    uploader="Local Jam",
                    views=340,
                    release_year=2015,
                ),
            ],
        },
        # 6. Popular Songs vs Obscure Songs
        {
            "query": "Ditto",
            "category": "Popular vs obscure songs",
            "expected_ids": ["newjeans_ditto"],
            "grades": {
                "newjeans_ditto": 3,
                "ditto_obscure_rap": 0,
                "ditto_pokemon_clip": 0,
            },
            "candidates": [
                CandidateResult(
                    id="ditto_obscure_rap",
                    title="Ditto",
                    uploader="SoundCloud Rapper 2017",
                    views=45,
                    release_year=2017,
                ),
                CandidateResult(
                    id="newjeans_ditto",
                    title="NewJeans - Ditto (Official MV)",
                    uploader="HYBE LABELS",
                    views=180000000,
                    likes=4600000,
                    listeners=42000000,
                    chart_rank=1,
                    release_year=2022,
                ),
                CandidateResult(
                    id="ditto_pokemon_clip",
                    title="Ditto Transforms into Pikachu! (Funny Scene)",
                    uploader="PokeFans",
                    views=950000,
                    is_music=False,
                    content_type="clip",
                ),
            ],
        },
        # 7. Missing Popularity Metadata
        {
            "query": "Acoustic Serenade",
            "category": "Missing popularity metadata",
            "expected_ids": ["serenade_studio_master"],
            "grades": {
                "serenade_studio_master": 3,
                "guitar_tutorial_clickbait": 0,
                "random_vlog": 0,
            },
            "candidates": [
                CandidateResult(
                    id="guitar_tutorial_clickbait",
                    title="How to Play Guitar in 5 Minutes (Serenade lesson)",
                    uploader="Learn Guitar",
                    views=10000000,
                    likes=450000,
                    is_music=False,
                    content_type="tutorial",
                ),
                CandidateResult(
                    id="serenade_studio_master",
                    title="Acoustic Serenade - Official Studio Master",
                    uploader="Indie Artist Collective",
                    views=None,
                    likes=None,
                    listeners=None,
                    chart_rank=None,
                    release_year=2025,
                ),
                CandidateResult(
                    id="random_vlog",
                    title="Morning Serenade Coffee Routine",
                    uploader="DailyVlogs",
                    views=2500000,
                    is_music=False,
                    content_type="vlog",
                ),
            ],
        },
    ]


def rank_unboosted_baseline(query: SearchQuery, candidates: List[CandidateResult]) -> List[CandidateResult]:
    """Baseline ranker: sorts strictly by raw textual similarity, ignoring popularity, views, and trend flags."""
    from backend.search.relevance_engine import ngram_similarity, levenshtein_similarity

    q_norm = query.raw_query.lower().strip()
    scored = []
    for c in candidates:
        cand_copy = copy.copy(c)
        title_norm = (cand_copy.clean_title or cand_copy.title).lower()
        sim = 0.5 * ngram_similarity(q_norm, title_norm) + 0.5 * levenshtein_similarity(q_norm, title_norm)
        if query.media_type == "audio" and not cand_copy.is_music:
            sim *= 0.10
        cand_copy.score = sim
        scored.append(cand_copy)

    # Sort strictly by score, then id
    scored.sort(key=lambda x: (x.score, x.id), reverse=True)
    return scored


def run_benchmark():
    dataset = build_benchmark_dataset()

    print("=" * 85)
    print("KON Search 1.2 — Popularity-Aware Ranking Benchmark")
    print(f"Total Evaluated Benchmark Scenarios: {len(dataset)}")
    print(f"Native Rust Core Available: {rust_bridge.is_rust_available()}")
    print("=" * 85)

    # Collect results across 3 systems:
    # 1. Baseline (Un-boosted text-only)
    # 2. Upgraded: KON Search 1.2 Rei (Precision)
    # 3. Upgraded: KON Search 1.2 Rei Flash (Speed)

    systems = {
        "Baseline (Un-boosted)": {"ndcg": [], "mrr": [], "p5": [], "r10": [], "latencies": []},
        "KON Search 1.2 Rei": {"ndcg": [], "mrr": [], "p5": [], "r10": [], "latencies": []},
        "KON Search 1.2 Rei Flash": {"ndcg": [], "mrr": [], "p5": [], "r10": [], "latencies": []},
    }

    category_results = {}
    consistency_matches = 0
    total_queries = len(dataset)

    for item in dataset:
        q_text = item["query"]
        category = item["category"]
        expected_ids = set(item["expected_ids"])
        grades = item["grades"]
        raw_candidates = item["candidates"]

        if category not in category_results:
            category_results[category] = {
                "baseline_p1": 0,
                "rei_p1": 0,
                "flash_p1": 0,
                "total": 0,
            }
        category_results[category]["total"] += 1

        query = SearchQuery(raw_query=q_text, media_type="audio")

        # 1. Baseline
        t0 = time.perf_counter()
        baseline_ranked = rank_unboosted_baseline(query, [copy.copy(c) for c in raw_candidates])
        lat_base = (time.perf_counter() - t0) * 1000.0
        systems["Baseline (Un-boosted)"]["latencies"].append(lat_base)

        b_ndcg, b_mrr, b_p5, b_r10 = calculate_metrics(baseline_ranked, expected_ids, grades)
        systems["Baseline (Un-boosted)"]["ndcg"].append(b_ndcg)
        systems["Baseline (Un-boosted)"]["mrr"].append(b_mrr)
        systems["Baseline (Un-boosted)"]["p5"].append(b_p5)
        systems["Baseline (Un-boosted)"]["r10"].append(b_r10)
        if baseline_ranked and baseline_ranked[0].id in expected_ids:
            category_results[category]["baseline_p1"] += 1

        # 2. KON Search 1.2 Rei
        t0 = time.perf_counter()
        rei_ranked = rust_bridge.rank_candidates(query, [copy.copy(c) for c in raw_candidates])
        lat_rei = (time.perf_counter() - t0) * 1000.0
        systems["KON Search 1.2 Rei"]["latencies"].append(lat_rei)

        r_ndcg, r_mrr, r_p5, r_r10 = calculate_metrics(rei_ranked, expected_ids, grades)
        systems["KON Search 1.2 Rei"]["ndcg"].append(r_ndcg)
        systems["KON Search 1.2 Rei"]["mrr"].append(r_mrr)
        systems["KON Search 1.2 Rei"]["p5"].append(r_p5)
        systems["KON Search 1.2 Rei"]["r10"].append(r_r10)
        if rei_ranked and rei_ranked[0].id in expected_ids:
            category_results[category]["rei_p1"] += 1

        # 3. KON Search 1.2 Rei Flash
        t0 = time.perf_counter()
        flash_ranked = rust_bridge.rank_candidates_flash(query, [copy.copy(c) for c in raw_candidates])
        lat_flash = (time.perf_counter() - t0) * 1000.0
        systems["KON Search 1.2 Rei Flash"]["latencies"].append(lat_flash)

        f_ndcg, f_mrr, f_p5, f_r10 = calculate_metrics(flash_ranked, expected_ids, grades)
        systems["KON Search 1.2 Rei Flash"]["ndcg"].append(f_ndcg)
        systems["KON Search 1.2 Rei Flash"]["mrr"].append(f_mrr)
        systems["KON Search 1.2 Rei Flash"]["p5"].append(f_p5)
        systems["KON Search 1.2 Rei Flash"]["r10"].append(f_r10)
        if flash_ranked and flash_ranked[0].id in expected_ids:
            category_results[category]["flash_p1"] += 1

        # Consistency check: Did Rei and Rei Flash agree on the #1 ranked result?
        if rei_ranked and flash_ranked and rei_ranked[0].id == flash_ranked[0].id:
            consistency_matches += 1

    ranking_consistency_pct = (consistency_matches / total_queries) * 100.0

    # Summary table
    print("\n" + "=" * 85)
    print(f"{'Ranking System':<28} | {'NDCG@10':<9} | {'MRR':<7} | {'P@5':<7} | {'R@10':<7} | {'p50 Lat':<9} | {'p95 Lat'}")
    print("-" * 85)

    summary_data = {}
    for name, m in systems.items():
        avg_ndcg = sum(m["ndcg"]) / len(m["ndcg"])
        avg_mrr = sum(m["mrr"]) / len(m["mrr"])
        avg_p5 = sum(m["p5"]) / len(m["p5"])
        avg_r10 = sum(m["r10"]) / len(m["r10"])
        lats = sorted(m["latencies"])
        p50 = lats[len(lats) // 2]
        p95 = lats[int(len(lats) * 0.95)]
        print(f"{name:<28} | {avg_ndcg:9.3f} | {avg_mrr:7.3f} | {avg_p5*100:6.1f}% | {avg_r10*100:6.1f}% | {p50:6.3f} ms | {p95:6.3f} ms")
        summary_data[name] = {
            "ndcg10": round(avg_ndcg, 4),
            "mrr": round(avg_mrr, 4),
            "p5": round(avg_p5 * 100.0, 2),
            "r10": round(avg_r10 * 100.0, 2),
            "p50_ms": round(p50, 4),
            "p95_ms": round(p95, 4),
        }

    print("=" * 85)
    print(f"Ranking Consistency (Rei vs Rei Flash Top-1 Match): {ranking_consistency_pct:.1f}%")
    print("\nCategory Breakdown (Top-1 Accuracy / Precision@1):")
    print(f"{'Category':<32} | {'Baseline':<10} | {'Rei':<10} | {'Rei Flash'}")
    print("-" * 70)
    for cat, res in category_results.items():
        base_rate = (res["baseline_p1"] / res["total"]) * 100.0
        rei_rate = (res["rei_p1"] / res["total"]) * 100.0
        flash_rate = (res["flash_p1"] / res["total"]) * 100.0
        print(f"{cat:<32} | {base_rate:9.1f}% | {rei_rate:9.1f}% | {flash_rate:9.1f}%")

    # Export benchmark report JSON
    report = {
        "title": "KON Search 1.2 — Popularity-Aware Ranking Benchmark",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "ranking_consistency": f"{ranking_consistency_pct:.1f}%",
        "systems": summary_data,
        "categories": category_results,
    }
    with open("backend/search/benchmark/popularity_benchmark_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print("\nBenchmark report saved to backend/search/benchmark/popularity_benchmark_report.json")


if __name__ == "__main__":
    run_benchmark()
