"""In-memory thread-safe LRU & TTL cache for ultra-fast media search queries."""

import time
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional


class SearchCache:
    """High-performance thread-safe LRU cache with TTL expiration."""

    def __init__(self, max_size: int = 500, default_ttl_seconds: float = 3600.0):
        self.max_size = max_size
        self.default_ttl = default_ttl_seconds
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    @staticmethod
    def make_key(query: str, media_type: str = "all", provider: Optional[str] = None, limit: int = 5) -> str:
        """Create deterministic canonical cache key."""
        clean_q = query.strip().lower()
        return f"{clean_q}::{media_type.lower()}::{provider or 'all'}::{limit}"

    def get(self, key: str) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached candidate results if not expired."""
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None

            entry = self._cache[key]
            now = time.time()
            if now > entry["expires_at"]:
                del self._cache[key]
                self.misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self.hits += 1
            return entry["data"]

    def set(self, key: str, data: List[Dict[str, Any]], ttl_seconds: Optional[float] = None) -> None:
        """Store results in cache with expiration."""
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        now = time.time()
        expires_at = now + ttl

        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            elif len(self._cache) >= self.max_size:
                # Evict oldest entry (FIFO in OrderedDict)
                self._cache.popitem(last=False)

            self._cache[key] = {
                "data": data,
                "expires_at": expires_at,
                "created_at": now,
            }

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0

    def get_stats(self) -> Dict[str, Any]:
        """Return cache health and hit rate statistics."""
        with self._lock:
            total_requests = self.hits + self.misses
            hit_ratio = round((self.hits / total_requests) * 100, 2) if total_requests > 0 else 0.0
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "hit_ratio_percent": hit_ratio,
            }


_shared_search_cache: Optional[SearchCache] = None


def get_shared_search_cache() -> SearchCache:
    global _shared_search_cache
    if _shared_search_cache is None:
        _shared_search_cache = SearchCache()
    return _shared_search_cache
