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
  Film,
  PictureInPicture2,
  ShieldCheck,
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

/**
 * Extract 11-char YouTube Video ID from any video metadata object or URL.
 * Handles yt_ prefix, direct ID, youtu.be, watch?v=, watch?...&v=, shorts, embed, and vi thumbnail URLs.
 */
export function extractYouTubeId(video, resolvedInfo = null) {
  if (!video && !resolvedInfo) return null;
  const sources = [
    video?.youtube_id,
    video?.id,
    video?.candidate_id,
    video?.url,
    video?.webpage_url,
    video?.thumbnail,
    resolvedInfo?.youtube_id,
    resolvedInfo?.id,
    resolvedInfo?.candidate_id,
    resolvedInfo?.url,
    resolvedInfo?.webpage_url,
    resolvedInfo?.thumbnail,
  ];

  for (const item of sources) {
    if (!item || typeof item !== "string") continue;
    const s = item.trim();
    if (s.startsWith("yt_") && s.length === 14) {
      return s.slice(3);
    }
    if (s.length === 11 && /^[a-zA-Z0-9_-]{11}$/.test(s)) {
      return s;
    }
    const match = s.match(/(?:[?&]v=|youtu\.be\/|\/(?:embed|shorts|v)\/|\/vi(?:_webp)?\/)([a-zA-Z0-9_-]{11})/);
    if (match) {
      return match[1];
    }
  }
  return null;
}

/**
 * YouTube Embed Video Player Modal.
 * Switched completely to the official YouTube embed player.
 * Supports Theater Modal Mode and Floating Mini-Player (Picture-in-Picture) Mode.
 * Local files fall back cleanly to native HTML5 playback.
 */
