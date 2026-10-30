"""Unified SearchEngine coordinating providers, normalization, ranking, and feedback."""

import asyncio
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional
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
        pool_limit = min(max(limit + 8, 15), 30)
        candidates = self.aggregator.aggregate_candidates(
            query=search_term,
            limit_per_provider=pool_limit,
            ffmpeg_path=ffmpeg_path,
            preferred_provider=preferred_provider,
            media_type=media_type,
        )

        # 3b. Retrieve franchise/game theme or canonical soundtrack if known association exists
        has_franchise_role = any(k in clean_q.lower() for k in ("opening", "ending", " op", " ed", "theme", "ost", "soundtrack"))
        from backend.search.normalization import resolve_soundtrack_associations
        associated_songs = resolve_soundtrack_associations(clean_q)

        soundtrack_query_target = None
        if associated_songs:
            soundtrack_query_target = associated_songs[0]
        elif has_franchise_role and not (search_query.detected_artist and search_query.detected_title):
            soundtrack_query_target = clean_q

        if soundtrack_query_target and soundtrack_query_target.lower() != clean_q.lower():
            extra_candidates = self.aggregator.aggregate_candidates(
                query=soundtrack_query_target,
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

    async def search_live_stream(
        self,
        query: str,
        limit: int = 20,
        media_type: str = "all",
        preferred_provider: Optional[str] = None,
        ffmpeg_path: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream real-time search progress, multi-provider candidates, and live re-ranking."""
        clean_q = query.strip()
        if not clean_q:
            yield {
                "stage": "no_results",
                "message": "Search query cannot be empty",
                "status": "no_results",
                "results": [],
                "count": 0,
            }
            return

        # 0. Check cache
        cache_key = self.cache.make_key(clean_q, media_type=media_type, provider=preferred_provider, limit=limit)
        cached = self.cache.get(cache_key)
        if cached is not None:
            yield {
                "stage": "completed",
                "message": "Completed from high-speed cache",
                "status": "complete",
                "results": cached,
                "count": len(cached),
                "providers_completed": ["cache"],
                "providers_timed_out": [],
                "providers_failed": [],
                "engine": self.get_active_engine(),
                "product": "KON Search 1.2 Rei",
            }
            return

        # 1. Stage: Understanding your search
        search_query = parse_query_intent(
            clean_q,
            media_type=media_type,
        )
        yield {
            "stage": "understanding",
            "message": "Understanding your search",
            "details": {
                "detected_title": search_query.detected_title,
                "detected_artist": search_query.detected_artist,
                "version_hint": search_query.version_hint,
                "qualifier": search_query.qualifier,
                "edition": search_query.edition,
            },
            "query": clean_q,
        }

        # 2. Stage: Searching providers
        active_providers = list(self.aggregator.providers)
        if media_type == "video":
            active_providers = [p for p in active_providers if p.name != "soundcloud"]
        if preferred_provider:
            active_providers.sort(key=lambda p: 0 if p.name == preferred_provider else 1)

        provider_names = [p.name for p in active_providers]
        yield {
            "stage": "searching",
            "message": f"Querying {len(active_providers)} providers: {', '.join(provider_names)}",
            "providers": provider_names,
        }

        pool_limit = min(max(limit + 8, 15), 30)
        accumulated_candidates: List[CandidateResult] = []
        completed_providers: List[str] = []
        timed_out_providers: List[str] = []
        failed_providers: List[str] = []

        async def run_single_provider(provider):
            try:
                res = await asyncio.wait_for(
                    asyncio.to_thread(provider.search, clean_q, pool_limit, ffmpeg_path),
                    timeout=12.0,
                )
                return provider.name, res, None
            except asyncio.TimeoutError:
                return provider.name, [], "timeout"
            except Exception as e:
                return provider.name, [], str(e)

        # Determine if soundtrack/theme retrieval is available for this entity
        has_franchise_role = any(k in clean_q.lower() for k in ("opening", "ending", " op", " ed", "theme", "ost", "soundtrack"))
        from backend.search.normalization import resolve_soundtrack_associations
        associated_songs = resolve_soundtrack_associations(clean_q)

        soundtrack_query_target = None
        if associated_songs:
            soundtrack_query_target = associated_songs[0]
        elif has_franchise_role and not (search_query.detected_artist and search_query.detected_title):
            soundtrack_query_target = clean_q

        tasks = [asyncio.create_task(run_single_provider(p)) for p in active_providers]
        if soundtrack_query_target and soundtrack_query_target.lower() != clean_q.lower():
            async def run_soundtrack_provider(provider, target_q):
                try:
                    res = await asyncio.wait_for(
                        asyncio.to_thread(provider.search, target_q, min(pool_limit // 2, 8), ffmpeg_path),
                        timeout=8.0,
                    )
                    return f"{provider.name} (soundtrack)", res, None
                except Exception:
                    return f"{provider.name} (soundtrack)", [], None

            for p in active_providers:
                tasks.append(asyncio.create_task(run_soundtrack_provider(p, soundtrack_query_target)))

        for coro in asyncio.as_completed(tasks):
            p_name, candidates, err = await coro
            if err == "timeout":
                timed_out_providers.append(p_name)
            elif err:
                failed_providers.append(p_name)
            else:
                completed_providers.append(p_name)
                if candidates:
                    accumulated_candidates.extend(candidates)
                    from backend.search.relevance_engine import deduplicate_candidates
                    accumulated_candidates = deduplicate_candidates(accumulated_candidates)

                    yield {
                        "stage": "collecting",
                        "message": f"Collected {len(candidates)} candidates from {p_name}",
                        "provider": p_name,
                        "candidate_count": len(candidates),
                        "total_candidates": len(accumulated_candidates),
                    }

                    yield {
                        "stage": "matching",
                        "message": "Matching & ranking candidates by relevance",
                        "provider": p_name,
                    }

                    ranked = rust_bridge.rank_candidates(query=search_query, candidates=accumulated_candidates)
                    partial_results = [c.to_dict() for c in ranked[:limit]]
                    pending = [p for p in provider_names if p not in completed_providers and p not in timed_out_providers and p not in failed_providers]

                    yield {
                        "stage": "updating",
                        "message": f"Updated results with {p_name}",
                        "results": partial_results,
                        "count": len(partial_results),
                        "is_partial": len(pending) > 0,
                        "providers_completed": list(completed_providers),
                        "providers_pending": pending,
                    }

        # Final ranking and completion
        if accumulated_candidates:
            ranked = rust_bridge.rank_candidates(query=search_query, candidates=accumulated_candidates)
            final_results = [c.to_dict() for c in ranked[:limit]]
            self.cache.set(cache_key, final_results)

            if timed_out_providers or failed_providers:
                yield {
                    "stage": "partial_results",
                    "message": f"Search completed with partial results ({', '.join(timed_out_providers + failed_providers)} timed out or failed)",
                    "status": "partial",
                    "results": final_results,
                    "count": len(final_results),
                    "providers_completed": completed_providers,
                    "providers_timed_out": timed_out_providers,
                    "providers_failed": failed_providers,
                    "engine": self.get_active_engine(),
                    "product": "KON Search 1.2 Rei",
                }
            else:
                yield {
                    "stage": "completed",
                    "message": "Search completed",
                    "status": "complete",
                    "results": final_results,
                    "count": len(final_results),
                    "providers_completed": completed_providers,
                    "providers_timed_out": timed_out_providers,
                    "providers_failed": failed_providers,
                    "engine": self.get_active_engine(),
                    "product": "KON Search 1.2 Rei",
                }
        else:
            yield {
                "stage": "no_results",
                "message": "No good matches found",
                "status": "no_results",
                "results": [],
                "count": 0,
                "providers_completed": completed_providers,
                "providers_timed_out": timed_out_providers,
                "providers_failed": failed_providers,
                "engine": self.get_active_engine(),
                "product": "KON Search 1.2 Rei",
            }

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
