"""Layer D: Local search feedback storage, verified match memory, and evidence-driven weight tuning."""

import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from backend.config import STATE_DIR
from backend.storage.storage import AtomicJsonStore
from backend.search.models import CandidateResult, RankerConfig, SearchFeedbackEntry, SearchQuery
from backend.search.normalization import normalize_text

log = logging.getLogger("kon_search_feedback")


class SearchFeedbackStore:
    """Manages persistent, local-first search feedback and verified matches."""

    def __init__(self, state_dir: Path = STATE_DIR):
        self.file_path = state_dir / "search_feedback.json"
        self.store = AtomicJsonStore(self.file_path, default_value=[])

    def get_all(self) -> List[Dict[str, Any]]:
        """Return all recorded feedback entries."""
        return self.store.load()

    def record_selection(
        self,
        query: str,
        selected_id: str,
        selected_title: str,
        selected_url: str,
        is_mismatch: bool = False,
        reason: Optional[str] = None,
        provider: str = "youtube",
    ) -> Dict[str, Any]:
        """Record a user's selection or mismatch report."""
        norm_q = normalize_text(query)
        entry = SearchFeedbackEntry(
            query=norm_q,
            selected_id=selected_id,
            selected_title=selected_title,
            selected_url=selected_url,
            is_mismatch=is_mismatch,
            reason=reason,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            provider=provider,
        )

        entries = self.get_all()
        # Prepend latest
        entries.insert(0, entry.to_dict())
        # Cap to 1000 items
        if len(entries) > 1000:
            entries = entries[:1000]
        self.store.save(entries)
        return entry.to_dict()

    def get_verified_lookup(self) -> Dict[str, str]:
        """Build a lookup map of normalized queries to verified target IDs/URLs."""
        entries = self.get_all()
        lookup: Dict[str, str] = {}
        # Iterate in reverse so newer entries take precedence
        for e in reversed(entries):
            if not e.get("is_mismatch"):
                q = e.get("query", "")
                target = e.get("selected_id") or e.get("selected_url")
                if q and target:
                    lookup[q] = target
        return lookup

    def clear(self) -> None:
        self.store.save([])


def tune_weights_on_evidence(
    examples: List[Dict[str, Any]],
    eval_rank_fn,
    base_config: Optional[RankerConfig] = None,
) -> Tuple[RankerConfig, float]:
    """Evidence-driven parameter update: grid-search ranking weights to maximize MRR on examples.

    Runs an evidence-based parameter update without external cloud dependencies.
    """
    from backend.search.benchmark.evaluator import BenchmarkEvaluator

    evaluator = BenchmarkEvaluator(examples)
    best_config = base_config or RankerConfig()
    best_score = evaluator.evaluate(lambda q, c: eval_rank_fn(q, c, best_config))["mrr"]

    # Candidate weight perturbations
    candidate_variations = [
        # (weight_exact, weight_fuzzy, weight_artist, weight_version)
        (0.40, 0.20, 0.20, 0.20),
        (0.35, 0.25, 0.20, 0.20),
        (0.30, 0.30, 0.20, 0.20),
        (0.30, 0.20, 0.25, 0.25),
        (0.25, 0.25, 0.25, 0.25),
    ]

    for w_exact, w_fuzzy, w_artist, w_version in candidate_variations:
        candidate_cfg = RankerConfig(
            weight_exact_title=w_exact,
            weight_fuzzy_title=w_fuzzy,
            weight_artist_match=w_artist,
            weight_version_match=w_version,
            weight_token_overlap=0.15,
            weight_duration_match=0.15,
            weight_feedback_boost=0.25,
        )
        report = evaluator.evaluate(lambda q, c: eval_rank_fn(q, c, candidate_cfg))
        cand_mrr = report["mrr"]
        if cand_mrr > best_score:
            best_score = cand_mrr
            best_config = candidate_cfg

    return best_config, best_score
