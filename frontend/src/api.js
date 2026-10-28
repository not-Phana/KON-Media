/**
 * API client for KON Media backend.
 */

const API_BASE = "/api";

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
