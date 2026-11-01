import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Play,
  Pause,
  Volume2,
  Volume1,
  VolumeX,
  Maximize2,
  Minimize2,
  RotateCcw,
  RotateCw,
  Download,
  Loader2,
  AlertCircle,
  X,
  ExternalLink,
  ChevronDown,
  Sparkles,
  Film,
  MonitorPlay,
  PictureInPicture2,
  Layers,
} from "lucide-react";
import { resolveVideoStream, getVideoStreamUrl } from "../api";

/**
 * Format seconds to MM:SS or HH:MM:SS
 */
function formatTime(seconds) {
  if (!seconds || isNaN(seconds) || seconds < 0) return "0:00";
  const s = Math.floor(seconds);
  const hrs = Math.floor(s / 3600);
  const mins = Math.floor((s % 3600) / 60);
  const secs = s % 60;
  const padSecs = secs < 10 ? `0${secs}` : `${secs}`;

  if (hrs > 0) {
    const padMins = mins < 10 ? `0${mins}` : `${mins}`;
    return `${hrs}:${padMins}:${padSecs}`;
  }
  return `${mins}:${padSecs}`;
}

const PLAYBACK_SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

/**
 * Universal In-Browser Video Player Component
 * Supports Theater Modal Mode and Floating Mini-Player (Picture-in-Picture) Mode.
 * Seamlessly plays videos from YouTube, Vimeo, direct URLs, and downloaded local files.
 */
export function getYouTubeVideoId(urlOrId) {
  if (!urlOrId) return null;
  const str = String(urlOrId).trim();
  if (str.startsWith("yt_")) return str.slice(3).replace(/^ch_/, "");
  const m = str.match(/(?:youtu\.be\/|youtube\.com\/(?:embed\/|v\/|watch\?v=|watch\?.+&v=))([\w-]{11})/i);
  if (m) return m[1];
  if (/^[a-zA-Z0-9_-]{11}$/.test(str)) return str;
  return null;
}

