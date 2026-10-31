/**
 * API client for KON Media backend.
 */

export function getApiBase() {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("kon_backend_url");
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, "") + "/api";
    }
    if (window.__KON_BACKEND_URL__ && typeof window.__KON_BACKEND_URL__ === "string") {
      return window.__KON_BACKEND_URL__.trim().replace(/\/+$/, "") + "/api";
    }
  }
  return import.meta.env.VITE_API_BASE || "/api";
}

export const API_BASE = {
  valueOf() { return getApiBase(); },
  toString() { return getApiBase(); },
  [Symbol.toPrimitive]() { return getApiBase(); },
};

export function setCustomBackendUrl(url) {
  if (!url || !url.trim()) {
    localStorage.removeItem("kon_backend_url");
  } else {
    localStorage.setItem("kon_backend_url", url.trim().replace(/\/+$/, ""));
  }
}

export function getCustomBackendUrl() {
  return localStorage.getItem("kon_backend_url") || "";
}

export async function fetchHealth() {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error("Backend service unreachable");
  return res.json();
}

export async function analyzeMediaUrl(url) {
  const res = await fetch(`${API_BASE}/analyze`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Analysis failed");
  }
  return data;
}

export async function searchMedia(query, { limit = 5, provider = null, mediaType = "all", engineMode = "rei", signal = null } = {}) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  if (provider) params.append("provider", provider);
  if (mediaType && mediaType !== "all") params.append("media_type", mediaType);
  if (engineMode) params.append("engine_mode", engineMode);

  const res = await fetch(`${API_BASE}/search?${params.toString()}`, { signal });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Search failed");
  }
  return data;
}

export async function fetchSearchSuggestions(query, { limit = 6, mediaType = "all", engineMode = "rei", signal = null } = {}) {
  const cleanQ = query?.trim();
  if (!cleanQ) return { suggestions: [], count: 0 };
  const params = new URLSearchParams({ q: cleanQ, limit: String(limit) });
  if (mediaType && mediaType !== "all") params.append("media_type", mediaType);
  if (engineMode) params.append("engine_mode", engineMode);

  try {
    const res = await fetch(`${API_BASE}/search/suggestions?${params.toString()}`, { signal });
    if (!res.ok) return { suggestions: [], count: 0 };
    return await res.json();
  } catch (err) {
    if (err.name === "AbortError") throw err;
    return { suggestions: [], count: 0 };
  }
}

export async function clearSuggestionHistory() {
  const res = await fetch(`${API_BASE}/search/suggestions/history`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error("Failed to clear suggestion history");
  return res.json();
}

export async function fetchSuggestionHistoryStats() {
  try {
    const res = await fetch(`${API_BASE}/search/suggestions/history`);
    if (!res.ok) return { history_count: 0, refinements_count: 0, recent_history: [] };
    return await res.json();
  } catch {
    return { history_count: 0, refinements_count: 0, recent_history: [] };
  }
}

export async function streamSearchMedia(
  query,
  {
    limit = 20,
    provider = null,
    mediaType = "all",
    engineMode = "rei",
    signal = null,
    onStage = () => {},
    onResults = () => {},
    onComplete = () => {},
    onError = () => {},
  } = {}
) {
  const params = new URLSearchParams({ q: query, limit: String(limit) });
  if (provider) params.append("provider", provider);
  if (mediaType && mediaType !== "all") params.append("media_type", mediaType);
  if (engineMode) params.append("engine_mode", engineMode);

  let res;
  try {
    res = await fetch(`${API_BASE}/search/live?${params.toString()}`, { signal });
  } catch (err) {
    if (err.name === "AbortError") throw err;
    // Fallback to static endpoint on network/connection failure
    try {
      const staticData = await searchMedia(query, { limit, provider, mediaType, engineMode, signal });
      onResults(staticData.results || [], false);
      onComplete(staticData);
      return staticData;
    } catch (staticErr) {
      onError(staticErr);
      throw staticErr;
    }
  }

  if (!res.ok || !res.body) {
    try {
      const staticData = await searchMedia(query, { limit, provider, mediaType, engineMode, signal });
      onResults(staticData.results || [], false);
      onComplete(staticData);
      return staticData;
    } catch (staticErr) {
      onError(staticErr);
      throw staticErr;
    }
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";
  let lastFinalData = null;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() || "";

      for (const ev of events) {
        const trimmed = ev.trim();
        if (trimmed.startsWith("data: ")) {
          try {
            const data = JSON.parse(trimmed.slice(6));
            onStage(data);
            if (data.results && Array.isArray(data.results)) {
              onResults(data.results, data.is_partial || false);
            }
            if (
              data.stage === "completed" ||
              data.stage === "partial_results" ||
              data.stage === "no_results"
            ) {
              lastFinalData = data;
              onComplete(data);
            }
          } catch {
            // ignore non-json SSE frames
          }
        }
      }
    }
  } catch (err) {
    if (err.name === "AbortError") throw err;
    onError(err);
    throw err;
  } finally {
    try {
      reader.releaseLock();
    } catch {
      // ignore
    }
  }

  return lastFinalData;
}

