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
from backend.search.normalization import normalize_text

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


def is_rust_core_available() -> bool:
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
                "normalized_query": query.normalized_query or (normalize_text(query.raw_query) if query.raw_query else ""),
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
                    if item.get("is_music") is not None:
                        original.is_music = bool(item.get("is_music"))
                    if item.get("content_type"):
                        original.content_type = item.get("content_type")
                    ranked.append(original)

            if limit is not None:
                return ranked[:limit]
            return ranked
        except Exception as e:
            log.warning("Rust search ranking encountered an error (%s); falling back to Python relevance engine.", e)

    # Fallback path
    from backend.search.relevance_engine import rank_candidates as py_rank_candidates

    return py_rank_candidates(query, candidates, limit=limit)


def rank_candidates_flash(
    query: SearchQuery,
    candidates: List[CandidateResult],
    limit: Optional[int] = None,
) -> List[CandidateResult]:
    """Rank candidates using ultra-fast Flash pipeline in native Rust (or fast fallback)."""
    if not candidates:
        return []

    if _RUST_AVAILABLE and _RUST_MODULE is not None and hasattr(_RUST_MODULE, "rank_candidates_flash_json"):
        try:
            query_dict = {
                "raw_query": query.raw_query,
                "normalized_query": query.normalized_query or (normalize_text(query.raw_query) if query.raw_query else ""),
                "expected_artist": query.expected_artist,
                "expected_title": query.expected_title,
                "expected_duration": query.expected_duration,
                "version_hint": query.version_hint,
                "media_type": query.media_type,
            }
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

            result_json = _RUST_MODULE.rank_candidates_flash_json(
                json.dumps(query_dict),
                json.dumps(candidates_list),
                limit,
            )
            parsed: List[Dict[str, Any]] = json.loads(result_json)

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
                    if item.get("is_music") is not None:
                        original.is_music = bool(item.get("is_music"))
                    if item.get("content_type"):
                        original.content_type = item.get("content_type")
                    ranked.append(original)

            if limit is not None:
                return ranked[:limit]
            return ranked
        except Exception as e:
            log.warning("Rust Flash ranking encountered an error (%s); falling back to precision ranking.", e)

    return rank_candidates(query, candidates, limit=limit)


def get_rust_suggestions_flash(query: str, media_type: str = "audio", limit: int = 6) -> Optional[List[Dict[str, Any]]]:
    """Retrieve fast search suggestions from native Rust core in Flash mode."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None and hasattr(_RUST_MODULE, "get_search_suggestions_flash_json"):
        try:
            res_json = _RUST_MODULE.get_search_suggestions_flash_json(query, media_type, limit)
            return json.loads(res_json)
        except Exception as err:
            log.warning("Rust Flash suggestions call failed (%s); falling back.", err)
    return get_rust_suggestions(query, media_type, limit)


def get_rust_suggestions(query: str, media_type: str = "audio", limit: int = 6) -> Optional[List[Dict[str, Any]]]:
    """Retrieve search suggestions from native Rust core if available."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            res_json = _RUST_MODULE.get_search_suggestions_json(query, media_type, limit)
            return json.loads(res_json)
        except Exception as err:
            log.warning("Rust suggestions call failed (%s); falling back to Python pipeline.", err)
    return None


def parse_rust_intent(query: str) -> Optional[Dict[str, Any]]:
    """Parse query intent using native Rust engine."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            res_json = _RUST_MODULE.parse_query_intent_json(query)
            return json.loads(res_json)
        except Exception as err:
            log.warning("Rust intent parsing failed (%s); falling back to Python.", err)
    return None


def parse_rust_entity(title: str, uploader: str = "") -> Optional[Dict[str, Any]]:
    """Parse cluttered candidate title into clean song/artist/context using native Rust."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            res_json = _RUST_MODULE.parse_media_entity_json(title, uploader)
            return json.loads(res_json)
        except Exception as err:
            log.warning("Rust entity parsing failed (%s); falling back to Python.", err)
    return None


def rust_cache_get(key: str) -> Optional[str]:
    """Get value from global native Rust cache."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            return _RUST_MODULE.cache_get(key)
        except Exception:
            pass
    return None


def rust_cache_insert(key: str, value: str, ttl_secs: Optional[int] = None) -> None:
    """Insert key-value pair into global native Rust cache."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            _RUST_MODULE.cache_insert(key, value, ttl_secs)
        except Exception:
            pass


def evaluate_rust_stream_pair(video: Dict[str, Any], audio: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Evaluate video and audio stream compatibility and pairing score in native Rust."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            res_json = _RUST_MODULE.evaluate_stream_pair_json(json.dumps(video), json.dumps(audio))
            return json.loads(res_json)
        except Exception as err:
            log.warning("Rust stream pair evaluation failed (%s).", err)
    return None


def verify_rust_audio_samples(samples: List[float], sample_rate: int = 44100) -> Optional[Dict[str, Any]]:
    """Verify audio samples for silence, RMS energy, and distortion in native Rust."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            res_json = _RUST_MODULE.verify_audio_samples_json(samples, sample_rate)
            return json.loads(res_json)
        except Exception as err:
            log.warning("Rust audio verification failed (%s).", err)
    return None


def classify_rust_media(title: str, uploader: str = "", duration_secs: float = 0.0) -> Optional[Dict[str, Any]]:
    """Classify media title into song, soundtrack, or non-music video in native Rust."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            res_json = _RUST_MODULE.classify_media_candidate_json(title, uploader, duration_secs)
            return json.loads(res_json)
        except Exception as err:
            log.warning("Rust media classification failed (%s).", err)
    return None


def search_rust_soundtrack(query: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
    """Search verified soundtrack database in native Rust."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            res_json = _RUST_MODULE.search_soundtrack_db_json(query, limit)
            return json.loads(res_json)
        except Exception as err:
            log.warning("Rust soundtrack DB lookup failed (%s).", err)
    return None


def search_rust_catalog(query: str, limit: int = 10) -> Optional[List[Dict[str, Any]]]:
    """Search canonical discography tracks in native Rust."""
    if _RUST_AVAILABLE and _RUST_MODULE is not None:
        try:
            res_json = _RUST_MODULE.search_catalog_tracks_json(query, limit)
            return json.loads(res_json)
        except Exception as err:
            log.warning("Rust catalog tracks lookup failed (%s).", err)
    return None
