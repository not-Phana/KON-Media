"""Unified SearchEngine coordinating providers, normalization, ranking, and feedback."""

import logging
from typing import Any, Dict, List, Optional
from backend.search.models import CandidateResult, RankerConfig, SearchQuery
from backend.search.normalization import parse_query_intent
from backend.search.ranking import rank_candidates
from backend.search.providers import MultiProviderAggregator, SearchProvider
from backend.search.feedback import SearchFeedbackStore
from backend.search.learning_model import SearchLearningModel
from backend.search.cache import SearchCache, get_shared_search_cache
import backend.search.rust_bridge as rust_bridge

log = logging.getLogger("kon_search_engine")

_shared_learning_model: Optional[SearchLearningModel] = None


def get_shared_learning_model() -> SearchLearningModel:
    global _shared_learning_model
    if _shared_learning_model is None:
        _shared_learning_model = SearchLearningModel()
    return _shared_learning_model


class SearchEngine:
    """Unified cross-platform search engine with multi-signal ranking and evidence learning."""

    def __init__(
        self,
        aggregator: Optional[MultiProviderAggregator] = None,
        config: Optional[RankerConfig] = None,
        feedback_store: Optional[SearchFeedbackStore] = None,
        learning_model: Optional[SearchLearningModel] = None,
        cache: Optional[SearchCache] = None,
    ):
        self.aggregator = aggregator or MultiProviderAggregator()
        self.config = config or RankerConfig()
        self.feedback_store = feedback_store or SearchFeedbackStore()
        self.learning_model = learning_model or get_shared_learning_model()
        self.cache = cache or get_shared_search_cache()

    def search(
        self,
        query: str,
        limit: int = 5,
        media_type: str = "all",
        preferred_provider: Optional[str] = None,
        expected_artist: Optional[str] = None,
        expected_title: Optional[str] = None,
        expected_duration: Optional[float] = None,
        ffmpeg_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Search across providers, normalize, rank, and return formatted candidates."""
        clean_q = query.strip()
        if not clean_q:
            return []

        # 0. Check ultra-fast in-memory/TTL search cache (~0.001s)
        cache_key = self.cache.make_key(clean_q, media_type=media_type, provider=preferred_provider, limit=limit)
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        # 1. Parse structured query intent
        search_query = parse_query_intent(
            clean_q,
            expected_artist=expected_artist,
            expected_title=expected_title,
            expected_duration=expected_duration,
            media_type=media_type,
        )

        # 2. Formulate search query without destructive query mutation
        # Preserve user query intact - never poison search term with blind unigram associations or guesses
        search_term = clean_q

        # 3. Retrieve candidates from providers concurrently with broad candidate pool
        pool_limit = min(max(limit * 3, 24), 60)
        candidates = self.aggregator.aggregate_candidates(
            query=search_term,
            limit_per_provider=pool_limit,
            ffmpeg_path=ffmpeg_path,
            preferred_provider=preferred_provider,
            media_type=media_type,
        )

        # 3b. If seeking audio or theme and query resolves to a specific soundtrack song, retrieve the official artist release
        from backend.search.normalization import resolve_soundtrack_associations
        associated_songs = resolve_soundtrack_associations(clean_q)
        if associated_songs and (media_type == "audio" or any(k in clean_q.lower() for k in ("opening", "ending", "op", "ed", "theme", "ost", "song"))):
            clean_song_target = associated_songs[0]
            if clean_song_target.lower() != clean_q.lower():
                extra_candidates = self.aggregator.aggregate_candidates(
                    query=clean_song_target,
                    limit_per_provider=min(pool_limit // 2, 8),
                    ffmpeg_path=ffmpeg_path,
                    preferred_provider=preferred_provider,
                    media_type=media_type,
                )
                candidates.extend(extra_candidates)

        if not candidates:
            return []

        # 4. Load historical verified feedback lookup
        feedback_lookup = self.feedback_store.get_verified_lookup()

        # 5. Rank candidates using native Rust search core (or verified Python relevance fallback)
        ranked = rust_bridge.rank_candidates(
            query=search_query,
            candidates=candidates,
        )

        # 6. Apply verified historical user feedback boost if available
        norm_key = search_query.normalized_query
        if feedback_lookup and norm_key in feedback_lookup:
            verified_id = feedback_lookup[norm_key]
            for i, c in enumerate(ranked):
                if c.id == verified_id:
                    c.score += 1.0
                    if "Verified user match from historical feedback" not in c.explanation:
                        c.explanation.append("Verified user match from historical feedback")
                    # Move to front
                    verified_cand = ranked.pop(i)
                    ranked.insert(0, verified_cand)
                    break

        # 7. Format results for API / UI consumers and store in fast cache
        results = [c.to_dict() for c in ranked[:limit]]
        self.cache.set(cache_key, results)
        return results

    def get_active_engine(self) -> str:
        """Return diagnostic engine identifier."""
        return rust_bridge.get_active_engine_name()

    def record_feedback(
        self,
        query: str,
        selected_id: str,
        selected_title: str,
        selected_url: str,
        is_mismatch: bool = False,
        reason: Optional[str] = None,
        provider: str = "youtube",
    ) -> Dict[str, Any]:
        """Record user confirmation or mismatch for continuous learning and perform online SGD."""
        res = self.feedback_store.record_selection(
            query=query,
            selected_id=selected_id,
            selected_title=selected_title,
            selected_url=selected_url,
            is_mismatch=is_mismatch,
            reason=reason,
            provider=provider,
        )

        # Online learning update
        try:
            label = 0.0 if is_mismatch else 1.0
            feats = {
                "exact_title": 0.8 if label == 1.0 else 0.2,
                "fuzzy_title": 0.8 if label == 1.0 else 0.2,
                "token_overlap": 0.8 if label == 1.0 else 0.1,
                "artist_match": 0.8 if label == 1.0 else 0.2,
                "duration_compat": 0.9,
                "version_compat": 1.0 if label == 1.0 else 0.3,
                "audio_affinity": 0.8,
            }
            loss = self.learning_model.train_step(query, selected_title, feats, label)
            self.learning_model.save_model()
            res["learning_update"] = {
                "loss": round(loss, 4),
                "total_updates": self.learning_model.metadata["total_updates"],
            }
        except Exception as e:
            log.warning("Online training step failed: %s", e)

        return res

    def self_train(
        self,
        download_history: Optional[List[Dict[str, Any]]] = None,
        epochs: int = 5,
    ) -> Dict[str, Any]:
        """Trigger an autonomous batch training pass across feedback signals and download history."""
        feedback_entries = self.feedback_store.get_all()
        history = download_history or []
        train_results = self.learning_model.self_train(
            feedback_entries=feedback_entries,
            download_history=history,
            epochs=epochs,
        )
        return train_results
