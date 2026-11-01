/**
 * Local-First Storage Utility for KON Search 1.2.
 * Manages Favorites, Recently Played, and Search History in local storage with zero account requirement.
 */

const FAVORITES_KEY = "kon_favorite_songs";
const RECENTLY_PLAYED_KEY = "kon_recently_played_songs";
const SEARCH_HISTORY_KEY = "kon_recent_search_queries";

/**
 * 1. FAVORITES MANAGEMENT
 */
export function getFavorites() {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.warn("Failed to load favorites:", e);
    return [];
  }
}

export function saveFavorites(favorites) {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
    window.dispatchEvent(new CustomEvent("kon_favorites_changed", { detail: favorites }));
  } catch (e) {
    console.warn("Failed to save favorites:", e);
  }
}

export function toggleFavorite(track) {
  if (!track || (!track.id && !track.url)) return false;
  const list = getFavorites();
  const trackId = track.id || track.url;
  const existingIdx = list.findIndex((item) => (item.id || item.url) === trackId);

  let updated;
  let isNowFavorite = false;

  if (existingIdx >= 0) {
    updated = list.filter((_, i) => i !== existingIdx);
    isNowFavorite = false;
  } else {
    const cleanItem = {
      id: track.id || track.url,
      title: track.clean_title || track.title || "Unknown Song",
      artist: track.artist || track.uploader || "",
      thumbnail: track.thumbnail || null,
      duration: track.duration || null,
      url: track.url || "",
      platform: track.platform || "media",
      content_type: track.content_type || "song",
      added_at: new Date().toISOString(),
    };
    updated = [cleanItem, ...list];
    isNowFavorite = true;
  }

  saveFavorites(updated);
  return isNowFavorite;
}

export function isTrackFavorite(track, favoritesList = null) {
  if (!track) return false;
  const list = favoritesList || getFavorites();
  const trackId = track.id || track.url;
  return list.some((item) => (item.id || item.url) === trackId);
}

/**
 * 2. RECENTLY PLAYED MANAGEMENT
 */
export function getRecentlyPlayed() {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(RECENTLY_PLAYED_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch (e) {
    console.warn("Failed to load recently played:", e);
    return [];
  }
}

export function addRecentlyPlayed(track) {
  if (!track || (!track.id && !track.url)) return;
  const list = getRecentlyPlayed();
  const trackId = track.id || track.url;

  // Filter out existing occurrence to move it to the top
  const filtered = list.filter((item) => (item.id || item.url) !== trackId);
  const entry = {
    id: track.id || track.url,
    title: track.clean_title || track.title || "Unknown Song",
    artist: track.artist || track.uploader || "",
    thumbnail: track.thumbnail || null,
    duration: track.duration || null,
    url: track.url || "",
    platform: track.platform || "media",
    stream_url: track.stream_url || track.direct_url || null,
    is_local: track.is_local || false,
    played_at: new Date().toISOString(),
  };

  const updated = [entry, ...filtered].slice(0, 40);
  try {
    localStorage.setItem(RECENTLY_PLAYED_KEY, JSON.stringify(updated));
    window.dispatchEvent(new CustomEvent("kon_recently_played_changed", { detail: updated }));
  } catch (e) {
    console.warn("Failed to save recently played:", e);
  }
}

export function clearRecentlyPlayed() {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(RECENTLY_PLAYED_KEY);
    window.dispatchEvent(new CustomEvent("kon_recently_played_changed", { detail: [] }));
  } catch (e) {
    console.warn("Failed to clear recently played:", e);
  }
}

/**
 * Helper to test if a query string contains awkward or legacy test terms
 */
function isAwkwardQuery(str) {
  if (!str) return false;
  const lower = str.toLowerCase();
  return (
    lower.includes("basement") ||
    lower.includes("elevenz") ||
    lower.includes("ex-girlfriend")
  );
}

// Proactively purge awkward legacy test queries from localStorage on load
if (typeof window !== "undefined") {
  try {
    const rawHist = localStorage.getItem(SEARCH_HISTORY_KEY);
    if (rawHist) {
      const parsed = JSON.parse(rawHist);
      if (Array.isArray(parsed)) {
        const cleanHist = parsed.filter(
          (item) => item && item.query && !isAwkwardQuery(item.query)
        );
        if (cleanHist.length !== parsed.length) {
          localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(cleanHist));
        }
      }
    }

    const savedQuery = localStorage.getItem("kon_search_query") || "";
    if (isAwkwardQuery(savedQuery)) {
      localStorage.removeItem("kon_search_query");
    }

    const rawResults = localStorage.getItem("kon_search_results");
    if (rawResults && isAwkwardQuery(rawResults)) {
      localStorage.removeItem("kon_search_results");
      localStorage.removeItem("kon_search_meta");
      localStorage.removeItem("kon_search_state");
    }
  } catch (_) {}
}

/**
 * 3. SEARCH QUERY HISTORY
 */
export function getSearchQueryHistory() {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(SEARCH_HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    // Sanitize and filter out test or awkward queries
    const sanitized = parsed.filter(
      (item) => item && item.query && !isAwkwardQuery(item.query)
    );
    if (sanitized.length !== parsed.length) {
      localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(sanitized));
    }
    return sanitized;
  } catch (e) {
    console.warn("Failed to load search query history:", e);
    return [];
  }
}

export function addSearchQueryHistory(query, engineMode = "rei") {
  const clean = (query || "").trim();
  if (!clean || clean.startsWith("http://") || clean.startsWith("https://")) return;
  if (isAwkwardQuery(clean)) return;

  const list = getSearchQueryHistory();
  const filtered = list.filter((item) => item.query.toLowerCase() !== clean.toLowerCase());
  const entry = {
    query: clean,
    engine_mode: engineMode,
    timestamp: new Date().toISOString(),
  };

  const updated = [entry, ...filtered].slice(0, 15);
  try {
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(updated));
    window.dispatchEvent(new CustomEvent("kon_search_history_changed", { detail: updated }));
  } catch (e) {
    console.warn("Failed to save search history:", e);
  }
}

export function removeSearchQueryHistory(query) {
  if (typeof window === "undefined") return [];
  const clean = (query || "").trim().toLowerCase();
  const list = getSearchQueryHistory();
  const updated = list.filter((item) => item.query.toLowerCase() !== clean);
  try {
    localStorage.setItem(SEARCH_HISTORY_KEY, JSON.stringify(updated));
    window.dispatchEvent(new CustomEvent("kon_search_history_changed", { detail: updated }));
  } catch (e) {
    console.warn("Failed to remove search history item:", e);
  }
  return updated;
}

export function clearSearchQueryHistory() {
  if (typeof window === "undefined") return;
  try {
    localStorage.removeItem(SEARCH_HISTORY_KEY);
    window.dispatchEvent(new CustomEvent("kon_search_history_changed", { detail: [] }));
  } catch (e) {
    console.warn("Failed to clear search history:", e);
  }
}