export async function submitSearchFeedback(feedback) {
  const res = await fetch(`${API_BASE}/search/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(feedback),
  });
  return res.json();
}

export async function fetchModelStats() {
  const res = await fetch(`${API_BASE}/search/model-stats`);
  if (!res.ok) throw new Error("Failed to fetch model stats");
  return res.json();
}

export async function fetchContinuousTrainStatus() {
  const res = await fetch(`${API_BASE}/search/train/continuous/status`);
  if (!res.ok) throw new Error("Failed to fetch continuous training status");
  return res.json();
}

export async function startContinuousTrain() {
  const res = await fetch(`${API_BASE}/search/train/continuous/start`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to start continuous training");
  return res.json();
}

export async function stopContinuousTrain() {
  const res = await fetch(`${API_BASE}/search/train/continuous/stop`, {
    method: "POST",
  });
  if (!res.ok) throw new Error("Failed to stop continuous training");
  return res.json();
}

export async function triggerModelTraining(epochs = 5) {
  const res = await fetch(`${API_BASE}/search/train`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ epochs }),
  });
  if (!res.ok) throw new Error("Failed to trigger model training");
  return res.json();
}

export async function learnFromDocument({ content, isUrl = null, epochs = 5 }) {
  const res = await fetch(`${API_BASE}/search/learn-doc`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content, is_url: isUrl, epochs }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Failed to learn from document");
  }
  return data;
}

export async function fetchGdriveStatus() {
  const res = await fetch(`${API_BASE}/search/gdrive-status`);
  if (!res.ok) throw new Error("Failed to fetch Google Drive status");
  return res.json();
}

export async function queueDownload(options) {
  const res = await fetch(`${API_BASE}/download`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(options),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Download queueing failed");
  }
  return data;
}

export async function cancelTask(taskId) {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/cancel`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Cancellation failed");
  }
  return data;
}

