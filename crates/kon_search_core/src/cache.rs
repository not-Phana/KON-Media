//! Thread-safe, high-concurrency LRU/TTL Cache in native Rust.
//!
//! Provides sub-microsecond cache lookups, bounded memory eviction,
//! time-to-live expiration, and lock-protected statistical tracking.

use std::collections::HashMap;
use std::sync::{OnceLock, RwLock};
use std::time::{Duration, Instant};

#[derive(Debug, Clone)]
struct CacheEntry<V> {
    value: V,
    inserted_at: Instant,
    last_accessed: Instant,
    ttl: Duration,
}

#[derive(Debug, Clone, Default)]
pub struct CacheMetrics {
    pub hits: u64,
    pub misses: u64,
    pub evictions: u64,
}

pub struct FastLruCache<K, V> {
    entries: RwLock<HashMap<K, CacheEntry<V>>>,
    max_capacity: usize,
    default_ttl: Duration,
    metrics: RwLock<CacheMetrics>,
}

impl<K: std::hash::Hash + Eq + Clone, V: Clone> FastLruCache<K, V> {
    pub fn new(max_capacity: usize, default_ttl_secs: u64) -> Self {
        Self {
            entries: RwLock::new(HashMap::with_capacity(max_capacity)),
            max_capacity,
            default_ttl: Duration::from_secs(default_ttl_secs),
            metrics: RwLock::new(CacheMetrics::default()),
        }
    }

    pub fn get(&self, key: &K) -> Option<V> {
        let mut map = match self.entries.write() {
            Ok(guard) => guard,
            Err(_) => return None,
        };

        let now = Instant::now();
        if let Some(entry) = map.get_mut(key) {
            if now.duration_since(entry.inserted_at) <= entry.ttl {
                entry.last_accessed = now;
                if let Ok(mut met) = self.metrics.write() {
                    met.hits += 1;
                }
                return Some(entry.value.clone());
            }
        }

        // Key either missing or expired
        if map.contains_key(key) {
            map.remove(key);
        }
        if let Ok(mut met) = self.metrics.write() {
            met.misses += 1;
        }
        None
    }

    pub fn insert(&self, key: K, value: V, custom_ttl: Option<Duration>) {
        let mut map = match self.entries.write() {
            Ok(guard) => guard,
            Err(_) => return,
        };

        let now = Instant::now();
        let ttl = custom_ttl.unwrap_or(self.default_ttl);

        // Evict LRU if capacity reached
        if map.len() >= self.max_capacity && !map.contains_key(&key) {
            // Find least recently accessed entry
            let oldest_key = map
                .iter()
                .min_by_key(|(_, v)| v.last_accessed)
                .map(|(k, _)| k.clone());

            if let Some(k) = oldest_key {
                map.remove(&k);
                if let Ok(mut met) = self.metrics.write() {
                    met.evictions += 1;
                }
            }
        }

        map.insert(
            key,
            CacheEntry {
                value,
                inserted_at: now,
                last_accessed: now,
                ttl,
            },
        );
    }

    pub fn clear(&self) {
        if let Ok(mut map) = self.entries.write() {
            map.clear();
        }
    }

    pub fn prune_expired(&self) -> usize {
        let mut map = match self.entries.write() {
            Ok(guard) => guard,
            Err(_) => return 0,
        };

        let now = Instant::now();
        let initial = map.len();
        map.retain(|_, v| now.duration_since(v.inserted_at) <= v.ttl);
        initial - map.len()
    }

    pub fn size(&self) -> usize {
        self.entries.read().map(|m| m.len()).unwrap_or(0)
    }

    pub fn stats(&self) -> (u64, u64, u64) {
        if let Ok(m) = self.metrics.read() {
            (m.hits, m.misses, m.evictions)
        } else {
            (0, 0, 0)
        }
    }
}

// Global static query and suggestion cache
static GLOBAL_SEARCH_CACHE: OnceLock<FastLruCache<String, String>> = OnceLock::new();

pub fn get_global_cache() -> &'static FastLruCache<String, String> {
    GLOBAL_SEARCH_CACHE.get_or_init(|| FastLruCache::new(1000, 300))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_cache_insert_and_get() {
        let cache = FastLruCache::new(5, 60);
        cache.insert("key1".to_string(), "val1".to_string(), None);
        assert_eq!(cache.get(&"key1".to_string()), Some("val1".to_string()));
        assert_eq!(cache.get(&"missing".to_string()), None);
        let (hits, misses, _) = cache.stats();
        assert_eq!(hits, 1);
        assert_eq!(misses, 1);
    }

    #[test]
    fn test_cache_eviction() {
        let cache = FastLruCache::new(2, 60);
        cache.insert("a".to_string(), "1".to_string(), None);
        cache.insert("b".to_string(), "2".to_string(), None);
        cache.insert("c".to_string(), "3".to_string(), None);
        assert_eq!(cache.size(), 2);
    }
}
