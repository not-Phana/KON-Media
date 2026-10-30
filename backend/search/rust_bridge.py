"""Bridge module connecting Python backend to native Rust search core (kon_search_core).

Adopts a safe fallback design:
1. Tries to load compiled native Rust PyO3 extension `kon_search_core`.
   If loaded: active engine is "rust-core/1.2.0".
2. If uncompiled or missing from environment: logs an explicit diagnostic and falls back
   to the verified pure-Python relevance engine with identical semantics.
   Active engine is "python-fallback/1.2.0".
"""

import json
import logging
from typing import Any, Dict, List, Optional
from backend.search.models import CandidateResult, SearchQuery

log = logging.getLogger("kon_search_bridge")

_RUST_AVAILABLE = False
_RUST_MODULE = None

try:
    import kon_search_core as _core  # type: ignore

    _RUST_MODULE = _core
    _RUST_AVAILABLE = True
    log.info("KON Search native Rust extension loaded successfully (version: %s)", getattr(_core, "__version__", "1.2.0"))
except ImportError as err:
    log.info(
        "KON Search native Rust extension (kon_search_core) not compiled or importable (%s). "
        "Operating with verified Python relevance engine (engine: python-fallback/1.2.0).",
        err,
    )


def is_rust_available() -> bool:
    """Return whether the native Rust search core is active."""
    return _RUST_AVAILABLE


def get_active_engine_name() -> str:
    """Return diagnostic identification string of the currently active search engine."""
    if _RUST_AVAILABLE:
        return f"rust-core/{getattr(_RUST_MODULE, '__version__', '1.2.0')}"
    return "python-fallback/1.2.0"


def rank_candidates(
    query: SearchQuery,
    candidates: List[CandidateResult],
    limit: Optional[int] = None,
) -> List[CandidateResult]:
    """Rank candidates using native Rust core or Python fallback engine."""
    if not candidates:
        return []

    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            # Serialize query
            query_dict = {
                "raw_query": query.raw_query,
                "normalized_query": query.normalized_query,
                "expected_artist": query.expected_artist,
                "expected_title": query.expected_title,
                "expected_duration": query.expected_duration,
                "version_hint": query.version_hint,
                "media_type": query.media_type,
            }
            # Serialize candidates
            candidates_list = [
                {
                    "id": c.id,
                    "title": c.title,
                    "clean_title": c.clean_title,
                    "song_title": c.song_title,
                    "artist": c.artist,
                    "context_source": c.context_source,
                    "is_cluttered": c.is_cluttered,
                    "is_cutscene": c.is_cutscene,
                    "uploader": c.uploader,
                    "duration": c.duration,
                    "views": c.views,
                    "platform": c.platform,
                    "url": c.url,
                }
                for c in candidates
            ]

            result_json = _RUST_MODULE.rank_candidates_json(
                json.dumps(query_dict),
                json.dumps(candidates_list),
            )
            parsed: List[Dict[str, Any]] = json.loads(result_json)

            # Map back to CandidateResult instances
            cand_by_id = {c.id: c for c in candidates}
            ranked: List[CandidateResult] = []
            for item in parsed:
                cid = item["id"]
                original = cand_by_id.get(cid)
                if original is not None:
                    original.score = item.get("score", 0.0)
                    original.confidence = item.get("confidence", "medium")
                    original.features = item.get("features", {})
                    original.explanation = item.get("explanations", [])
                    if item.get("clean_title"):
                        original.clean_title = item.get("clean_title")
                    if item.get("song_title"):
                        original.song_title = item.get("song_title")
                    if item.get("artist"):
                        original.artist = item.get("artist")
                    if item.get("context_source"):
                        original.context_source = item.get("context_source")
                    if item.get("is_cluttered") is not None:
                        original.is_cluttered = item.get("is_cluttered", False)
                    if item.get("is_cutscene") is not None:
                        original.is_cutscene = item.get("is_cutscene", False)
                    ranked.append(original)

            if limit is not None:
                return ranked[:limit]
            return ranked
        except Exception as e:
            log.warning("Rust search ranking encountered an error (%s); falling back to Python relevance engine.", e)

    # Fallback path
    from backend.search.relevance_engine import rank_candidates as py_rank_candidates

    return py_rank_candidates(query, candidates, limit=limit)
