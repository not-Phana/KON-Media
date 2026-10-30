"""Local-first adaptive search suggestion memory for KON Search 1.2 Rei.

Maintains bounded local user search refinements and verified suggestion history.
Zero cloud tracking, zero account requirements, fully transparent and clearable.
"""

import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import STATE_DIR
from backend.search.normalization import normalize_text
from backend.storage.storage import AtomicJsonStore

log = logging.getLogger("kon_adaptive_suggestions")

MAX_SUGGESTION_HISTORY = 100


class AdaptiveSuggestionStore:
    """Manages persistent local suggestion history and query refinements."""

    def __init__(self, state_dir: Path = STATE_DIR):
        self.state_file = state_dir / "suggestion_history.json"
        self.store = AtomicJsonStore(
            self.state_file,
            default_value={"history": [], "refinements": {}},
        )

    def record_selection(
        self,
        query: str,
        title: str,
        artist: Optional[str] = None,
        category: str = "song",
        platform: str = "youtube",
        url: Optional[str] = None,
        thumbnail: Optional[str] = None,
        duration: Optional[float] = None,
    ) -> None:
        """Record a selected suggestion into bounded local history."""
        clean_q = query.strip()
        if not clean_q or not title.strip():
            return

        norm_q = normalize_text(clean_q)
        norm_t = normalize_text(title)

        data = self.store.load() or {"history": [], "refinements": {}}
        history: List[Dict[str, Any]] = data.get("history", [])

        # Remove previous identical entry if exists to avoid clutter
        history = [
            h for h in history
            if not (normalize_text(h.get("query", "")) == norm_q and normalize_text(h.get("title", "")) == norm_t)
        ]

        entry = {
            "query": clean_q,
            "title": title.strip(),
            "artist": artist.strip() if artist else None,
            "category": category,
            "platform": platform,
            "url": url,
            "thumbnail": thumbnail,
            "duration": duration,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        history.insert(0, entry)
        if len(history) > MAX_SUGGESTION_HISTORY:
            history = history[:MAX_SUGGESTION_HISTORY]

        data["history"] = history
        self.store.save(data)

    def record_refinement(self, original_query: str, refined_query: str) -> None:
        """Record a user query refinement (e.g. 'shelter' -> 'shelter porter robinson')."""
        norm_orig = normalize_text(original_query)
        norm_ref = normalize_text(refined_query)
        if not norm_orig or not norm_ref or norm_orig == norm_ref:
            return

        data = self.store.load() or {"history": [], "refinements": {}}
        refinements: Dict[str, List[str]] = data.get("refinements", {})

        current = refinements.get(norm_orig, [])
        if refined_query not in current:
            current.insert(0, refined_query)
            refinements[norm_orig] = current[:5]

        # Bound total refinement keys
        if len(refinements) > MAX_SUGGESTION_HISTORY:
            oldest_key = next(iter(refinements))
            del refinements[oldest_key]

        data["refinements"] = refinements
        self.store.save(data)

    def get_matching_history(self, norm_q: str, limit: int = 4) -> List[Dict[str, Any]]:
        """Retrieve previous suggestions matching the user's current query."""
        if not norm_q:
            return []

        data = self.store.load() or {"history": [], "refinements": {}}
        history: List[Dict[str, Any]] = data.get("history", [])
        matches = []
        seen = set()

        for item in history:
            h_q = normalize_text(item.get("query", ""))
            h_title = normalize_text(item.get("title", ""))
            h_artist = normalize_text(item.get("artist", "") or "")

            if norm_q in h_q or norm_q in h_title or (h_artist and norm_q in h_artist):
                key = f"{h_title}::{h_artist}"
                if key not in seen:
                    seen.add(key)
                    matches.append(item)
                    if len(matches) >= limit:
                        break

        return matches

    def get_matching_refinements(self, norm_q: str, limit: int = 3) -> List[str]:
        """Retrieve refined search phrases previously used for similar queries."""
        if not norm_q:
            return []

        data = self.store.load() or {"history": [], "refinements": {}}
        refinements: Dict[str, List[str]] = data.get("refinements", {})
        results = []

        if norm_q in refinements:
            results.extend(refinements[norm_q])

        for k, v in refinements.items():
            if k != norm_q and (k.startswith(norm_q) or norm_q.startswith(k)):
                for r in v:
                    if r not in results:
                        results.append(r)

        return results[:limit]

    def clear_history(self) -> Dict[str, Any]:
        """Clear all local suggestion history and query refinements."""
        self.store.save({"history": [], "refinements": {}})
        return {"status": "cleared", "history_count": 0, "refinements_count": 0}

    def get_stats(self) -> Dict[str, Any]:
        """Get summary of local adaptive suggestion storage."""
        data = self.store.load() or {"history": [], "refinements": {}}
        history = data.get("history", [])
        refinements = data.get("refinements", {})
        return {
            "history_count": len(history),
            "refinements_count": len(refinements),
            "max_capacity": MAX_SUGGESTION_HISTORY,
        }


_shared_adaptive_store: Optional[AdaptiveSuggestionStore] = None


def get_shared_adaptive_store() -> AdaptiveSuggestionStore:
    global _shared_adaptive_store
    if _shared_adaptive_store is None:
        _shared_adaptive_store = AdaptiveSuggestionStore()
    return _shared_adaptive_store
