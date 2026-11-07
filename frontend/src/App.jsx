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
import LearningDashboardModal from "./components/LearningDashboardModal";
import BottomMusicPlayer from "./components/BottomMusicPlayer";
import NavigationTabBar from "./components/NavigationTabBar";
import PlaybackQueueDrawer from "./components/PlaybackQueueDrawer";
import LyricsModal from "./components/LyricsModal";
import VideoPlayerModal from "./components/VideoPlayerModal";
import LeftSidebar from "./components/LeftSidebar";
import RightSidebar from "./components/RightSidebar";
import LibraryWorkspace from "./components/LibraryWorkspace";
import {
  getFavorites,
  toggleFavorite,
  isTrackFavorite,
  getRecentlyPlayed,
  addRecentlyPlayed,
  clearRecentlyPlayed,
} from "./utils/playerStorage";
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
  recordLearningInteraction,
  fetchLyrics,
  getStreamUrl,
} from "./api";

export default function App() {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem("kon_theme") || "dark";
    } catch (_) {
      return "dark";
    }
  });

  const [glassMode, setGlassMode] = useState(() => {
    try {
      return localStorage.getItem("kon_glass_mode") === "true";
    } catch (_) {
      return false;
    }
  });

  const [customWallpaper, setCustomWallpaper] = useState(() => {
    try {
      return localStorage.getItem("kon_custom_wallpaper") || "";
    } catch (_) {
      return "";
    }
  });

  const [health, setHealth] = useState(null);
  const [settings, setSettings] = useState(null);
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isModelModalOpen, setIsModelModalOpen] = useState(false);
  const [isLearningDashboardOpen, setIsLearningDashboardOpen] = useState(false);

  const [analyzedMedia, setAnalyzedMedia] = useState(() => {
    try {
      const saved = localStorage.getItem("kon_analyzed_media");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [searchResults, setSearchResults] = useState(() => {
    try {
      const saved = localStorage.getItem("kon_search_results");
      if (saved && (saved.toLowerCase().includes("basement") || saved.toLowerCase().includes("elevenz"))) {
        localStorage.removeItem("kon_search_results");
        return null;
      }
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });

  const [searchQuery, setSearchQuery] = useState(() => {
    try {
      const q = localStorage.getItem("kon_search_query") || "";
      const lower = q.toLowerCase();
      if (lower.includes("basement") || lower.includes("elevenz") || lower.includes("ex-girlfriend")) {
        localStorage.removeItem("kon_search_query");
        return "";
      }
      return q;
    } catch {
      return "";
    }
  });

  const [currentSearchMode, setCurrentSearchMode] = useState(() => {
    try {
      return localStorage.getItem("kon_search_mode") || "all";
    } catch {
      return "all";
    }
  });

  const [searchState, setSearchState] = useState(() => {
    try {
      return localStorage.getItem("kon_search_state") || "idle";
    } catch {
      return "idle";
    }
  });

  const [searchStage, setSearchStage] = useState(null);
  const [searchMeta, setSearchMeta] = useState(() => {
    try {
      const saved = localStorage.getItem("kon_search_meta");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
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
  const [currentTrack, setCurrentTrack] = useState(() => {
    try {
      const saved = localStorage.getItem("kon_player_current_track");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [isPlaying, setIsPlaying] = useState(() => {
    try {
      return localStorage.getItem("kon_player_is_playing") === "true";
    } catch {
      return false;
    }
  });
  const [isLoadingAudio, setIsLoadingAudio] = useState(false);
  const [audioError, setAudioError] = useState(null);
  const [playbackQueue, setPlaybackQueue] = useState(() => {
    try {
      const saved = localStorage.getItem("kon_player_queue");
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [queueIndex, setQueueIndex] = useState(() => {
    try {
      const saved = localStorage.getItem("kon_player_queue_index");
      return saved !== null ? parseInt(saved, 10) : -1;
    } catch {
      return -1;
    }
  });
  const [isLyricsModalOpen, setIsLyricsModalOpen] = useState(() => {
    try {
      return localStorage.getItem("kon_lyrics_modal_open") === "true";
    } catch {
      return false;
    }
  });
  const [lyricsData, setLyricsData] = useState(null);
  const [isLoadingLyrics, setIsLoadingLyrics] = useState(false);
  const [lyricsError, setLyricsError] = useState(null);

  // Universal Video Player State
  const [currentVideo, setCurrentVideo] = useState(() => {
    try {
      const saved = localStorage.getItem("kon_current_video");
      return saved ? JSON.parse(saved) : null;
    } catch {
      return null;
    }
  });
  const [isVideoPlayerOpen, setIsVideoPlayerOpen] = useState(() => {
    try {
      return localStorage.getItem("kon_video_player_open") === "true";
    } catch {
      return false;
    }
  });
  const [videoPlayerMode, setVideoPlayerMode] = useState(() => {
    try {
      return localStorage.getItem("kon_video_player_mode") || "theater";
    } catch {
      return "theater";
    }
  });

  // Workspace Navigation & Drawer State
  const [activeView, setActiveView] = useState(() => {
    try {
      return localStorage.getItem("kon_active_view") || "search";
    } catch {
      return "search";
    }
  });
  const [isQueueOpen, setIsQueueOpen] = useState(() => {
    try {
      return localStorage.getItem("kon_queue_drawer_open") === "true";
    } catch {
      return false;
    }
  });
  const [favorites, setFavorites] = useState(() => getFavorites());
  const [recentlyPlayed, setRecentlyPlayed] = useState(() => getRecentlyPlayed());

  // Persist playback and navigation state across page reloads
  useEffect(() => {
    try {
      if (currentTrack) {
        localStorage.setItem("kon_player_current_track", JSON.stringify(currentTrack));
      } else {
        localStorage.removeItem("kon_player_current_track");
      }
    } catch (_) {}
  }, [currentTrack]);

  useEffect(() => {
    try {
      localStorage.setItem("kon_player_is_playing", String(isPlaying));
    } catch (_) {}
  }, [isPlaying]);

  useEffect(() => {
    try {
      if (playbackQueue && playbackQueue.length > 0) {
        localStorage.setItem("kon_player_queue", JSON.stringify(playbackQueue));
      } else {
        localStorage.removeItem("kon_player_queue");
      }
      localStorage.setItem("kon_player_queue_index", String(queueIndex));
    } catch (_) {}
  }, [playbackQueue, queueIndex]);

  useEffect(() => {
    try {
      localStorage.setItem("kon_lyrics_modal_open", String(isLyricsModalOpen));
    } catch (_) {}
  }, [isLyricsModalOpen]);

  useEffect(() => {
    try {
      if (currentVideo) {
        localStorage.setItem("kon_current_video", JSON.stringify(currentVideo));
      } else {
        localStorage.removeItem("kon_current_video");
      }
    } catch (_) {}
  }, [currentVideo]);

  useEffect(() => {
    try {
      localStorage.setItem("kon_video_player_open", String(isVideoPlayerOpen));
    } catch (_) {}
  }, [isVideoPlayerOpen]);

  useEffect(() => {
    try {
      localStorage.setItem("kon_video_player_mode", videoPlayerMode);
    } catch (_) {}
  }, [videoPlayerMode]);

  useEffect(() => {
    try {
      localStorage.setItem("kon_active_view", activeView);
    } catch (_) {}
  }, [activeView]);

  useEffect(() => {
    try {
      if (searchQuery) {
        localStorage.setItem("kon_search_query", searchQuery);
      } else {
        localStorage.removeItem("kon_search_query");
      }
    } catch (_) {}
  }, [searchQuery]);

  useEffect(() => {
    try {
      if (searchResults && searchResults.length > 0) {
        localStorage.setItem("kon_search_results", JSON.stringify(searchResults));
      } else if (searchResults === null) {
        localStorage.removeItem("kon_search_results");
      }
    } catch (_) {}
  }, [searchResults]);

  useEffect(() => {
    try {
      localStorage.setItem("kon_search_state", searchState);
    } catch (_) {}
  }, [searchState]);

  useEffect(() => {
    try {
      localStorage.setItem("kon_search_mode", currentSearchMode);
    } catch (_) {}
  }, [currentSearchMode]);

  useEffect(() => {
    try {
      if (searchMeta) {
        localStorage.setItem("kon_search_meta", JSON.stringify(searchMeta));
      } else {
        localStorage.removeItem("kon_search_meta");
      }
    } catch (_) {}
  }, [searchMeta]);

  useEffect(() => {
    try {
      if (analyzedMedia) {
        localStorage.setItem("kon_analyzed_media", JSON.stringify(analyzedMedia));
      } else {
        localStorage.removeItem("kon_analyzed_media");
      }
    } catch (_) {}
  }, [analyzedMedia]);

  useEffect(() => {
    try {
      localStorage.setItem("kon_queue_drawer_open", String(isQueueOpen));
    } catch (_) {}
  }, [isQueueOpen]);

  // Queue and Favorite Actions
  const handleAddToQueue = (cand) => {
    if (!cand) return;
    const item = {
      id: cand.id || cand.url,
      title: cand.clean_title || cand.title,
      artist: cand.uploader || cand.artist || "",
      thumbnail: cand.thumbnail,
      duration: cand.duration,
      url: cand.url,
      platform: cand.platform,
    };
    setPlaybackQueue((prev) => [...prev, item]);
    setToast({ message: `Added to queue: ${item.title}` });
    setTimeout(() => setToast(null), 3000);
  };

  const handleRemoveFromQueue = (index) => {
    setPlaybackQueue((prev) => prev.filter((_, i) => i !== index));
    if (index === queueIndex) {
      if (queueIndex < playbackQueue.length - 1) {
        handlePlayCandidate(playbackQueue[queueIndex + 1]);
      }
    } else if (index < queueIndex) {
      setQueueIndex((prev) => prev - 1);
    }
  };

  const handleClearQueue = () => {
    setPlaybackQueue([]);
    setQueueIndex(-1);
  };

  const handleToggleTrackFavorite = (track) => {
    if (!track) return;
    const isNowFav = toggleFavorite(track);
    if (isNowFav) {
      recordLearningInteraction({
        query: searchQuery,
        candidate_id: track.id || track.url,
        candidate_title: track.clean_title || track.title,
        event_type: "favorite",
        candidate_url: track.url,
        engine_mode: track.engine_mode || engineMode,
      });
    }
    setToast({
      message: isNowFav ? `Saved to Favorites: ${track.clean_title || track.title}` : `Removed from Favorites`,
      type: "info",
    });
    setTimeout(() => setToast(null), 3000);
  };

  // Play candidate handler (preview before download)
  const handlePlayCandidate = async (cand, customQueue = null) => {
    recordLearningInteraction({
      query: searchQuery,
      candidate_id: cand?.id || cand?.url,
      candidate_title: cand?.clean_title || cand?.title || "",
      event_type: "preview",
      candidate_url: cand?.url,
      engine_mode: cand?.engine_mode || engineMode,
    }).catch(() => {});
    if (!cand) return;

    // If clicking currently active track, simply toggle play/pause
    if (
      currentTrack &&
      ((currentTrack.id && cand.id && currentTrack.id === cand.id) ||
        (currentTrack.filename && cand.filename && currentTrack.filename === cand.filename) ||
        (currentTrack.file_path && cand.file_path && currentTrack.file_path === cand.file_path) ||
        (currentTrack.url && cand.url && currentTrack.url === cand.url))
    ) {
      setIsPlaying((prev) => !prev);
      return;
    }

    // Set up queue from search results or customQueue (such as downloads history)
    const queue = customQueue || (searchResults && searchResults.length > 0 ? searchResults : [cand]);
    const idx = queue.findIndex(
      (c) =>
        (c.id && cand.id && c.id === cand.id) ||
        (c.filename && cand.filename && c.filename === cand.filename) ||
        (c.url && cand.url && c.url === cand.url)
    );
    setPlaybackQueue(queue);
    setQueueIndex(idx >= 0 ? idx : 0);

    // If it is a locally downloaded media file (from history/downloads), play immediately from disk
    const filename = cand.filename || (cand.file_path ? cand.file_path.replace(/\\/g, "/").split("/").pop() : "");
    if (cand.is_local || cand.file_exists || cand.stream_url || filename || cand.file_path) {
      const localStreamUrl = cand.stream_url || (filename ? getStreamUrl(filename) : "");
      if (localStreamUrl) {
        const localTrack = {
          id: cand.id || filename,
          title: cand.clean_title || cand.title || filename,
          artist: cand.artist || cand.uploader || "",
          thumbnail: cand.thumbnail,
          duration: cand.duration,
          url: cand.url || localStreamUrl,
          stream_url: localStreamUrl,
          direct_url: localStreamUrl,
          is_local: true,
          file_path: cand.file_path,
          filename: filename,
          ext: cand.ext,
          media_type: cand.media_type || "audio",
        };
        setCurrentTrack(localTrack);
        setIsPlaying(true);
        setIsLoadingAudio(false);
        setAudioError(null);
        addRecentlyPlayed(localTrack);
        return;
      }
    }

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
      const candArtist = cand.artist || cand.uploader || "";
      const resolved = await resolveAudioStream(cand.url, {
        title: cand.clean_title || cand.title,
        artist: candArtist,
        id: cand.id,
      });

      if (resolved.playable) {
        setCurrentTrack((prev) => ({
          ...prev,
          ...resolved,
          title: resolved.title || prev.title,
          artist: resolved.artist || candArtist || prev.artist || "",
          uploader: cand.uploader || prev.uploader || "",
          thumbnail: resolved.thumbnail || prev.thumbnail,
          duration: resolved.duration || prev.duration,
          stream_url: resolved.stream_url,
          direct_url: resolved.direct_url,
          is_local: resolved.is_local,
          file_path: resolved.file_path,
        }));
        setIsPlaying(true);
        addRecentlyPlayed({
          ...optimisticTrack,
          ...resolved,
        });
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

  // On initial mount, if track has no stream URL, re-resolve cleanly
  useEffect(() => {
    if (currentTrack && !currentTrack.stream_url && !currentTrack.direct_url && currentTrack.url) {
      handlePlayCandidate(currentTrack);
    }
  }, []);

  // Reactive listeners for local storage state changes
  useEffect(() => {
    const handleFavChange = (e) => setFavorites(e.detail || getFavorites());
    const handleRecentChange = (e) => setRecentlyPlayed(e.detail || getRecentlyPlayed());
    window.addEventListener("kon_favorites_changed", handleFavChange);
    window.addEventListener("kon_recently_played_changed", handleRecentChange);
    return () => {
      window.removeEventListener("kon_favorites_changed", handleFavChange);
      window.removeEventListener("kon_recently_played_changed", handleRecentChange);
    };
  }, []);

  // Reactive lyrics fetcher when current track changes
  useEffect(() => {
    if (!currentTrack) {
      setLyricsData(null);
      setLyricsError(null);
      setIsLoadingLyrics(false);
      return;
    }

    let isMounted = true;
    const abortCtrl = new AbortController();
    setIsLoadingLyrics(true);
    setLyricsError(null);

    fetchLyrics({
      title: currentTrack.song_title || currentTrack.clean_title || currentTrack.title,
      artist: currentTrack.artist || currentTrack.uploader || "",
      duration: currentTrack.duration,
      filePath: currentTrack.file_path,
      signal: abortCtrl.signal,
    })
      .then((data) => {
        if (!isMounted) return;
        setIsLoadingLyrics(false);
        if (data && data.found) {
          setLyricsData(data);
        } else {
          setLyricsData(null);
          setLyricsError(data?.error || "No lyrics found for this track");
        }
      })
      .catch((err) => {
        if (!isMounted || err.name === "AbortError") return;
        setIsLoadingLyrics(false);
        setLyricsError(err.message || "Failed to load lyrics");
      });

    return () => {
      isMounted = false;
      abortCtrl.abort();
    };
  }, [currentTrack?.id, currentTrack?.url, currentTrack?.title, currentTrack?.artist]);

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      const tag = e.target.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea" || e.target.isContentEditable) {
        return;
      }
      if (e.code === "Space" && currentTrack) {
        e.preventDefault();
        handleTogglePlay();
      }
      if (e.key === "Escape") {
        setIsQueueOpen(false);
        setIsSettingsOpen(false);
        setIsModelModalOpen(false);
        setIsLearningDashboardOpen(false);
        setIsLyricsModalOpen(false);
      }
      if ((e.key === "l" || e.key === "L") && currentTrack) {
        e.preventDefault();
        setIsLyricsModalOpen((prev) => !prev);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [currentTrack, isQueueOpen, isSettingsOpen, isModelModalOpen, isLearningDashboardOpen]);

  const handlePlayVideo = (videoItem) => {
    if (!videoItem) return;
    // Auto-pause background audio so audio streams do not clash
    setIsPlaying(false);
    setCurrentVideo(videoItem);
    setIsVideoPlayerOpen(true);
  };

  const handleCloseVideoPlayer = () => {
    setIsVideoPlayerOpen(false);
  };

  const handleClosePlayer = () => {
    setIsPlaying(false);
    setCurrentTrack(null);
    try {
      localStorage.removeItem("kon_player_current_track");
      localStorage.removeItem("kon_player_is_playing");
      localStorage.removeItem("kon_player_current_time");
      localStorage.removeItem("kon_player_queue");
      localStorage.removeItem("kon_player_queue_index");
      localStorage.removeItem("kon_lyrics_modal_open");
    } catch (_) {}
  };

  const handleTrackListen = (track, durationListened, isCompleted) => {
    if (!track) return;
    recordLearningInteraction({
      query: searchQuery,
      candidate_id: track.id || track.url,
      candidate_title: track.clean_title || track.title || "",
      event_type: "listen",
      candidate_url: track.url,
      engine_mode: track.engine_mode || engineMode,
      listen_duration: durationListened,
      track_duration: track.duration,
    }).catch(() => {});
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
      if (s) {
        setSettings(s);
        if (typeof s.glass_mode === "boolean") {
          setGlassMode(s.glass_mode);
          try {
            localStorage.setItem("kon_glass_mode", String(s.glass_mode));
          } catch (_) {}
        }
        if (typeof s.custom_wallpaper === "string" && s.custom_wallpaper) {
          setCustomWallpaper(s.custom_wallpaper);
          try {
            localStorage.setItem("kon_custom_wallpaper", s.custom_wallpaper);
          } catch (_) {}
        }
      }
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

  // Synchronize Glass Mode class on documentElement
  useEffect(() => {
    try {
      if (glassMode) {
        document.documentElement.classList.add("theme-glass");
      } else {
        document.documentElement.classList.remove("theme-glass");
      }
      localStorage.setItem("kon_glass_mode", String(glassMode));
    } catch (_) {}
  }, [glassMode]);

  const handleToggleGlassMode = (enabled) => {
    setGlassMode(enabled);
    try {
      localStorage.setItem("kon_glass_mode", String(enabled));
    } catch (_) {}
    saveSettings({ glass_mode: enabled }).catch(() => {});
  };

  const handleSelectWallpaper = (wp) => {
    const val = wp || "";
    setCustomWallpaper(val);
    try {
      if (val) {
        localStorage.setItem("kon_custom_wallpaper", val);
      } else {
        localStorage.removeItem("kon_custom_wallpaper");
      }
    } catch (_) {}
    saveSettings({ custom_wallpaper: val }).catch(() => {});
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

      recordLearningInteraction({
        query: searchQuery,
        candidate_id: candidate.id || candidate.url,
        candidate_title: effectiveTitle,
        event_type: "download",
        candidate_url: candidate.url,
        engine_mode: candidate.engine_mode || engineMode,
      }).catch(() => {});
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
    recordLearningInteraction({
      query: searchQuery,
      candidate_id: candidate?.id || candidate?.url,
      candidate_title: candidate?.clean_title || candidate?.title || "",
      event_type: "select",
      candidate_url: candidate?.url,
      engine_mode: candidate?.engine_mode || engineMode,
    }).catch(() => {});
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
      if (typeof newSettings.glass_mode === "boolean") {
        setGlassMode(newSettings.glass_mode);
        try {
          localStorage.setItem("kon_glass_mode", String(newSettings.glass_mode));
        } catch (_) {}
      }
      if (typeof newSettings.custom_wallpaper === "string") {
        setCustomWallpaper(newSettings.custom_wallpaper);
        try {
          if (newSettings.custom_wallpaper) {
            localStorage.setItem("kon_custom_wallpaper", newSettings.custom_wallpaper);
          } else {
            localStorage.removeItem("kon_custom_wallpaper");
          }
        } catch (_) {}
      }
      const updated = await saveSettings(newSettings);
      setSettings(updated);
      const h = await fetchHealth().catch(() => null);
      if (h) setHealth(h);
    } catch (err) {
      console.error("Save settings failed:", err);
    }
  };

  return (
    <div className={`min-h-screen ${glassMode || customWallpaper ? "bg-transparent" : "bg-[var(--bg-main)]"} text-[var(--text-primary)] transition-colors duration-250 flex flex-col justify-between relative overflow-x-hidden`}>
      {/* Custom Wallpaper Backdrop OR Living Ambient Artwork Reflection Backdrop for Glass Mode */}
      {customWallpaper ? (
        <div
          className="kon-custom-wallpaper-backdrop"
          style={
            customWallpaper.startsWith("data:") ||
            customWallpaper.startsWith("http") ||
            customWallpaper.startsWith("/") ||
            customWallpaper.startsWith("file:")
              ? { backgroundImage: `url(${customWallpaper})` }
              : { background: customWallpaper }
          }
          aria-hidden="true"
        >
          <div className="kon-custom-wallpaper-overlay" />
        </div>
      ) : glassMode && (
        <div
          className="kon-glass-ambient-backdrop"
          style={
            currentTrack?.thumbnail
              ? {
                  backgroundImage: `url(${JSON.stringify(currentTrack.thumbnail)})`,
                  backgroundSize: "cover",
                  backgroundPosition: "center",
                }
              : undefined
          }
          aria-hidden="true"
        />
      )}
      <div className={`relative z-10 w-full px-0 py-2 sm:py-3 ${currentTrack ? "pb-28" : ""}`}>
        {/* 3-Column Workstation Layout */}
        <div className="flex items-start gap-3 xl:gap-5 w-full px-0">
          {/* Left Sidebar: Navigation, Engine Switcher & Autonomous Learning */}
          <LeftSidebar
            activeView={activeView}
            onViewChange={setActiveView}
            favoritesCount={favorites.length}
            recentCount={recentlyPlayed.length}
            activeDownloadsCount={
              activeTasks.filter((t) =>
                ["queued", "downloading", "processing", "verifying"].includes(t.status)
              ).length
            }
            engineMode={engineMode}
            onEngineModeChange={handleEngineModeChange}
            onOpenModelModal={() => setIsModelModalOpen(true)}
            onOpenLearningDashboard={() => setIsLearningDashboardOpen(true)}
            onOpenSettings={() => setIsSettingsOpen(true)}
            onOpenFile={handleOpenFile}
            health={health}
            theme={theme}
            onToggleTheme={handleToggleTheme}
          />

          {/* Center Stage Workspace (Uncluttered & Focused) */}
          <main className="flex-1 min-w-0 space-y-6">
            {/* Mobile / Tablet Header & Navigation (< lg screens) */}
            <div className="block lg:hidden space-y-4">
              <Header
                health={health}
                onOpenSettings={() => setIsSettingsOpen(true)}
                onOpenFile={handleOpenFile}
                onOpenModelModal={() => setIsModelModalOpen(true)}
                onOpenLearningDashboard={() => setIsLearningDashboardOpen(true)}
                theme={theme}
                onToggleTheme={handleToggleTheme}
              />
              <NavigationTabBar
                activeView={activeView}
                onViewChange={setActiveView}
                favoritesCount={favorites.length}
                recentCount={recentlyPlayed.length}
                activeDownloadsCount={
                  activeTasks.filter((t) =>
                    ["queued", "downloading", "processing", "verifying"].includes(t.status)
                  ).length
                }
                engineMode={engineMode}
                onOpenModelModal={() => setIsModelModalOpen(true)}
                onOpenLearningDashboard={() => setIsLearningDashboardOpen(true)}
              />
            </div>

            {/* Favorites and Recently Played Library Workspace */}
            {(activeView === "favorites" || activeView === "recent") && (
              <LibraryWorkspace
                activeTab={activeView}
                onTabChange={setActiveView}
                favorites={favorites}
                recentlyPlayed={recentlyPlayed}
                currentTrack={currentTrack}
                isPlaying={isPlaying}
                onPlayTrack={(track, queue) => {
                  handlePlayCandidate(track, queue);
                }}
                onToggleFavorite={handleToggleTrackFavorite}
                onClearRecentlyPlayed={() => {
                  clearRecentlyPlayed();
                  setRecentlyPlayed([]);
                }}
                onDirectDownload={handleDirectDownload}
                onOpenFile={handleOpenFile}
                history={history}
                onNavigateToSearch={() => setActiveView("search")}
                onPlayVideo={handlePlayVideo}
              />
            )}

            {/* URL Input & Ingress Bar */}
            {activeView === "search" && (
              <UrlInputBar
                initialQuery={searchQuery}
                onAnalyze={handleAnalyze}
                isLoading={isAnalyzing}
                error={analyzeError}
                onClearError={() => setAnalyzeError(null)}
                onOpenModelModal={() => setIsModelModalOpen(true)}
                onOpenLearningDashboard={() => setIsLearningDashboardOpen(true)}
                engineMode={engineMode}
                onEngineModeChange={handleEngineModeChange}
              />
            )}

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
                  setSearchQuery("");
                  try {
                    localStorage.removeItem("kon_search_results");
                    localStorage.removeItem("kon_search_state");
                    localStorage.removeItem("kon_search_meta");
                    localStorage.removeItem("kon_search_query");
                  } catch (_) {}
                }}
                onFeedback={(fb) => submitSearchFeedback(fb).catch(() => {})}
                onOpenModelModal={() => setIsModelModalOpen(true)}
                onOpenLearningDashboard={() => setIsLearningDashboardOpen(true)}
                onPlayCandidate={handlePlayCandidate}
                currentPlayingTrack={currentTrack}
                isPlaying={isPlaying}
                isLoadingAudio={isLoadingAudio}
                onAddToQueue={handleAddToQueue}
                onToggleFavorite={handleToggleTrackFavorite}
                favorites={favorites}
                onSearch={(q) => handleAnalyze(q, "video", engineMode)}
                onPlayVideo={handlePlayVideo}
              />
            )}

            {/* Media Preview & Format Selector */}
            {analyzedMedia && (
              <MediaPreviewCard
                mediaInfo={analyzedMedia}
                onStartDownload={handleStartDownload}
                onDismiss={() => setAnalyzedMedia(null)}
                onUpdateMediaInfo={setAnalyzedMedia}
                onPlayVideo={handlePlayVideo}
              />
            )}

            {/* Active Task Queue Monitor (Full view on downloads tab) */}
            {activeView === "downloads" && (
              <ActiveTasksMonitor
                tasks={activeTasks}
                onCancelTask={handleCancelTask}
                onOpenFile={handleOpenFile}
                onDismissTask={handleDismissTask}
                onRetryTask={handleRetryTask}
                onClearFinished={handleClearFinished}
                onPlayTrack={(task) => handlePlayCandidate(task, history)}
                onPlayVideo={handlePlayVideo}
                currentTrack={currentTrack}
                isPlaying={isPlaying}
                onTogglePlay={handleTogglePlay}
              />
            )}

            {/* Compact screen task monitor fallback (< xl) */}
            {activeView === "search" && activeTasks.length > 0 && (
              <div className="block xl:hidden">
                <ActiveTasksMonitor
                  tasks={activeTasks}
                  onCancelTask={handleCancelTask}
                  onOpenFile={handleOpenFile}
                  onDismissTask={handleDismissTask}
                  onRetryTask={handleRetryTask}
                  onClearFinished={handleClearFinished}
                  onPlayTrack={(task) => handlePlayCandidate(task, history)}
                  onPlayVideo={handlePlayVideo}
                  currentTrack={currentTrack}
                  isPlaying={isPlaying}
                  onTogglePlay={handleTogglePlay}
                />
              </div>
            )}

            {/* Local Download History */}
            {activeView === "downloads" && (
              <HistoryWorkspace
                history={history}
                onOpenFile={handleOpenFile}
                onDeleteItem={handleDeleteHistoryItem}
                onClearAll={handleClearHistory}
                onPlayVideo={handlePlayVideo}
                onPlayTrack={(track, queue) => {
                  handlePlayCandidate(track, queue || history);
                }}
                currentTrack={currentTrack}
                isPlaying={isPlaying}
                onTogglePlay={handleTogglePlay}
              />
            )}
          </main>

          {/* Right Sidebar: Now Playing Spotlight, Queue Peek & Downloads Stream */}
          <RightSidebar
            currentTrack={currentTrack}
            isPlaying={isPlaying}
            isLoadingAudio={isLoadingAudio}
            onTogglePlay={handleTogglePlay}
            onPlayCandidate={handlePlayCandidate}
            onToggleFavorite={() => handleToggleTrackFavorite(currentTrack)}
            isFavorite={isTrackFavorite(currentTrack, favorites)}
            onDirectDownload={handleDirectDownload}
            playbackQueue={playbackQueue}
            queueIndex={queueIndex}
            onToggleQueue={() => setIsQueueOpen((prev) => !prev)}
            activeTasks={activeTasks}
            onCancelTask={handleCancelTask}
            onOpenFile={handleOpenFile}
            lyricsData={lyricsData}
            isLoadingLyrics={isLoadingLyrics}
            lyricsError={lyricsError}
            onOpenFullscreenLyrics={() => setIsLyricsModalOpen(true)}
            glassMode={glassMode}
          />
        </div>
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
        glassMode={glassMode}
        onToggleGlassMode={handleToggleGlassMode}
        customWallpaper={customWallpaper}
        onSelectWallpaper={handleSelectWallpaper}
      />

      {/* KON Search 1.2 Rei Model Spotlight Modal */}
      <ModelInfoModal
        isOpen={isModelModalOpen}
        onClose={() => setIsModelModalOpen(false)}
      />

      {/* Autonomous Continuous Learning Dashboard Modal */}
      <LearningDashboardModal
        isOpen={isLearningDashboardOpen}
        onClose={() => setIsLearningDashboardOpen(false)}
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
        onToggleQueue={() => setIsQueueOpen((prev) => !prev)}
        isQueueOpen={isQueueOpen}
        onToggleFavorite={() => handleToggleTrackFavorite(currentTrack)}
        isFavorite={isTrackFavorite(currentTrack, favorites)}
        onTrackListen={handleTrackListen}
        onToggleLyrics={() => setIsLyricsModalOpen((prev) => !prev)}
        isLyricsOpen={isLyricsModalOpen}
      />

      {/* Listening Queue Slide-Out Drawer */}
      <PlaybackQueueDrawer
        isOpen={isQueueOpen}
        onClose={() => setIsQueueOpen(false)}
        queue={playbackQueue}
        currentIndex={queueIndex}
        currentTrack={currentTrack}
        isPlaying={isPlaying}
        onPlayTrack={(cand) => handlePlayCandidate(cand)}
        onRemoveTrack={handleRemoveFromQueue}
        onClearQueue={handleClearQueue}
        onDirectDownload={handleDirectDownload}
        onOpenFile={handleOpenFile}
        history={history}
      />

      {/* Full-Screen / Theater Lyrics Experience */}
      <LyricsModal
        isOpen={isLyricsModalOpen}
        onClose={() => setIsLyricsModalOpen(false)}
        currentTrack={currentTrack}
        isPlaying={isPlaying}
        onTogglePlay={handleTogglePlay}
        lyricsData={lyricsData}
        isLoadingLyrics={isLoadingLyrics}
        lyricsError={lyricsError}
        glassMode={glassMode}
      />

      {/* Universal In-Browser Video Player (Theater & Mini-Player Modes) */}
      <VideoPlayerModal
        video={currentVideo}
        isOpen={isVideoPlayerOpen}
        mode={videoPlayerMode}
        onClose={handleCloseVideoPlayer}
        onModeChange={(newMode) => setVideoPlayerMode(newMode)}
        onDownload={(vid) => handleDirectDownload(vid, "video")}
        onPauseAudio={() => setIsPlaying(false)}
      />

      {/* Interactive Toast Notification with Pop-Up Physics */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 max-w-md p-4 rounded-2xl neu-card shadow-2xl flex items-center justify-between gap-3.5 neu-toast-pop neu-popup-aura text-[#1E293B] dark:text-[#F8FAFC] border border-[#0084FF]/25 overflow-hidden">
          <div className="flex items-center gap-3 min-w-0">
            <span
              className={`w-1.5 self-stretch rounded-full shrink-0 ${
                toast.type === "success"
                  ? "bg-[#10B981] shadow-[0_0_8px_rgba(16,185,129,0.6)]"
                  : toast.type === "error"
                  ? "bg-[#EF4444] shadow-[0_0_8px_rgba(239,68,68,0.6)]"
                  : "bg-[#0084FF] shadow-[0_0_8px_rgba(0,132,255,0.6)]"
              }`}
            />
            <span className="text-xs font-semibold leading-relaxed">
              {toast.message}
            </span>
          </div>
          <button
            onClick={() => setToast(null)}
            className="neu-raised p-1.5 text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F8FAFC] cursor-pointer shrink-0 rounded-xl neu-btn-elastic group"
          >
            <X className="w-3.5 h-3.5 transition-transform duration-200 group-hover:rotate-90" />
          </button>
        </div>
      )}
    </div>
  );
}