export default function VideoPlayerModal({
  video,
  isOpen,
  mode = "theater", // "theater" | "mini"
  onClose,
  onModeChange,
  onDownload,
  onPauseAudio,
}) {
  const videoRef = useRef(null);
  const containerRef = useRef(null);
  const progressBarRef = useRef(null);
  const hideControlsTimerRef = useRef(null);

  // Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [bufferedEnd, setBufferedEnd] = useState(0);
  const [volume, setVolume] = useState(() => {
    try {
      const saved = localStorage.getItem("kon_video_volume");
      return saved !== null ? Number(saved) : 0.85;
    } catch (_) {
      return 0.85;
    }
  });
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [areControlsVisible, setAreControlsVisible] = useState(true);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);

  // Stream resolution & playback engine state
  const [isLoadingStream, setIsLoadingStream] = useState(false);
  const [streamError, setStreamError] = useState(null);
  const [resolvedInfo, setResolvedInfo] = useState(null);
  const [playerEngine, setPlayerEngine] = useState(() => {
    const isDirectLocal = !!(video?.is_local || video?.file_path || video?.stream_url?.startsWith("/api/stream/"));
    if (isDirectLocal) return "direct";
    const directYt = getYouTubeVideoId(video?.id || video?.candidate_id || video?.webpage_url || video?.url);
    if (directYt) return "smart";
    return "direct";
  });

  // Hover timestamp preview
  const [hoverTime, setHoverTime] = useState(null);
  const [hoverPosition, setHoverPosition] = useState(0);

  // Save volume preference
  useEffect(() => {
    try {
      localStorage.setItem("kon_video_volume", String(volume));
    } catch (_) {}
  }, [volume]);

  // Resolve video stream whenever the video prop changes
  useEffect(() => {
    if (!video || !isOpen) return;

    let isMounted = true;
    const abortController = new AbortController();

    // Immediate detection of YouTube ID for zero-latency instant start
    const directYtId = getYouTubeVideoId(video.id || video.candidate_id || video.webpage_url || video.url);

    // If stream URL is already resolved and matches this video
    if (video.stream_url) {
      setResolvedInfo({
        stream_url: video.stream_url,
        title: video.title,
        uploader: video.uploader || video.artist,
        is_local: !!video.is_local,
        resolution: video.resolution || (video.is_local ? "Local Video" : "Direct Stream"),
        youtube_id: directYtId,
      });
      setIsLoadingStream(false);
      setStreamError(null);
      return;
    }

    // For YouTube videos, initialize immediately so playback starts instantly without waiting for backend
    if (directYtId && !video.is_local) {
      setResolvedInfo((prev) => ({
        ...prev,
        youtube_id: directYtId,
        title: video.title,
        uploader: video.uploader || video.artist,
        is_local: false,
        resolution: video.resolution || "HD Stream",
        thumbnail: video.thumbnail,
      }));
      setIsLoadingStream(false);
      setStreamError(null);
    } else {
      setIsLoadingStream(true);
      setStreamError(null);
    }

    // Resolve stream & full metadata in background
    async function resolve() {
      try {
        const data = await resolveVideoStream(video.webpage_url || video.url, {
          title: video.title,
          id: video.id || video.candidate_id,
          uploader: video.uploader || video.artist,
          signal: abortController.signal,
        });

        if (!isMounted) return;

        setResolvedInfo((prev) => ({
          ...prev,
          ...data,
          youtube_id: data.youtube_id || directYtId,
        }));
        setIsLoadingStream(false);
      } catch (err) {
        if (!isMounted || err.name === "AbortError") return;
        if (!directYtId) {
          setStreamError(err.message || "Unable to resolve playable video stream");
          setIsLoadingStream(false);
        }
      }
    }

    resolve();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [video, isOpen]);

  // Sync volume & playback rate to video element
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.volume = isMuted ? 0 : volume;
      videoRef.current.playbackRate = playbackRate;
    }
  }, [volume, isMuted, playbackRate]);

  // Handle auto-hide controls in theater mode
  const resetHideTimer = useCallback(() => {
    setAreControlsVisible(true);
    if (hideControlsTimerRef.current) {
      clearTimeout(hideControlsTimerRef.current);
    }
    if (isPlaying) {
      hideControlsTimerRef.current = setTimeout(() => {
        setAreControlsVisible(false);
        setShowSpeedMenu(false);
      }, 3000);
    }
  }, [isPlaying]);

  useEffect(() => {
    if (!isPlaying) {
      setAreControlsVisible(true);
      if (hideControlsTimerRef.current) {
        clearTimeout(hideControlsTimerRef.current);
      }
    } else {
      resetHideTimer();
    }
    return () => {
      if (hideControlsTimerRef.current) {
        clearTimeout(hideControlsTimerRef.current);
      }
    };
  }, [isPlaying, resetHideTimer]);

  // Handle play/pause
  const togglePlay = useCallback(() => {
    if (!videoRef.current) return;
    if (videoRef.current.paused) {
      videoRef.current.play().catch(() => {});
      if (onPauseAudio) onPauseAudio();
    } else {
      videoRef.current.pause();
    }
  }, [onPauseAudio]);

  // Seek relative
  const seekRelative = useCallback((delta) => {
    if (!videoRef.current) return;
    const next = Math.max(0, Math.min(videoRef.current.duration || 0, videoRef.current.currentTime + delta));
    videoRef.current.currentTime = next;
    setCurrentTime(next);
  }, []);

  // Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    if (!containerRef.current) return;

    if (!document.fullscreenElement) {
      containerRef.current.requestFullscreen().catch(() => {});
      setIsFullscreen(true);
    } else {
      document.exitFullscreen().catch(() => {});
      setIsFullscreen(false);
    }
  }, []);

  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => document.removeEventListener("fullscreenchange", handleFsChange);
  }, []);

  // Keyboard controls
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      const activeTag = document.activeElement?.tagName?.toLowerCase();
      if (activeTag === "input" || activeTag === "textarea" || document.activeElement?.isContentEditable) {
        return;
      }

      switch (e.key) {
        case " ":
        case "k":
        case "K":
          e.preventDefault();
          togglePlay();
          break;
        case "f":
        case "F":
          e.preventDefault();
          toggleFullscreen();
          break;
        case "m":
        case "M":
          e.preventDefault();
          setIsMuted((prev) => !prev);
          break;
        case "ArrowLeft":
        case "j":
        case "J":
          e.preventDefault();
          seekRelative(-5);
          break;
        case "ArrowRight":
        case "l":
        case "L":
          e.preventDefault();
          seekRelative(5);
          break;
        case "ArrowUp":
          e.preventDefault();
          setVolume((prev) => Math.min(1, Number((prev + 0.05).toFixed(2))));
          setIsMuted(false);
          break;
        case "ArrowDown":
          e.preventDefault();
          setVolume((prev) => Math.max(0, Number((prev - 0.05).toFixed(2))));
          break;
        case "Escape":
          if (isFullscreen) {
            document.exitFullscreen().catch(() => {});
          } else if (mode === "theater") {
            if (onModeChange) onModeChange("mini");
            else if (onClose) onClose();
          } else {
            if (onClose) onClose();
          }
          break;
        default:
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, mode, isFullscreen, togglePlay, toggleFullscreen, seekRelative, onClose, onModeChange]);

  // Video element event listeners
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    setCurrentTime(videoRef.current.currentTime);
    if (videoRef.current.buffered.length > 0) {
      setBufferedEnd(videoRef.current.buffered.end(videoRef.current.buffered.length - 1));
    }
  };

  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;
    setDuration(videoRef.current.duration || 0);
  };

  const handleSeekClick = (e) => {
    if (!progressBarRef.current || !videoRef.current || !duration) return;
    const rect = progressBarRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, clickX / rect.width));
    const target = ratio * duration;
    videoRef.current.currentTime = target;
    setCurrentTime(target);
  };

  const handleSeekMouseMove = (e) => {
    if (!progressBarRef.current || !duration) return;
    const rect = progressBarRef.current.getBoundingClientRect();
    const hoverX = e.clientX - rect.left;
    const ratio = Math.max(0, Math.min(1, hoverX / rect.width));
    setHoverTime(ratio * duration);
    setHoverPosition(hoverX);
  };

  const handleSeekMouseLeave = () => {
    setHoverTime(null);
  };

  if (!isOpen || !video) return null;

  const currentStreamRaw = resolvedInfo?.stream_url;
  const playableSrc = currentStreamRaw ? getVideoStreamUrl(currentStreamRaw) : null;
  const videoTitle = resolvedInfo?.title || video.title || "Video";
  const videoUploader = resolvedInfo?.uploader || video.uploader || video.artist || "Unknown Creator";
  const isLocal = !!(resolvedInfo?.is_local || video.is_local);
  const detectedYtId =
    resolvedInfo?.youtube_id ||
    getYouTubeVideoId(video?.id || video?.candidate_id || video?.webpage_url || video?.url);
  const useEmbedPlayer = !!detectedYtId && playerEngine === "smart";
  const resolution = resolvedInfo?.resolution || video.resolution || (isLocal ? "Local File" : "HD Stream");

  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;
  const bufferPercent = duration > 0 ? (bufferedEnd / duration) * 100 : 0;

  // Render Mini-Player (Floating Picture-in-Picture)
  if (mode === "mini") {
    return (
      <div
        ref={containerRef}
        className="fixed bottom-24 right-6 z-50 w-84 sm:w-96 rounded-2xl neu-raised border border-[#0084FF]/30 shadow-[0_12px_40px_rgba(0,0,0,0.5)] overflow-hidden backdrop-blur-xl bg-[#1E293B]/95 text-white transition-all duration-300 select-none animate-in fade-in slide-in-from-bottom-4"
      >
        {/* Top Mini Header */}
        <div className="flex items-center justify-between px-3.5 py-2 bg-black/40 border-b border-white/10 text-xs">
          <div className="flex items-center gap-2 min-w-0 mr-2">
            <Film className="w-3.5 h-3.5 text-[#0084FF] shrink-0" />
            <span className="font-semibold text-[11px] truncate text-slate-200">
              {videoTitle}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            {/* Expand to Theater Mode */}
            <button
              type="button"
              onClick={() => onModeChange && onModeChange("theater")}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
              title="Expand to Theater Mode"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
            {/* Close */}
            <button
              type="button"
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-[#EF4444] hover:bg-white/10 transition-colors cursor-pointer"
              title="Close Video Player"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Video Canvas Container */}
        <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden group">
          {useEmbedPlayer ? (
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${detectedYtId}?autoplay=1&enablejsapi=1&rel=0&modestbranding=1`}
              title={videoTitle}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
              className="w-full h-full border-0"
            />
          ) : isLoadingStream ? (
            <div className="flex flex-col items-center gap-2 text-slate-400 p-4 text-center">
              <Loader2 className="w-7 h-7 animate-spin text-[#0084FF]" />
              <span className="text-xs font-medium">Resolving stream...</span>
            </div>
          ) : streamError ? (
            <div className="flex flex-col items-center gap-2 text-[#EF4444] p-4 text-center">
              <AlertCircle className="w-6 h-6" />
              <span className="text-xs font-semibold">{streamError}</span>
            </div>
          ) : playableSrc ? (
            <video
              ref={videoRef}
              src={playableSrc}
              playsInline
              crossOrigin="anonymous"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onPlay={() => {
                setIsPlaying(true);
                if (onPauseAudio) onPauseAudio();
              }}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
              onClick={togglePlay}
              className="w-full h-full object-contain cursor-pointer"
            />
          ) : (
            <div className="text-xs text-slate-400">Stream unavailable</div>
          )}

          {/* Mini Play/Pause overlay (only for native video) */}
          {!useEmbedPlayer && !isLoadingStream && !streamError && playableSrc && (
            <button
              type="button"
              onClick={togglePlay}
              className={`absolute inset-0 flex items-center justify-center bg-black/40 transition-opacity ${
                isPlaying ? "opacity-0 group-hover:opacity-100" : "opacity-100"
              }`}
            >
              <div className="w-10 h-10 rounded-full bg-[#0084FF] text-white flex items-center justify-center shadow-lg transition-transform hover:scale-110">
                {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
              </div>
            </button>
          )}

          {/* Mini Scrub bar at bottom of video (only for native video) */}
          {!useEmbedPlayer && (
            <div
              ref={progressBarRef}
              onClick={handleSeekClick}
              className="absolute bottom-0 left-0 right-0 h-1 bg-white/20 hover:h-2 transition-all cursor-pointer group/bar"
            >
              <div
                className="absolute top-0 bottom-0 left-0 bg-white/30"
                style={{ width: `${bufferPercent}%` }}
              />
              <div
                className="absolute top-0 bottom-0 left-0 bg-[#0084FF]"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          )}
        </div>

        {/* Mini Bottom Controls Bar */}
        <div className="flex items-center justify-between px-3 py-2 bg-[#0F172A]/90 text-xs">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={togglePlay}
              className="text-slate-300 hover:text-white transition-colors cursor-pointer"
            >
              {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
            </button>
            <span className="text-[10px] text-slate-400 font-mono">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            {isLocal && (
              <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30">
                Local
              </span>
            )}
            <button
              type="button"
              onClick={() => setIsMuted((prev) => !prev)}
              className="text-slate-400 hover:text-white transition-colors cursor-pointer"
            >
              {isMuted || volume === 0 ? <VolumeX className="w-3.5 h-3.5 text-rose-400" /> : <Volume2 className="w-3.5 h-3.5" />}
            </button>
            <button
              type="button"
              onClick={() => onModeChange && onModeChange("theater")}
              className="text-slate-400 hover:text-[#0084FF] transition-colors cursor-pointer"
              title="Expand to Theater View"
            >
              <PictureInPicture2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Render Theater Mode Modal
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-xl p-3 sm:p-6 select-none animate-in fade-in duration-200"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div
        ref={containerRef}
        onMouseMove={resetHideTimer}
        className="relative w-full max-w-5xl rounded-3xl overflow-hidden neu-raised border border-white/10 shadow-[0_25px_70px_rgba(0,0,0,0.85)] bg-black flex flex-col group"
      >
        {/* Top Header Overlay */}
        <div
          className={`absolute top-0 left-0 right-0 z-30 p-4 sm:p-5 flex items-center justify-between bg-gradient-to-b from-black/90 via-black/50 to-transparent transition-opacity duration-300 ${
            areControlsVisible ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
        >
          <div className="flex items-center gap-3 min-w-0 mr-4">
            <div className="w-9 h-9 rounded-2xl bg-[#0084FF]/20 border border-[#0084FF]/40 flex items-center justify-center shrink-0">
              <Film className="w-4 h-4 text-[#0084FF]" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm sm:text-base font-bold text-white truncate m-0">
                {videoTitle}
              </h2>
              <div className="flex items-center gap-2 text-xs text-slate-300 mt-0.5">
                <span className="truncate">{videoUploader}</span>
                <span className="text-slate-500 font-bold">|</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wide uppercase ${
                  isLocal
                    ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                    : "bg-[#0084FF]/20 text-[#0084FF] border border-[#0084FF]/30"
                }`}>
                  {resolution}
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Player Engine Switcher */}
            {detectedYtId && (
              <button
                type="button"
                onClick={() => setPlayerEngine((prev) => (prev === "smart" ? "direct" : "smart"))}
                className="neu-raised px-2.5 py-1.5 rounded-xl text-xs font-semibold text-slate-300 hover:text-white hover:border-[#0084FF]/40 flex items-center gap-1.5 transition-all cursor-pointer"
                title={
                  playerEngine === "smart"
                    ? (isLocal ? "Switch to Local Downloaded File" : "Switch to Direct Proxy Stream")
                    : "Switch to Smart Player (Instant YouTube Embed and Full Audio)"
                }
              >
                <Sparkles className="w-3.5 h-3.5 text-[#0084FF]" />
                <span className="hidden sm:inline">
                  {playerEngine === "smart" ? "Smart Player" : (isLocal ? "Local Video" : "Direct Proxy")}
                </span>
              </button>
            )}

            {/* Download Button */}
            {onDownload && (
              <button
                type="button"
                onClick={() => onDownload(video)}
                className="neu-raised px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-300 hover:text-white hover:border-[#0084FF]/40 flex items-center gap-1.5 transition-all cursor-pointer"
                title="Download this video"
              >
                <Download className="w-3.5 h-3.5 text-[#0084FF]" />
                <span className="hidden sm:inline">Download</span>
              </button>
            )}

            {/* Switch to Floating Mini Player */}
            <button
              type="button"
              onClick={() => onModeChange && onModeChange("mini")}
              className="p-2 rounded-xl neu-raised text-slate-300 hover:text-[#0084FF] transition-all cursor-pointer"
              title="Minimize to Floating Mini-Player (watch while browsing)"
            >
              <PictureInPicture2 className="w-4 h-4" />
            </button>

            {/* Close Button */}
            <button
              type="button"
              onClick={onClose}
              className="p-2 rounded-xl neu-raised text-slate-300 hover:text-[#EF4444] transition-all cursor-pointer"
              title="Close Video (Esc)"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* High-Resolution Video Player Canvas */}
        <div className="relative aspect-video w-full bg-black flex items-center justify-center overflow-hidden">
          {useEmbedPlayer ? (
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${detectedYtId}?autoplay=1&enablejsapi=1&rel=0&modestbranding=1`}
              title={videoTitle}
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
              className="w-full h-full border-0"
            />
          ) : isLoadingStream ? (
            <div className="flex flex-col items-center gap-3 text-slate-400 p-8 text-center">
              <Loader2 className="w-10 h-10 animate-spin text-[#0084FF]" />
              <div className="text-sm font-semibold text-white">Preparing Video Stream</div>
              <div className="text-xs text-slate-400 max-w-sm">
                Resolving video source and setting up high-performance byte-range streaming proxy...
              </div>
            </div>
          ) : streamError ? (
            <div className="flex flex-col items-center gap-3 text-[#EF4444] p-8 text-center max-w-md">
              <AlertCircle className="w-10 h-10" />
              <div className="text-sm font-bold text-white">Playback Error</div>
              <div className="text-xs text-slate-400">{streamError}</div>
              {video.webpage_url && (
                <a
                  href={video.webpage_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-2 inline-flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 text-xs font-semibold text-white transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  <span>Open in external browser</span>
                </a>
              )}
            </div>
          ) : playableSrc ? (
            <video
              ref={videoRef}
              src={playableSrc}
              playsInline
              crossOrigin="anonymous"
              onTimeUpdate={handleTimeUpdate}
              onLoadedMetadata={handleLoadedMetadata}
              onPlay={() => {
                setIsPlaying(true);
                if (onPauseAudio) onPauseAudio();
              }}
              onPause={() => setIsPlaying(false)}
              onEnded={() => setIsPlaying(false)}
              onClick={togglePlay}
              className="w-full h-full object-contain cursor-pointer"
            />
          ) : (
            <div className="text-sm text-slate-400">Stream unavailable</div>
          )}

          {/* Big Center Play/Pause Indicator on click / pause (for native video) */}
          {!useEmbedPlayer && !isLoadingStream && !streamError && playableSrc && !isPlaying && (
            <button
              type="button"
              onClick={togglePlay}
              className="absolute inset-0 flex items-center justify-center bg-black/35 hover:bg-black/25 transition-colors cursor-pointer"
            >
              <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-[#0084FF]/90 hover:bg-[#0084FF] text-white flex items-center justify-center shadow-[0_0_30px_rgba(0,132,255,0.6)] transform hover:scale-105 transition-all">
                <Play className="w-8 h-8 sm:w-10 sm:h-10 fill-current ml-1" />
              </div>
            </button>
          )}
        </div>

        {/* Bottom Control Bar Overlay (active for native video) */}
        {!useEmbedPlayer && (
        <div
          className={`absolute bottom-0 left-0 right-0 z-30 p-4 sm:p-5 bg-gradient-to-t from-black/95 via-black/70 to-transparent transition-opacity duration-300 flex flex-col gap-3 ${
            areControlsVisible ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
        >
          {/* Timeline Seekbar with Hover Tooltip */}
          <div
            ref={progressBarRef}
            onClick={handleSeekClick}
            onMouseMove={handleSeekMouseMove}
            onMouseLeave={handleSeekMouseLeave}
            className="relative h-2 bg-white/20 hover:h-3 rounded-full transition-all cursor-pointer group/timeline flex items-center"
          >
            {/* Buffer Track */}
            <div
              className="absolute top-0 bottom-0 left-0 bg-white/30 rounded-full transition-all"
              style={{ width: `${bufferPercent}%` }}
            />
            {/* Played Track */}
            <div
              className="absolute top-0 bottom-0 left-0 bg-gradient-to-r from-[#0084FF] to-[#38BDF8] rounded-full shadow-[0_0_10px_rgba(0,132,255,0.5)]"
              style={{ width: `${progressPercent}%` }}
            />
            {/* Scrubber Knob */}
            <div
              className="absolute w-3.5 h-3.5 rounded-full bg-white shadow-md transform -translate-x-1/2 scale-0 group-hover/timeline:scale-100 transition-transform"
              style={{ left: `${progressPercent}%` }}
            />

            {/* Hover Timestamp Preview Pip */}
            {hoverTime !== null && (
              <div
                className="absolute -top-8 transform -translate-x-1/2 px-2 py-0.5 rounded-md bg-[#0F172A] border border-white/20 text-[10px] font-mono font-bold text-white shadow-lg pointer-events-none"
                style={{ left: `${hoverPosition}px` }}
              >
                {formatTime(hoverTime)}
              </div>
            )}
          </div>

          {/* Primary Controls Row */}
          <div className="flex items-center justify-between text-white">
            {/* Left Controls: Play, Skip, Volume, Time */}
            <div className="flex items-center gap-2 sm:gap-4">
              {/* Play/Pause */}
              <button
                type="button"
                onClick={togglePlay}
                className="w-9 h-9 rounded-xl bg-white/10 hover:bg-[#0084FF] text-white flex items-center justify-center transition-colors cursor-pointer"
                title={isPlaying ? "Pause (Space)" : "Play (Space)"}
              >
                {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
              </button>

              {/* Rewind 5s */}
              <button
                type="button"
                onClick={() => seekRelative(-5)}
                className="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                title="Rewind 5 seconds (Left Arrow)"
              >
                <RotateCcw className="w-4 h-4" />
              </button>

              {/* Fast Forward 5s */}
              <button
                type="button"
                onClick={() => seekRelative(5)}
                className="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                title="Fast forward 5 seconds (Right Arrow)"
              >
                <RotateCw className="w-4 h-4" />
              </button>

              {/* Volume Slider & Mute Toggle */}
              <div className="flex items-center gap-2 group/vol">
                <button
                  type="button"
                  onClick={() => setIsMuted((prev) => !prev)}
                  className="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                  title={isMuted ? "Unmute (M)" : "Mute (M)"}
                >
                  {isMuted || volume === 0 ? (
                    <VolumeX className="w-4 h-4 text-rose-400" />
                  ) : volume < 0.5 ? (
                    <Volume1 className="w-4 h-4" />
                  ) : (
                    <Volume2 className="w-4 h-4" />
                  )}
                </button>

                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={isMuted ? 0 : volume}
                  onChange={(e) => {
                    setVolume(Number(e.target.value));
                    setIsMuted(false);
                  }}
                  className="w-16 sm:w-20 h-1.5 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[#0084FF] transition-all"
                  title={`Volume: ${Math.round((isMuted ? 0 : volume) * 100)}%`}
                />
              </div>

              {/* Time Display */}
              <div className="text-xs font-mono text-slate-300 hidden sm:block">
                <span>{formatTime(currentTime)}</span>
                <span className="text-slate-500 mx-1">/</span>
                <span className="text-slate-400">{formatTime(duration)}</span>
              </div>
            </div>

            {/* Right Controls: Playback Speed, Fullscreen */}
            <div className="flex items-center gap-2 sm:gap-3">
              {/* Playback Speed Menu */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowSpeedMenu((prev) => !prev)}
                  className="px-2.5 py-1.5 rounded-xl bg-white/10 hover:bg-white/20 text-xs font-bold text-slate-200 flex items-center gap-1 transition-colors cursor-pointer"
                  title="Playback Speed"
                >
                  <span>{playbackRate}x</span>
                  <ChevronDown className="w-3 h-3 text-slate-400" />
                </button>

                {showSpeedMenu && (
                  <div className="absolute bottom-full right-0 mb-2 py-1 w-24 rounded-xl bg-[#0F172A] border border-white/20 shadow-2xl flex flex-col z-40">
                    {PLAYBACK_SPEEDS.map((speed) => (
                      <button
                        key={speed}
                        type="button"
                        onClick={() => {
                          setPlaybackRate(speed);
                          setShowSpeedMenu(false);
                        }}
                        className={`px-3 py-1.5 text-xs text-left cursor-pointer transition-colors ${
                          playbackRate === speed
                            ? "bg-[#0084FF] text-white font-bold"
                            : "text-slate-300 hover:bg-white/10"
                        }`}
                      >
                        {speed === 1.0 ? "1.0x (Normal)" : `${speed}x`}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Toggle Fullscreen */}
              <button
                type="button"
                onClick={toggleFullscreen}
                className="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
                title={isFullscreen ? "Exit Fullscreen (F)" : "Enter Fullscreen (F)"}
              >
                {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
              </button>
            </div>
          </div>
        </div>
        )}
      </div>
    </div>
  );
}
