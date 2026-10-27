import React, { useState, useEffect, useCallback } from "react";
import Header from "./components/Header";
import UrlInputBar from "./components/UrlInputBar";
import MediaPreviewCard from "./components/MediaPreviewCard";
import ActiveTasksMonitor from "./components/ActiveTasksMonitor";
import HistoryWorkspace from "./components/HistoryWorkspace";
import SettingsModal from "./components/SettingsModal";
import {
  fetchHealth,
  analyzeMediaUrl,
  queueDownload,
  cancelTask,
  dismissTask,
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

  const [analyzedMedia, setAnalyzedMedia] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  const [activeTasks, setActiveTasks] = useState([]);
  const [history, setHistory] = useState([]);

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

  useEffect(() => {
    loadInitialData();

    // Subscribe to real-time Server-Sent Events (SSE)
    const unsubscribe = subscribeToEvents((event) => {
      if (event.type === "task_created") {
        setActiveTasks((prev) => {
          const exists = prev.some((t) => t.id === event.data.id);
          return exists ? prev : [event.data, ...prev];
        });
      } else if (event.type === "task_updated") {
        setActiveTasks((prev) =>
          prev.map((t) => (t.id === event.data.id ? event.data : t))
        );
      } else if (event.type === "task_completed") {
        // Update task status in active list
        setActiveTasks((prev) =>
          prev.map((t) => (t.id === event.data.id ? event.data : t))
        );
        // Refresh persistent history
        fetchHistory().then(setHistory).catch(() => {});
      } else if (event.type === "task_dismissed") {
        setActiveTasks((prev) => prev.filter((t) => t.id !== event.data.id));
      }
    });

    return () => {
      unsubscribe();
    };
  }, [loadInitialData]);

  // Handle URL analysis
  const handleAnalyze = async (url) => {
    setIsAnalyzing(true);
    setAnalyzeError(null);
    setAnalyzedMedia(null);
    try {
      const info = await analyzeMediaUrl(url);
      setAnalyzedMedia(info);
    } catch (err) {
      setAnalyzeError(err.message || "Failed to analyze URL");
    } finally {
      setIsAnalyzing(false);
    }
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

  // Handle folder opening in Windows File Explorer
  const handleOpenFile = async (filePath) => {
    try {
      await openFileInExplorer(filePath);
    } catch (err) {
      alert(`Could not open explorer: ${err.message}`);
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
    <div className="min-h-screen bg-[#17191D] text-[#F3F4F6] flex flex-col justify-between">
      <div className="max-w-5xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Global Application Header */}
        <Header health={health} onOpenSettings={() => setIsSettingsOpen(true)} />

        {/* URL Input & Ingress Bar */}
        <UrlInputBar
          onAnalyze={handleAnalyze}
          isLoading={isAnalyzing}
          error={analyzeError}
          onClearError={() => setAnalyzeError(null)}
        />

        {/* Media Preview & Format Selector */}
        {analyzedMedia && (
          <MediaPreviewCard
            mediaInfo={analyzedMedia}
            onStartDownload={handleStartDownload}
            onDismiss={() => setAnalyzedMedia(null)}
          />
        )}

        {/* Active Task Queue Monitor */}
        <ActiveTasksMonitor
          tasks={activeTasks}
          onCancelTask={handleCancelTask}
          onOpenFile={handleOpenFile}
          onDismissTask={handleDismissTask}
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
      <footer className="border-t border-[#2D323B] py-4 text-center text-xs text-[#6B7280]">
        <p className="m-0">
          KON Media · $0 Operating Cost · Private, Local-First Architecture · Windows 11
        </p>
      </footer>

      {/* Settings Modal */}
      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        currentSettings={settings}
        onSaveSettings={handleSaveSettings}
      />
    </div>
  );
}