export default function VideoPlayerModal({
  video,
  isOpen,
  onClose,
  mode = "theater", // "theater" | "mini"
  onModeChange,
  onPauseAudio,
  onDownload,
}) {
  const videoRef = useRef(null);
  const containerRef = useRef(null);
  const hideControlsTimeoutRef = useRef(null);

  // Playback & controls state
  const [areControlsVisible, setAreControlsVisible] = useState(true);
  const [resolvedInfo, setResolvedInfo] = useState(null);
  const [isLoadingStream, setIsLoadingStream] = useState(false);
  const [streamError, setStreamError] = useState(null);

  // Extract YouTube ID immediately
  const youtubeId = extractYouTubeId(video, resolvedInfo);
  const isLocal = !youtubeId && !!(video?.is_local || resolvedInfo?.is_local || video?.file_path);

  const videoTitle = resolvedInfo?.title || video?.title || "Video Player";
  const videoUploader = resolvedInfo?.uploader || video?.uploader || video?.artist || "YouTube Creator";

  // Auto-pause background audio when player opens
  useEffect(() => {
    if (isOpen && onPauseAudio) {
      onPauseAudio();
    }
  }, [isOpen, onPauseAudio]);

  // Background resolution for metadata or local stream fallback
  useEffect(() => {
    if (!video || !isOpen) return;

    let isMounted = true;
    const abortController = new AbortController();

    // If stream URL is already known for local video
    if (video.stream_url && video.is_local) {
      setResolvedInfo({
        stream_url: video.stream_url,
        title: video.title,
        uploader: video.uploader || video.artist,
        is_local: true,
      });
      return;
    }

    // Only resolve via backend if not a direct YouTube ID or if metadata is needed
    if (!youtubeId) {
      setIsLoadingStream(true);
      setStreamError(null);

      async function resolve() {
        try {
          const data = await resolveVideoStream(video.webpage_url || video.url || video.id, {
            title: video.title,
            id: video.id || video.candidate_id,
            uploader: video.uploader || video.artist,
            signal: abortController.signal,
          });

          if (!isMounted) return;
          setResolvedInfo(data);
          setIsLoadingStream(false);
        } catch (err) {
          if (!isMounted || err.name === "AbortError") return;
          setStreamError(err.message || "Unable to resolve video stream");
          setIsLoadingStream(false);
        }
      }

      resolve();
    }

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [video, isOpen, youtubeId]);

  // Auto-hide controls in theater mode
  const resetHideTimer = useCallback(() => {
    setAreControlsVisible(true);
    if (hideControlsTimeoutRef.current) {
      clearTimeout(hideControlsTimeoutRef.current);
    }
    if (mode === "theater") {
      hideControlsTimeoutRef.current = setTimeout(() => {
        setAreControlsVisible(false);
      }, 3500);
    }
  }, [mode]);

  useEffect(() => {
    resetHideTimer();
    return () => {
      if (hideControlsTimeoutRef.current) {
        clearTimeout(hideControlsTimeoutRef.current);
      }
    };
  }, [resetHideTimer]);

  // Escape key closes modal
  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(() => {});
        } else {
          onClose();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !video) return null;

  const currentStreamRaw = resolvedInfo?.stream_url || video?.stream_url;
  const playableSrc = currentStreamRaw ? getVideoStreamUrl(currentStreamRaw) : null;

  // Mini-Player Mode (Floating Picture-in-Picture)
  if (mode === "mini") {
    return (
      <div
        ref={containerRef}
        className="fixed bottom-24 right-6 z-50 w-84 sm:w-96 rounded-2xl neu-raised border border-[#EF4444]/40 shadow-[0_12px_40px_rgba(0,0,0,0.65)] overflow-hidden backdrop-blur-xl bg-[#1E293B]/95 text-white transition-all duration-300 select-none animate-in fade-in slide-in-from-bottom-4"
      >
        {/* Top Mini Header */}
        <div className="flex items-center justify-between px-3.5 py-2 bg-black/50 border-b border-white/10 text-xs">
          <div className="flex items-center gap-2 min-w-0 mr-2">
            <Film className="w-3.5 h-3.5 text-[#EF4444] shrink-0" />
            <span className="font-semibold text-[11px] truncate text-slate-200">
              {videoTitle}
            </span>
          </div>

          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={() => onModeChange && onModeChange("theater")}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors cursor-pointer"
              title="Expand to Theater Mode"
            >
              <Maximize2 className="w-3.5 h-3.5" />
            </button>
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

        {/* Video Canvas */}
        <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden">
          {youtubeId ? (
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${youtubeId}?autoplay=1&rel=0&modestbranding=1&playsinline=1&enablejsapi=1`}
              title={videoTitle}
              className="w-full h-full border-0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              referrerPolicy="strict-origin-when-cross-origin"
              allowFullScreen
            />
          ) : isLocal && playableSrc ? (
            <video
              ref={videoRef}
              src={playableSrc}
              controls
              autoPlay
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="flex flex-col items-center gap-2 text-slate-400 p-4 text-center">
              <Loader2 className="w-6 h-6 animate-spin text-[#EF4444]" />
              <span className="text-xs">Loading YouTube player...</span>
            </div>
          )}
        </div>
      </div>
    );
  }

  // Theater Mode Modal
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
            <div className="w-9 h-9 rounded-2xl bg-[#EF4444]/20 border border-[#EF4444]/40 flex items-center justify-center shrink-0">
              <Film className="w-4 h-4 text-[#EF4444]" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm sm:text-base font-bold text-white truncate m-0">
                {videoTitle}
              </h2>
              <div className="flex items-center gap-2 text-xs text-slate-300 mt-0.5">
                <span className="truncate max-w-[200px] sm:max-w-xs">{videoUploader}</span>
                <span className="text-slate-500">•</span>
                <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold border bg-[#EF4444]/20 text-[#EF4444] border-[#EF4444]/40 inline-flex items-center gap-1.5">
                  <Film className="w-3 h-3 text-[#EF4444]" />
                  <span>{youtubeId ? "YouTube Embed Player" : "Local Video Player"}</span>
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30 inline-flex items-center gap-1" title="Ad-Shield Protection: Blocking ad trackers and popup overlays">
                  <ShieldCheck className="w-3 h-3 text-emerald-400" />
                  <span>Ad-Shield</span>
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Download Button */}
            {onDownload && (
              <button
                type="button"
                onClick={() => onDownload(video)}
                className="neu-raised px-3 py-1.5 rounded-xl text-xs font-semibold text-slate-300 hover:text-white hover:border-[#EF4444]/40 flex items-center gap-1.5 transition-all cursor-pointer"
                title="Download this video"
              >
                <Download className="w-3.5 h-3.5 text-[#EF4444]" />
                <span className="hidden sm:inline">Download</span>
              </button>
            )}

            {/* Switch to Floating Mini Player */}
            <button
              type="button"
              onClick={() => onModeChange && onModeChange("mini")}
              className="p-2 rounded-xl neu-raised text-slate-300 hover:text-[#EF4444] transition-all cursor-pointer"
              title="Picture-in-Picture Mini Player"
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

        {/* Video Canvas Container */}
        <div className="relative aspect-video w-full bg-black flex items-center justify-center overflow-hidden">
          {youtubeId ? (
            <iframe
              src={`https://www.youtube-nocookie.com/embed/${youtubeId}?autoplay=1&rel=0&modestbranding=1&playsinline=1&enablejsapi=1`}
              title={videoTitle}
              className="w-full h-full border-0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              referrerPolicy="strict-origin-when-cross-origin"
              allowFullScreen
            />
          ) : isLocal && playableSrc ? (
            <video
              ref={videoRef}
              src={playableSrc}
              controls
              autoPlay
              className="w-full h-full object-contain"
            />
          ) : isLoadingStream ? (
            <div className="flex flex-col items-center gap-3 text-slate-400 p-8 text-center">
              <Loader2 className="w-10 h-10 animate-spin text-[#EF4444]" />
              <div className="text-sm font-semibold text-white">Loading Video</div>
              <div className="text-xs text-slate-400 max-w-sm">
                Resolving video source...
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
              controls
              autoPlay
              className="w-full h-full object-contain"
            />
          ) : (
            <div className="text-sm text-slate-400">Video unavailable</div>
          )}
        </div>
      </div>
    </div>
  );
}