export async function dismissTask(taskId) {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/dismiss`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Dismiss failed");
  }
  return data;
}

export async function retryTask(taskId) {
  const res = await fetch(`${API_BASE}/tasks/${taskId}/retry`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Retry failed");
  }
  return data;
}

export async function clearFinishedTasks() {
  const res = await fetch(`${API_BASE}/tasks/clear-finished`, {
    method: "POST",
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Clear finished tasks failed");
  }
  return data;
}

export async function fetchActiveTasks() {
  const res = await fetch(`${API_BASE}/tasks`);
  if (!res.ok) throw new Error("Failed to fetch active tasks");
  return res.json();
}

export async function fetchHistory() {
  const res = await fetch(`${API_BASE}/history`);
  if (!res.ok) throw new Error("Failed to fetch history");
  return res.json();
}

export async function clearHistory() {
  const res = await fetch(`${API_BASE}/history`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to clear history");
  return res.json();
}

export async function deleteHistoryItem(taskId) {
  const res = await fetch(`${API_BASE}/history/${taskId}`, { method: "DELETE" });
  if (!res.ok) throw new Error("Failed to delete history item");
  return res.json();
}

export async function fetchSettings() {
  const res = await fetch(`${API_BASE}/settings`);
  if (!res.ok) throw new Error("Failed to fetch settings");
  return res.json();
}

export async function saveSettings(settings) {
  const res = await fetch(`${API_BASE}/settings`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(settings),
  });
  return res.json();
}

export async function validateFFmpeg(ffmpegPath) {
  const res = await fetch(`${API_BASE}/settings/validate-ffmpeg`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ffmpeg_path: ffmpegPath }),
  });
  return res.json();
}

export async function openFileInExplorer(filePath) {
  const res = await fetch(`${API_BASE}/open-folder`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ file_path: filePath || "" }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Could not open Explorer");
  }
  return data;
}

export function getDownloadUrl(filename) {
  return `${API_BASE}/downloads/${encodeURIComponent(filename)}`;
}

export function getStreamUrl(filename) {
  return `${API_BASE}/stream/${encodeURIComponent(filename)}`;
}

export async function openExternalUrl(url) {
  const res = await fetch(`${API_BASE}/open-url`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Could not open external URL");
  }
  return data;
}

export async function matchSpotifyTrack(url, title) {
  const res = await fetch(`${API_BASE}/spotify/match`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, title }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Audio match failed");
  }
  return data;
}

export async function validateStreamPairing(videoStream, audioStream) {
  const res = await fetch(`${API_BASE}/validate-pairing`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      video_stream: videoStream,
      audio_stream: audioStream,
    }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Stream pairing validation failed");
  }
  return data;
}

export async function validateStreamPair(videoStream, audioStream) {
  const res = await fetch(`${API_BASE}/streams/validate-pair`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ video_stream: videoStream, audio_stream: audioStream }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || "Stream pair validation failed");
  }
  return data;
}

export function subscribeToEvents(onEvent, onError) {
  const es = new EventSource(`${API_BASE}/events`);

  es.addEventListener("connected", (e) => {
    try {
      const parsed = JSON.parse(e.data);
      if (onEvent) onEvent({ type: "connected", data: parsed });
    } catch (_) {}
  });

  es.addEventListener("task_created", (e) => {
    try {
      const parsed = JSON.parse(e.data);
      if (onEvent) onEvent({ type: "task_created", data: parsed });
    } catch (_) {}
  });

  es.addEventListener("task_updated", (e) => {
    try {
      const parsed = JSON.parse(e.data);
      if (onEvent) onEvent({ type: "task_updated", data: parsed });
    } catch (_) {}
  });

  es.addEventListener("task_completed", (e) => {
    try {
      const parsed = JSON.parse(e.data);
      if (onEvent) onEvent({ type: "task_completed", data: parsed });
    } catch (_) {}
  });

  es.addEventListener("task_dismissed", (e) => {
    try {
      const parsed = JSON.parse(e.data);
      if (onEvent) onEvent({ type: "task_dismissed", data: parsed });
    } catch (_) {}
  });

  es.onerror = (err) => {
    if (onError) onError(err);
  };

  return () => es.close();
}

export async function resolveAudioStream(url, { title, id, signal } = {}) {
  const params = new URLSearchParams({ url });
  if (title) params.append("title", title);
  if (id) params.append("id", id);

  const res = await fetch(`${API_BASE}/audio/resolve?${params.toString()}`, { signal });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail || data.error || "Failed to resolve audio preview");
  }
  return data;
}

export function getAudioStreamUrl(rawUrl) {
  if (!rawUrl) return "";
  if (rawUrl.startsWith("http://") || rawUrl.startsWith("https://")) {
    return rawUrl;
  }
  const base = getApiBase();
  if (rawUrl.startsWith("/api/")) {
    const root = base.replace(/\/api$/, "");
    return `${root}${rawUrl}`;
  }
  return `${base}${rawUrl.startsWith("/") ? "" : "/"}${rawUrl}`;
}

// Autonomous Continuous Learning Endpoints
export async function fetchLearningTelemetry() {
  const res = await fetch(`${API_BASE}/learning/telemetry`);
  if (!res.ok) throw new Error("Failed to fetch learning telemetry");
  return res.json();
}

export async function triggerAutonomousTraining() {
  const res = await fetch(`${API_BASE}/learning/train-now`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to trigger autonomous training");
  return res.json();
}

export async function pauseLearningScheduler() {
  const res = await fetch(`${API_BASE}/learning/scheduler/pause`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to pause learning scheduler");
  return res.json();
}

export async function resumeLearningScheduler() {
  const res = await fetch(`${API_BASE}/learning/scheduler/resume`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to resume learning scheduler");
  return res.json();
}

export async function rollbackLearningModel() {
  const res = await fetch(`${API_BASE}/learning/rollback`, { method: "POST" });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to roll back model");
  return data;
}

export async function toggleLearningCollector(enabled) {
  const res = await fetch(`${API_BASE}/learning/collector/toggle`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ enabled }),
  });
  if (!res.ok) throw new Error("Failed to toggle collector");
  return res.json();
}

export async function clearLearningData() {
  const res = await fetch(`${API_BASE}/learning/collector/clear`, { method: "POST" });
  if (!res.ok) throw new Error("Failed to clear learning data");
  return res.json();
}

export async function recordLearningInteraction(event) {
  try {
    await fetch(`${API_BASE}/learning/event`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(event),
    });
  } catch (_) {}
}



// Lyrics Retrieval API
export async function fetchLyrics({ title, artist = "", duration = null, filePath = null, signal = null } = {}) {
  const params = new URLSearchParams();
  if (title) params.append("title", title);
  if (artist) params.append("artist", artist);
  if (duration && duration > 0) params.append("duration", String(duration));
  if (filePath) params.append("file_path", filePath);

  try {
    const res = await fetch(`${API_BASE}/lyrics?${params.toString()}`, { signal });
    if (!res.ok) {
      return { found: false, synced: false, lines: [], plain_lyrics: null, error: "Lyrics unavailable" };
    }
    return await res.json();
  } catch (err) {
    if (err.name === "AbortError") throw err;
    return { found: false, synced: false, lines: [], plain_lyrics: null, error: err.message };
  }
}
