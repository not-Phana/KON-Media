import React, { useState, useEffect, useCallback, useRef } from "react";
import Header from "./components/Header";
import { X } from "lucide-react";
import UrlInputBar from "./components/UrlInputBar";
import SearchResultsCard from "./components/SearchResultsCard";
import MediaPreviewCard from "./components/MediaPreviewCard";
import ActiveTasksMonitor from "./components/ActiveTasksMonitor";
import HistoryWorkspace from "./components/HistoryWorkspace";
import SettingsModal from "./components/SettingsModal";
import ModelInfoModal from "./components/ModelInfoModal";
import {
  fetchHealth,
  analyzeMediaUrl,
  searchMedia,
  submitSearchFeedback,
  queueDownload,
  cancelTask,
  dismissTask,
  retryTask,
  clearFinishedTasks,
  fetchActiveTasks,
  fetchHistory,
  clearHistory,
  deleteHistoryItem,
  fetchSettings,
  saveSettings,
  openFileInExplorer,
  subscribeToEvents,
} from "./api";

export default function App() {
  const [health, setHealth] = useState(null);
  const [settings, setSettings] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);

  const [analyzedMedia, setAnalyzedMedia] = useState(null);
  const [searchResults, setSearchResults] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  const [activeTasks, setActiveTasks] = useState([]);
  const [history, setHistory] = useState([]);
  const [toast, setToast] = useState(null);

  // Load initial health, settings, tasks, and history
  const loadInitialData = useCallback(async () => {
    try {
      const [h, s, t, hist] = await Promise.all([
        fetchHealth().catch(() => null),
        fetchSettings().catch(() => null),
        fetchActiveTasks().catch(() => []),
        fetchHistory().catch(() => []),
      ]);
      if (h) setHealth(h);
      if (s) setSettings(s);
      if (t) setActiveTasks(t);
      if (hist) setHistory(hist);
    } catch (_) {}
  }, []);

  const pendingUpdatesRef = useRef(new Map());
  const rafIdRef = useRef(null);

  const flushUpdates = useCallback(() => {
    if (pendingUpdatesRef.current.size === 0) return;
    const updates = new Map(pendingUpdatesRef.current);
    pendingUpdatesRef.current.clear();
    setActiveTasks((prev) =>
      prev.map((t) => {
        const update = updates.get(t.id);
        return update ? { ...t, ...update } : t;
      })
    );
  }, []);

  useEffect(() => {
    loadInitialData();

    // Subscribe to real-time Server-Sent Events (SSE)
    const unsubscribe = subscribeToEvents((event) => {
      if (event.type === "task_created") {
        flushUpdates();
        setActiveTasks((prev) => {
          const exists = prev.some((t) => t.id === event.data.id);
          return exists ? prev : [event.data, ...prev];
        });
      } else if (event.type === "task_updated") {
        // High frequency progress updates are throttled via requestAnimationFrame
        pendingUpdatesRef.current.set(event.data.id, event.data);
        if (!rafIdRef.current) {
          rafIdRef.current = requestAnimationFrame(() => {
            rafIdRef.current = null;
            flushUpdates();
          });
        }
      } else if (event.type === "task_completed") {
        pendingUpdatesRef.current.delete(event.data.id);
        setActiveTasks((prev) =>
          prev.map((t) => (t.id === event.data.id ? event.data : t))
        );
        // Refresh persistent history
        fetchHistory().then(setHistory).catch(() => {});
      } else if (event.type === "task_dismissed") {
        pendingUpdatesRef.current.delete(event.data.id);
        setActiveTasks((prev) => prev.filter((t) => t.id !== event.data.id));
      }
    });

    return () => {
      unsubscribe();
      if (rafIdRef.current) {
        cancelAnimationFrame(rafIdRef.current);
      }
    };
  }, [loadInitialData, flushUpdates]);

  // Handle URL analysis or keyword discovery
  const handleAnalyze = async (input, searchMode = "audio") => {
    setIsAnalyzing(true);
    setAnalyzeError(null);

    const isUrl = input.startsWith("http://") || input.startsWith("https://");

    if (isUrl) {
      setSearchResults(null);
      setAnalyzedMedia(null);
      try {
        const info = await analyzeMediaUrl(input);
        setAnalyzedMedia(info);
      } catch (err) {
        setAnalyzeError(err.message || "Failed to analyze URL");
      } finally {
        setIsAnalyzing(false);
      }
    } else {
      // Execute multi-signal search
      setAnalyzedMedia(null);
      setSearchQuery(input);
      try {
        const res = await searchMedia(input, { limit: 6, mediaType: searchMode });
        setSearchResults(res.results || []);
      } catch (err) {
        setAnalyzeError(err.message || "Failed to search media");
      } finally {
        setIsAnalyzing(false);
      }
    }
  };

  // Handle direct 1-click download from search result
  const handleDirectDownload = async (candidate, mediaType) => {
    const isAudio = mediaType === "audio";
    try {
      submitSearchFeedback({
        query: searchQuery,
        selected_id: candidate.id,
        selected_title: candidate.title,
        selected_url: candidate.url,
        is_mismatch: false,
        provider: candidate.platform,
      }).catch(() => {});

      await queueDownload({
        url: candidate.url,
        title: candidate.title,
        media_type: mediaType,
        format_id: isAudio ? "bestaudio/best" : "bestvideo+bestaudio/best",
        ext: isAudio ? "mp3" : "mp4",
        audio_bitrate: "320k",
        thumbnail: candidate.thumbnail,
        duration: candidate.duration,
      });

      setToast({
        message: `Queued ${isAudio ? "Song (MP3)" : "Video (MP4)"}: ${candidate.title}`,
        type: "success",
      });
      setTimeout(() => setToast(null), 4000);
    } catch (err) {
      setToast({
        message: `Could not queue download: ${err.message}`,
        type: "error",
      });
      setTimeout(() => setToast(null), 4000);
    }
  };

  // Handle selecting a search discovery for custom format inspection
  const handleSelectSearchResult = async (candidate) => {
    setSearchResults(null);
    submitSearchFeedback({
      query: searchQuery,
      selected_id: candidate.id,
      selected_title: candidate.title,
      selected_url: candidate.url,
      is_mismatch: false,
      provider: candidate.platform,
    }).catch(() => {});
    await handleAnalyze(candidate.url);
  };

  // Handle download submission
  const handleStartDownload = async (downloadOpts) => {
    try {
      await queueDownload(downloadOpts);
      // Dismiss preview once queued
      setAnalyzedMedia(null);
    } catch (err) {
      setAnalyzeError(err.message || "Could not queue download");
    }
  };

  // Handle task cancellation
  const handleCancelTask = async (taskId) => {
    try {
      await cancelTask(taskId);
    } catch (err) {
      console.error("Cancel failed:", err);
    }
  };

  // Handle task dismiss from active view
  const handleDismissTask = async (taskId) => {
    try {
      await dismissTask(taskId);
      setActiveTasks((prev) => prev.filter((t) => t.id !== taskId));
    } catch (_) {
      setActiveTasks((prev) => prev.filter((t) => t.id !== taskId));
    }
  };

  // Handle task retry
  const handleRetryTask = async (taskId) => {
    try {
      await retryTask(taskId);
      setActiveTasks((prev) =>
        prev.map((t) =>
          t.id === taskId
            ? {
                ...t,
                status: "queued",
                substate: null,
                substate_message: null,
                percentage: 0,
                speed: 0,
                eta: null,
                downloaded_bytes: 0,
                total_bytes: 0,
                error: null,
                file_path: null,
                filename: null,
              }
            : t
        )
      );
      setToast({ message: "Task re-queued for download", type: "info" });
      setTimeout(() => setToast(null), 3000);
    } catch (err) {
      setToast({ message: `Retry failed: ${err.message}`, type: "error" });
      setTimeout(() => setToast(null), 4000);
    }
  };

  // Handle clearing finished tasks in bulk
  const handleClearFinished = async () => {
    try {
      await clearFinishedTasks();
      setActiveTasks((prev) =>
        prev.filter((t) =>
          ["queued", "downloading", "processing", "verifying"].includes(t.status)
        )
      );
    } catch (err) {
      console.error("Clear finished tasks failed:", err);
      setActiveTasks((prev) =>
        prev.filter((t) =>
          ["queued", "downloading", "processing", "verifying"].includes(t.status)
        )
      );
    }
  };

  // Handle folder opening in Windows File Explorer
  const handleOpenFile = async (filePath) => {
    try {
      const res = await openFileInExplorer(filePath);
      const targetPath = res.path || filePath || "Downloads folder";
      try {
        await navigator.clipboard.writeText(targetPath);
        setToast({
          message: `Opening folder. Path copied to clipboard: ${targetPath}`,
          type: "success",
        });
      } catch (_) {
        setToast({ message: `Opening: ${targetPath}`, type: "info" });
      }
      setTimeout(() => setToast(null), 5000);
    } catch (err) {
      setToast({
        message: `Could not open folder: ${err.message}`,
        type: "error",
      });
      setTimeout(() => setToast(null), 5000);
    }
  };

  // Handle history operations
  const handleClearHistory = async () => {
    try {
      await clearHistory();
      setHistory([]);
    } catch (err) {
      console.error("Clear history failed:", err);
    }
  };

  const handleDeleteHistoryItem = async (taskId) => {
    try {
      await deleteHistoryItem(taskId);
      setHistory((prev) => prev.filter((item) => item.id !== taskId));
    } catch (err) {
      console.error("Delete history item failed:", err);
    }
  };

  // Handle settings update
  const handleSaveSettings = async (newSettings) => {
    try {
      const updated = await saveSettings(newSettings);
      setSettings(updated);
      const h = await fetchHealth().catch(() => null);
      if (h) setHealth(h);
    } catch (err) {
      console.error("Save settings failed:", err);
    }
  };

  return (
    <div className="min-h-screen bg-[#E9EEF5] text-[#1E293B] flex flex-col justify-between">
      <div className="max-w-5xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Global Application Header */}
        <Header
          health={health}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onOpenFile={handleOpenFile}
          onOpenModelModal={() => setIsModelModalOpen(true)}
        />

        {/* URL Input & Ingress Bar */}
        <UrlInputBar
          onAnalyze={handleAnalyze}
          isLoading={isAnalyzing}
          error={analyzeError}
          onClearError={() => setAnalyzeError(null)}
          onOpenModelModal={() => setIsModelModalOpen(true)}
        />

        {/* Ranked Search Discoveries */}
        {searchResults && (
          <SearchResultsCard
            query={searchQuery}
            results={searchResults}
            onSelectCandidate={handleSelectSearchResult}
            onDirectDownload={handleDirectDownload}
            onDismiss={() => setSearchResults(null)}
            onFeedback={(fb) => submitSearchFeedback(fb).catch(() => {})}
              onOpenModelModal={() => setIsModelModalOpen(true)}
          />
        )}

        {/* Media Preview & Format Selector */}
        {analyzedMedia && (
          <MediaPreviewCard
            mediaInfo={analyzedMedia}
            onStartDownload={handleStartDownload}
            onDismiss={() => setAnalyzedMedia(null)}
            onUpdateMediaInfo={setAnalyzedMedia}
          />
        )}

        {/* Active Task Queue Monitor */}
        <ActiveTasksMonitor
          tasks={activeTasks}
          onCancelTask={handleCancelTask}
          onOpenFile={handleOpenFile}
          onDismissTask={handleDismissTask}
          onRetryTask={handleRetryTask}
          onClearFinished={handleClearFinished}
        />

        {/* Local Download History */}
        <HistoryWorkspace
          history={history}
          onOpenFile={handleOpenFile}
          onDeleteItem={handleDeleteHistoryItem}
          onClearAll={handleClearHistory}
        />
      </div>

      {/* Footer */}
      <footer className="border-t border-slate-200/60 py-6 text-center text-xs text-[#64748B] font-medium">
        <p className="m-0">
          KON Media · Tactile Neumorphic Desktop Toolkit · Local-First Architecture · Windows 11
        </p>
      </footer>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        currentSettings={settings}
        onSaveSettings={handleSaveSettings}
        onOpenFile={handleOpenFile}
      />

      {/* KON Search 1 Rei Model Spotlight Modal */}
      <ModelInfoModal
        isOpen={isModelModalOpen}
        onClose={() => setIsModelModalOpen(false)}
      />

      {/* Interactive Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md p-4 rounded-2xl neu-card shadow-2xl flex items-center justify-between gap-3 animate-fade-in text-[#1E293B]">
          <span className="text-xs text-[#1E293B] font-medium leading-relaxed">
            {toast.message}
          </span>
          <button
            onClick={() => setToast(null)}
            className="neu-raised p-1 text-[#64748B] hover:text-[#1E293B] cursor-pointer shrink-0 rounded-lg"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}
    </div>
  );
}
