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
import BottomMusicPlayer from "./components/BottomMusicPlayer";
import {
  fetchHealth,
  analyzeMediaUrl,
  searchMedia,
  streamSearchMedia,
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
  resolveAudioStream,
} from "./api";

export default function App() {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("kon_theme") || "dark";
    } catch (_) {
      return "dark";
    }
  });

  const [health, setHealth] = useState(null);
  const [settings, setSettings] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);

  const [analyzedMedia, setAnalyzedMedia] = useState(null);
  const [searchResults, setSearchResults] = useState(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [currentSearchMode, setCurrentSearchMode] = useState("audio");
  const [searchState, setSearchState] = useState("idle"); // 'idle' | 'searching' | 'updating' | 'complete' | 'no_results' | 'partial' | 'error'
  const [searchStage, setSearchStage] = useState(null);
  const [searchMeta, setSearchMeta] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analyzeError, setAnalyzeError] = useState(null);

  const searchAbortRef = useRef(null);
  const searchIdRef = useRef(0);

  const [engineMode, setEngineMode] = useState(() => {
    try {
      return localStorage.getItem("kon_search_engine_mode") || "rei";
    } catch {
      return "rei";
    }
  });

  const handleEngineModeChange = (mode) => {
    setEngineMode(mode);
    try {
      localStorage.setItem("kon_search_engine_mode", mode);
    } catch (_) {}
  };

  const [activeTasks, setActiveTasks] = useState([]);
  const [history, setHistory] = useState([]);
  const [toast, setToast] = useState(null);

  // Persistent Built-in Audio Player State
  const [currentTrack, setCurrentTrack] = useState(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [audioError, setAudioError] = useState(null);
  const [playbackQueue, setPlaybackQueue] = useState([]);
  const [queueIndex, setQueueIndex] = useState(-1);

  // Play candidate handler (preview before download)
  const handlePlayCandidate = async (cand) => {
    if (!cand) return;

    // If clicking currently active track, simply toggle play/pause
    if (
      currentTrack &&
      (currentTrack.id === cand.id || currentTrack.url === cand.url)
    ) {
      setIsPlaying((prev) => !prev);
      return;
    }

    // Set up queue from search results if available
    const queue = searchResults && searchResults.length > 0 ? searchResults : [cand];
    const idx = queue.findIndex((c) => c.id === cand.id || c.url === cand.url);
    setPlaybackQueue(queue);
    setQueueIndex(idx >= 0 ? idx : 0);

    const optimisticTrack = {
      id: cand.id,
      title: cand.clean_title || cand.title,
      artist: cand.uploader || cand.artist || "",
      thumbnail: cand.thumbnail,
      duration: cand.duration,
      url: cand.url,
      engine_mode: cand.engine_mode || engineMode,
      model: cand.model,
      content_type: cand.content_type,
      is_music: cand.is_music,
      is_local: false,
    };
    setCurrentTrack(optimisticTrack);
    setIsLoadingAudio(true);
    setAudioError(null);
    setIsPlaying(false);

    try {
      const resolved = await resolveAudioStream(cand.url, {
        title: cand.clean_title || cand.title,
        id: cand.id,
      });

      if (resolved.playable) {
        setCurrentTrack((prev) => ({
          ...prev,
          ...resolved,
          title: resolved.title || prev.title,
          artist: resolved.artist || prev.artist,
          thumbnail: resolved.thumbnail || prev.thumbnail,
          duration: resolved.duration || prev.duration,
          stream_url: resolved.stream_url,
          direct_url: resolved.direct_url,
          is_local: resolved.is_local,
          file_path: resolved.file_path,
        }));
        setIsPlaying(true);
      } else {
        const errMsg = resolved.reason || resolved.error || "Cannot play preview";
        setAudioError(errMsg);
        setToast({ message: errMsg });
      }
    } catch (err) {
      const errMsg = err.message || "Failed to load audio stream";
      setAudioError(errMsg);
      setToast({ message: errMsg });
    } finally {
      setIsLoadingAudio(false);
    }
  };

  const handleTogglePlay = () => {
    setIsPlaying((prev) => !prev);
  };

  const handleNextTrack = ({ shuffle = false, repeat = "none" } = {}) => {
    if (!playbackQueue.length) return;

    if (shuffle) {
      const randomIdx = Math.floor(Math.random() * playbackQueue.length);
      handlePlayCandidate(playbackQueue[randomIdx]);
      return;
    }

    const nextIdx = queueIndex + 1;
    if (nextIdx < playbackQueue.length) {
      handlePlayCandidate(playbackQueue[nextIdx]);
    } else if (repeat === "all") {
      handlePlayCandidate(playbackQueue[0]);
    }
  };

  const handlePreviousTrack = ({ shuffle = false } = {}) => {
    if (!playbackQueue.length) return;

    if (shuffle) {
      const randomIdx = Math.floor(Math.random() * playbackQueue.length);
      handlePlayCandidate(playbackQueue[randomIdx]);
      return;
    }

    const prevIdx = queueIndex - 1;
    if (prevIdx >= 0) {
      handlePlayCandidate(playbackQueue[prevIdx]);
    }
  };

  const handleClosePlayer = () => {
    setIsPlaying(false);
    setCurrentTrack(null);
  };

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

  // Synchronize color scheme and theme attribute across the DOM per Modern Web Guidance
  useEffect(() => {
    try {
      const isDark =
        theme === "dark" ||
        (theme === "system" &&
          window.matchMedia &&
          window.matchMedia("(prefers-color-scheme: dark)").matches);

      if (isDark) {
        document.documentElement.classList.add("dark");
        document.documentElement.setAttribute("data-theme", "dark");
      } else {
        document.documentElement.classList.remove("dark");
        document.documentElement.setAttribute("data-theme", "light");
      }

      const meta = document.querySelector('meta[name="color-scheme"]');
      if (meta) {
        meta.setAttribute("content", theme === "system" ? "light dark" : theme);
      }
      localStorage.setItem("kon_theme", theme);
    } catch (_) {}
  }, [theme]);

  // Listen to OS system theme changes if mode is set to 'system'
  useEffect(() => {
    if (theme !== "system") return;
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e) => {
      if (e.matches) {
        document.documentElement.classList.add("dark");
        document.documentElement.setAttribute("data-theme", "dark");
      } else {
        document.documentElement.classList.remove("dark");
        document.documentElement.setAttribute("data-theme", "light");
      }
    };
    mediaQuery.addEventListener("change", handler);
    return () => mediaQuery.removeEventListener("change", handler);
  }, [theme]);

  const handleToggleTheme = () => {
    setTheme((prev) => (prev === "dark" ? "light" : "dark"));
  };

  // Handle URL analysis or keyword discovery
  const handleAnalyze = async (input, searchMode = "audio", modeOverride = null) => {
    setIsAnalyzing(true);
    setAnalyzeError(null);
    const activeEngine = modeOverride || engineMode;

    const isUrl = input.startsWith("http://") || input.startsWith("https://");

    if (isUrl) {
      if (searchAbortRef.current) {
        searchAbortRef.current.abort();
      }
      setSearchState("idle");
      setSearchResults(null);
      setSearchMeta(null);
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
      // Abort any in-flight search to prevent stale race conditions
      if (searchAbortRef.current) {
        searchAbortRef.current.abort();
      }
      const controller = new AbortController();
      searchAbortRef.current = controller;
      const currentSearchId = ++searchIdRef.current;

      setAnalyzedMedia(null);
      setSearchQuery(input);
      setCurrentSearchMode(searchMode);
      setSearchResults(null);
      setSearchState("searching");
      setSearchStage({ stage: "understanding", message: "Understanding your search..." });
      setSearchMeta(null);

      try {
        await streamSearchMedia(input, {
          limit: activeEngine === "flash" ? 12 : 20,
          mediaType: searchMode,
          engineMode: activeEngine,
          signal: controller.signal,
          onStage: (stageData) => {
            if (searchIdRef.current !== currentSearchId) return;
            setSearchStage(stageData);
            if (stageData.stage === "updating") {
              setSearchState("updating");
            }
          },
          onResults: (results) => {
            if (searchIdRef.current !== currentSearchId) return;
            setSearchResults(results);
          },
          onComplete: (finalData) => {
            if (searchIdRef.current !== currentSearchId) return;
            const results = finalData.results || [];
            setSearchResults(results);
            setSearchMeta({
              status: finalData.status || "complete",
              completed: finalData.providers_completed || [],
              timedOut: finalData.providers_timed_out || [],
              failed: finalData.providers_failed || [],
              engine: finalData.engine || (activeEngine === "flash" ? "KON Search 1.2 Rei Flash" : "KON Search 1.2 Rei"),
              engine_mode: finalData.engine_mode || activeEngine,
              model: finalData.model || (activeEngine === "flash" ? "KON Search 1.2 Rei Flash" : "KON Search 1.2 Rei"),
            });

            if (results.length === 0) {
              setSearchState("no_results");
            } else if (finalData.status === "partial") {
              setSearchState("partial");
            } else {
              setSearchState("complete");
            }
          },
          onError: (err) => {
            if (err.name === "AbortError") return;
            if (searchIdRef.current !== currentSearchId) return;
            setSearchState("error");
            setAnalyzeError(err.message || "Failed to search media");
          },
        });
      } catch (err) {
        if (err.name === "AbortError") {
          return; // Superseded by a newer search
        }
        if (searchIdRef.current !== currentSearchId) return;
        setSearchState("error");
        setAnalyzeError(err.message || "Failed to search media");
      } finally {
        if (searchIdRef.current === currentSearchId) {
          setIsAnalyzing(false);
        }
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

      // Use clean song title for cluttered anime/game video titles; preserve authentic title for clean releases
      const effectiveTitle =
        isAudio && candidate.is_cluttered && candidate.clean_title
          ? candidate.clean_title
          : candidate.title;

      const res = await queueDownload({
        url: candidate.url,
        title: effectiveTitle,
        media_type: mediaType,
        format_id: isAudio ? "bestaudio/best" : "bestvideo+bestaudio/best",
        ext: isAudio ? "mp3" : "mp4",
        audio_bitrate: "320k",
        thumbnail: candidate.thumbnail,
        duration: candidate.duration,
      });

      setToast({
        message: `Queued ${isAudio ? "Song (MP3)" : "Video (MP4)"}: ${effectiveTitle}`,
        type: "success",
      });
      setTimeout(() => setToast(null), 4000);
      return res;
    } catch (err) {
      setToast({
        message: `Could not queue download: ${err.message}`,
        type: "error",
      });
      setTimeout(() => setToast(null), 4000);
      throw err;
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
    <div className="min-h-screen bg-[var(--bg-main)] text-[var(--text-primary)] transition-colors duration-250 flex flex-col justify-between">
      <div className={`max-w-5xl w-full mx-auto px-4 sm:px-6 py-6 space-y-6 ${currentTrack ? "pb-28" : ""}`}>
        {/* Global Application Header */}
        <Header
          health={health}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onOpenFile={handleOpenFile}
          onOpenModelModal={() => setIsModelModalOpen(true)}
          theme={theme}
          onToggleTheme={handleToggleTheme}
        />

        {/* URL Input & Ingress Bar */}
        <UrlInputBar
          onAnalyze={handleAnalyze}
          isLoading={isAnalyzing}
          error={analyzeError}
          onClearError={() => setAnalyzeError(null)}
          onOpenModelModal={() => setIsModelModalOpen(true)}
          engineMode={engineMode}
          onEngineModeChange={handleEngineModeChange}
        />

        {/* Ranked Search Discoveries */}
        {(searchResults || searchState === "searching" || searchState === "updating" || searchState === "no_results") && (
          <SearchResultsCard
            query={searchQuery}
            results={searchResults}
            searchMode={currentSearchMode}
            engineMode={engineMode}
            searchState={searchState}
            searchStage={searchStage}
            searchMeta={searchMeta}
            activeTasks={activeTasks}
            history={history}
            onOpenFile={handleOpenFile}
            onSelectCandidate={handleSelectSearchResult}
            onDirectDownload={handleDirectDownload}
            onDismiss={() => {
              setSearchResults(null);
              setSearchState("idle");
              setSearchMeta(null);
            }}
            onFeedback={(fb) => submitSearchFeedback(fb).catch(() => {})}
            onOpenModelModal={() => setIsModelModalOpen(true)}
            onPlayCandidate={handlePlayCandidate}
            currentPlayingTrack={currentTrack}
            isPlaying={isPlaying}
            isLoadingAudio={isLoadingAudio}
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
        theme={theme}
        onSelectTheme={setTheme}
      />

      {/* KON Search 1.2 Rei Model Spotlight Modal */}
      <ModelInfoModal
        isOpen={isModelModalOpen}
        onClose={() => setIsModelModalOpen(false)}
      />

      {/* Persistent Bottom Music Player (VLC-style controls) */}
      <BottomMusicPlayer
        currentTrack={currentTrack}
        isPlaying={isPlaying}
        isLoading={isLoadingAudio}
        error={audioError}
        playbackQueue={playbackQueue}
        queueIndex={queueIndex}
        onPlay={() => setIsPlaying(true)}
        onPause={() => setIsPlaying(false)}
        onTogglePlay={handleTogglePlay}
        onNext={handleNextTrack}
        onPrevious={handlePreviousTrack}
        onClose={handleClosePlayer}
        onDirectDownload={handleDirectDownload}
        onOpenFile={handleOpenFile}
        activeTasks={activeTasks}
        history={history}
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
