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
  ShieldCheck,
} from "lucide-react";
import { resolveVideoStream, getVideoStreamUrl, getAudioStreamUrl } from "../api";

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

function extractYouTubeId(video) {
  if (!video) return null;
  if (video.id && /^[a-zA-Z0-9_-]{11}$/.test(video.id)) {
    return video.id;
  }
  const url = video.webpage_url || video.url || "";
  const match = url.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?v=|embed\/|v\/|shorts\/))([a-zA-Z0-9_-]{11})/);
  if (match) return match[1];
  if (video.candidate_id && /^[a-zA-Z0-9_-]{11}$/.test(video.candidate_id)) {
    return video.candidate_id;
  }
  return null;
}

const PLAYBACK_SPEEDS = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0];

/**
 * KON Media Native Ad-Free Video Player Modal.
 * Supports Theater Modal Mode and Floating Mini-Player (Picture-in-Picture) Mode.
 * 100% Ad-Free native HTML5 playback with synchronized high-bitrate stereo audio.
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
  const audioRef = useRef(null);
  const containerRef = useRef(null);
  const progressBarRef = useRef(null);
  const hideControlsTimeoutRef = useRef(null);

  // Playback state
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [bufferedEnd, setBufferedEnd] = useState(0);
  const [volume, setVolume] = useState(() => {
    try {
      const v = localStorage.getItem("kon_video_volume");
      return v !== null ? parseFloat(v) : 0.85;
    } catch {
      return 0.85;
    }
  });
  const [isMuted, setIsMuted] = useState(false);
  const [playbackRate, setPlaybackRate] = useState(1.0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [areControlsVisible, setAreControlsVisible] = useState(true);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);

  // Stream resolution & playback engine state
  const [isLoadingStream, setIsLoadingStream] = useState(true);
  const [streamError, setStreamError] = useState(null);
  const [resolvedInfo, setResolvedInfo] = useState(null);

  // Hover timestamp preview
  const [hoverTime, setHoverTime] = useState(null);
  const [hoverPosition, setHoverPosition] = useState(0);

  // Player engine state (Ad-Free Embed vs Native Player)
  const youtubeId = extractYouTubeId(video);
  const isLocal = !!(resolvedInfo?.is_local || video?.is_local);

  const [playerEngine, setPlayerEngine] = useState(() => {
    try {
      const saved = localStorage.getItem("kon_video_player_engine");
      if (saved) return saved;
    } catch (_) {}
    return "embed";
  });

  const handleEngineChange = (engine) => {
    setPlayerEngine(engine);
    try {
      localStorage.setItem("kon_video_player_engine", engine);
    } catch (_) {}
  };

  const effectiveEngine = (youtubeId && !isLocal) ? playerEngine : "native";

  // Save volume preference
  useEffect(() => {
    try {
      localStorage.setItem("kon_video_volume", String(volume));
    } catch (_) {}
  }, [volume]);

  // Resolve video & audio streams whenever the video prop changes
  useEffect(() => {
    if (!video || !isOpen) return;

    let isMounted = true;
    const abortController = new AbortController();

    // If stream URL is already resolved and matches this video
    if (video.stream_url) {
      setResolvedInfo({
        stream_url: video.stream_url,
        audio_stream_url: video.audio_stream_url || null,
        title: video.title,
        uploader: video.uploader || video.artist,
        is_local: !!video.is_local,
        resolution: video.resolution || (video.is_local ? "Local Video" : "Direct Stream"),
      });
      setIsLoadingStream(false);
      setStreamError(null);
      return;
    }

    setIsLoadingStream(true);
    setStreamError(null);

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
        }));
        setIsLoadingStream(false);
      } catch (err) {
        if (!isMounted || err.name === "AbortError") return;
        setStreamError(err.message || "Unable to resolve playable video stream");
        setIsLoadingStream(false);
      }
    }

    resolve();

    return () => {
      isMounted = false;
      abortController.abort();
    };
  }, [video, isOpen]);

  // Synchronize audio element with video element volume
  const currentAudioRaw = resolvedInfo?.audio_stream_url || video?.audio_stream_url;
  const audioStreamSrc = currentAudioRaw ? getAudioStreamUrl(currentAudioRaw) : null;

  useEffect(() => {
    if (videoRef.current) {
      if (audioStreamSrc) {
        // Mute video element when separate high-fidelity audio stream is active to prevent echo
        videoRef.current.muted = true;
      } else {
        videoRef.current.volume = isMuted ? 0 : volume;
        videoRef.current.muted = isMuted;
      }
    }
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : volume;
      audioRef.current.muted = isMuted;
    }
  }, [volume, isMuted, audioStreamSrc]);

  // Synchronize playback speed
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackRate;
    }
    if (audioRef.current) {
      audioRef.current.playbackRate = playbackRate;
    }
  }, [playbackRate]);

  // Auto-hide controls in theater mode during active playback
  const resetHideTimer = useCallback(() => {
    setAreControlsVisible(true);
    if (hideControlsTimeoutRef.current) {
      clearTimeout(hideControlsTimeoutRef.current);
    }
    if (isPlaying && mode === "theater") {
      hideControlsTimeoutRef.current = setTimeout(() => {
        setAreControlsVisible(false);
        setShowSpeedMenu(false);
      }, 3500);
    }
  }, [isPlaying, mode]);

  useEffect(() => {
    resetHideTimer();
    return () => {
      if (hideControlsTimeoutRef.current) {
        clearTimeout(hideControlsTimeoutRef.current);
      }
    };
  }, [isPlaying, resetHideTimer]);

  // Transport toggle
  const togglePlay = () => {
    const v = videoRef.current;
    const a = audioRef.current;
    if (!v) return;

    if (v.paused) {
      const p = v.play();
      if (p !== undefined) {
        p.then(() => {
          setIsPlaying(true);
          if (onPauseAudio) onPauseAudio();
          if (a) {
            a.currentTime = v.currentTime;
            a.play().catch(() => {});
          }
        }).catch((err) => {
          console.warn("Video play error:", err);
        });
      }
    } else {
      v.pause();
      if (a) a.pause();
      setIsPlaying(false);
    }
  };

  // Video event handlers
  const handleTimeUpdate = () => {
    const v = videoRef.current;
    if (!v) return;
    const cur = v.currentTime || 0;
    setCurrentTime(cur);

    // Keep synchronized audio track strictly aligned (drift tolerance 150ms)
    const a = audioRef.current;
    if (a && !v.paused) {
      const drift = Math.abs(cur - a.currentTime);
      if (drift > 0.15) {
        a.currentTime = cur;
      }
      if (a.paused) {
        a.play().catch(() => {});
      }
    }

    if (v.buffered.length > 0) {
      try {
        const end = v.buffered.end(v.buffered.length - 1);
        setBufferedEnd(end);
      } catch (_) {}
    }
  };

  const handleLoadedMetadata = () => {
    const v = videoRef.current;
    if (!v) return;
    if (v.duration && !isNaN(v.duration)) {
      setDuration(v.duration);
    }
    // Attempt auto-play when modal opens
    v.play()
      .then(() => {
        setIsPlaying(true);
        if (onPauseAudio) onPauseAudio();
        if (audioRef.current) {
          audioRef.current.currentTime = 0;
          audioRef.current.play().catch(() => {});
        }
      })
      .catch(() => {
        setIsPlaying(false);
      });
  };

  const handleWaiting = () => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
  };

  const handlePlaying = () => {
    setIsPlaying(true);
    if (audioRef.current && audioRef.current.paused) {
      audioRef.current.currentTime = videoRef.current?.currentTime || 0;
      audioRef.current.play().catch(() => {});
    }
  };

  const handleVideoEnded = () => {
    setIsPlaying(false);
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
  };

  const handleVideoPause = () => {
    setIsPlaying(false);
    if (audioRef.current) {
      audioRef.current.pause();
    }
  };

  // Seek interaction
  const handleSeekClick = (e) => {
    const rect = progressBarRef.current?.getBoundingClientRect();
    if (!rect || duration <= 0) return;
    const clickX = e.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, clickX / rect.width));
    const target = pct * duration;

    if (videoRef.current) {
      videoRef.current.currentTime = target;
      setCurrentTime(target);
    }
    if (audioRef.current) {
      audioRef.current.currentTime = target;
    }
  };

  const handleSeekMouseMove = (e) => {
    const rect = progressBarRef.current?.getBoundingClientRect();
    if (!rect || duration <= 0) return;
    const x = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const pct = x / rect.width;
    setHoverPosition(x);
    setHoverTime(pct * duration);
  };

  const handleSeekMouseLeave = () => {
    setHoverTime(null);
  };

  // Jump forward / backward
  const handleSkip = (seconds) => {
    const v = videoRef.current;
    if (!v) return;
    const target = Math.max(0, Math.min(duration || 9999, (v.currentTime || 0) + seconds));
    v.currentTime = target;
    setCurrentTime(target);
    if (audioRef.current) {
      audioRef.current.currentTime = target;
    }
  };

  // Volume interaction
  const handleVolumeChange = (e) => {
    const val = parseFloat(e.target.value);
    setVolume(val);
    if (val > 0 && isMuted) {
      setIsMuted(false);
    }
  };

  const toggleMute = () => {
    setIsMuted((prev) => !prev);
  };

  // Fullscreen toggle
  const toggleFullscreen = () => {
    const elem = containerRef.current;
    if (!elem) return;

    if (!document.fullscreenElement) {
      elem.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  };

  useEffect(() => {
    const handleFsChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };
    document.addEventListener("fullscreenchange", handleFsChange);
    return () => document.removeEventListener("fullscreenchange", handleFsChange);
  }, []);

  // Keyboard shortcut navigation
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      // Don't capture when typing in an input or textarea
      if (["INPUT", "TEXTAREA"].includes(document.activeElement?.tagName)) return;

      switch (e.key) {
        case " ":
        case "k":
          e.preventDefault();
          togglePlay();
          break;
        case "ArrowLeft":
          e.preventDefault();
          handleSkip(-5);
          break;
        case "ArrowRight":
          e.preventDefault();
          handleSkip(5);
          break;
        case "j":
          e.preventDefault();
          handleSkip(-10);
          break;
        case "l":
          e.preventDefault();
          handleSkip(10);
          break;
        case "f":
          e.preventDefault();
          toggleFullscreen();
          break;
        case "m":
          e.preventDefault();
          toggleMute();
          break;
        case "Escape":
          if (isFullscreen) {
            document.exitFullscreen().catch(() => {});
          } else {
            onClose();
          }
          break;
        default:
          break;
      }
      resetHideTimer();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, isFullscreen, duration, resetHideTimer]);

  if (!isOpen || !video) return null;

  const currentStreamRaw = resolvedInfo?.stream_url || video?.stream_url;
  const playableSrc = currentStreamRaw ? getVideoStreamUrl(currentStreamRaw) : null;
  const videoTitle = resolvedInfo?.title || video.title || "Video";
  const videoUploader = resolvedInfo?.uploader || video.uploader || video.artist || "Unknown Creator";
  const resolution = resolvedInfo?.resolution || video.resolution || (isLocal ? "Local File" : "1080p Full HD");

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
          {effectiveEngine === "embed" && youtubeId ? (
            <iframe
              src={`https://piped.video/embed/${youtubeId}?autoplay=1`}
              title={videoTitle}
              className="w-full h-full border-0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
            />
          ) : isLoadingStream ? (
            <div className="flex flex-col items-center gap-2 text-slate-400 p-4 text-center">
              <Loader2 className="w-7 h-7 animate-spin text-[#0084FF]" />
              <span className="text-xs font-medium">Connecting ad-free stream...</span>
            </div>
          ) : streamError ? (
            <div className="flex flex-col items-center gap-2 text-[#EF4444] p-4 text-center">
              <AlertCircle className="w-6 h-6" />
              <span className="text-xs font-semibold">{streamError}</span>
            </div>
          ) : playableSrc ? (
            <>
              <video
                ref={videoRef}
                src={playableSrc}
                playsInline
                crossOrigin="anonymous"
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
                onWaiting={handleWaiting}
                onPlaying={handlePlaying}
                onPause={handleVideoPause}
                onEnded={handleVideoEnded}
                onClick={togglePlay}
                className="w-full h-full object-contain cursor-pointer"
              />
              {audioStreamSrc && (
                <audio
                  ref={audioRef}
                  src={audioStreamSrc}
                  preload="auto"
                />
              )}
            </>
          ) : (
            <div className="text-xs text-slate-400">Stream unavailable</div>
          )}

          {/* Mini Play/Pause overlay */}
          {!isLoadingStream && !streamError && playableSrc && (
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

          {/* Mini Scrub bar at bottom of video */}
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
        </div>

        {/* Mini Bottom Controls Bar */}
        <div className="flex items-center justify-between px-3 py-2 bg-black/60 text-xs text-slate-300">
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={togglePlay}
              className="p-1 rounded-md text-slate-200 hover:text-white cursor-pointer"
            >
              {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current" />}
            </button>
            <span className="text-[11px] font-mono text-slate-400">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-[9px] px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 flex items-center gap-1">
              <ShieldCheck className="w-2.5 h-2.5 text-emerald-400" />
              <span>Ad-Free</span>
            </span>
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
                <span className="truncate max-w-[200px] sm:max-w-xs">{videoUploader}</span>
                <span className="text-slate-500">•</span>
                <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${
                  isLocal
                    ? "bg-emerald-500/20 text-emerald-400 border-emerald-500/30"
                    : "bg-[#0084FF]/20 text-[#0084FF] border-[#0084FF]/30"
                }`}>
                  {resolution}
                </span>
                <span className="px-2 py-0.5 rounded-full text-[10px] font-bold border bg-emerald-500/20 text-emerald-400 border-emerald-500/30 hidden sm:inline-flex items-center gap-1">
                  <ShieldCheck className="w-3 h-3 text-emerald-400" />
                  <span>100% Ad-Free</span>
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {/* Engine Switcher */}
            {youtubeId && !isLocal && (
              <div className="hidden sm:flex items-center gap-1 neu-recessed p-1 rounded-xl text-xs mr-1">
                <button
                  type="button"
                  onClick={() => handleEngineChange("embed")}
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    effectiveEngine === "embed"
                      ? "neu-raised text-[#0084FF] border border-[#0084FF]/30 bg-[#0084FF]/10 shadow-xs"
                      : "text-slate-400 hover:text-white"
                  }`}
                  title="Ad-Free YouTube Embed Player: 4K/1080p, captions, zero ads"
                >
                  Ad-Free Embed
                </button>
                <button
                  type="button"
                  onClick={() => handleEngineChange("native")}
                  className={`px-2.5 py-1 rounded-lg text-xs font-bold transition-all cursor-pointer ${
                    effectiveEngine === "native"
                      ? "neu-raised text-[#10B981] border border-[#10B981]/30 bg-[#10B981]/10 shadow-xs"
                      : "text-slate-400 hover:text-white"
                  }`}
                  title="Native In-App Player: Direct stream"
                >
                  Native Player
                </button>
              </div>
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

        {/* High-Resolution Video Player Canvas */}
        <div className="relative aspect-video w-full bg-black flex items-center justify-center overflow-hidden">
          {effectiveEngine === "embed" && youtubeId ? (
            <iframe
              src={`https://piped.video/embed/${youtubeId}?autoplay=1`}
              title={videoTitle}
              className="w-full h-full border-0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
            />
          ) : isLoadingStream ? (
            <div className="flex flex-col items-center gap-3 text-slate-400 p-8 text-center">
              <Loader2 className="w-10 h-10 animate-spin text-[#0084FF]" />
              <div className="text-sm font-semibold text-white">Connecting Ad-Free Video Stream</div>
              <div className="text-xs text-slate-400 max-w-sm">
                Resolving direct high-bitrate video and stereo audio tracks...
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
            <>
              <video
                ref={videoRef}
                src={playableSrc}
                playsInline
                crossOrigin="anonymous"
                onTimeUpdate={handleTimeUpdate}
                onLoadedMetadata={handleLoadedMetadata}
                onWaiting={handleWaiting}
                onPlaying={handlePlaying}
                onPause={handleVideoPause}
                onEnded={handleVideoEnded}
                onClick={togglePlay}
                className="w-full h-full object-contain cursor-pointer"
              />
              {audioStreamSrc && (
                <audio
                  ref={audioRef}
                  src={audioStreamSrc}
                  preload="auto"
                />
              )}
            </>
          ) : (
            <div className="text-sm text-slate-400">Stream unavailable</div>
          )}

          {/* Big Center Play/Pause Indicator on click / pause */}
          {!isLoadingStream && !streamError && playableSrc && !isPlaying && (
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

        {/* Bottom Control Bar Overlay */}
        {effectiveEngine === "native" && (
        <div
          className={`absolute bottom-0 left-0 right-0 z-30 p-4 sm:p-5 bg-gradient-to-t from-black/95 via-black/70 to-transparent transition-opacity duration-300 flex flex-col gap-3 ${
            areControlsVisible ? "opacity-100" : "opacity-0 pointer-events-none"
          }`}
        >
          {/* Progress / Scrubber Bar with Hover Tooltip */}
          <div
            ref={progressBarRef}
            onClick={handleSeekClick}
            onMouseMove={handleSeekMouseMove}
            onMouseLeave={handleSeekMouseLeave}
            className="relative w-full h-2 hover:h-3 bg-white/20 rounded-full cursor-pointer transition-all duration-200 group/bar select-none"
          >
            {/* Hover Tooltip */}
            {hoverTime !== null && duration > 0 && (
              <div
                className="absolute -top-7 neu-recessed px-1.5 py-0.5 rounded text-[10px] font-mono font-bold text-white shadow-md pointer-events-none transform -translate-x-1/2 z-20 bg-slate-900 border border-slate-700"
                style={{ left: `${hoverPosition}px` }}
              >
                {formatTime(hoverTime)}
              </div>
            )}

            {/* Buffer progress bar */}
            <div
              className="absolute top-0 bottom-0 left-0 bg-white/30 rounded-full transition-all duration-150"
              style={{ width: `${bufferPercent}%` }}
            />

            {/* Current play progress bar */}
            <div
              className="absolute top-0 bottom-0 left-0 bg-[#0084FF] rounded-full shadow-[0_0_12px_rgba(0,132,255,0.8)]"
              style={{ width: `${progressPercent}%` }}
            />

            {/* Scrubber thumb handle */}
            <div
              className="absolute top-1/2 -translate-y-1/2 -ml-2 w-4 h-4 bg-white rounded-full shadow-[0_0_10px_rgba(0,132,255,0.8)] opacity-0 group-hover/bar:opacity-100 transition-opacity pointer-events-none"
              style={{ left: `${progressPercent}%` }}
            />
          </div>

          {/* Controls Lower Row */}
          <div className="flex items-center justify-between text-white text-xs">
            {/* Left Section: Play/Pause, Replay/Skip, Timestamps */}
            <div className="flex items-center gap-3 sm:gap-4">
              <button
                type="button"
                onClick={togglePlay}
                className="p-1.5 rounded-xl neu-raised text-white hover:text-[#0084FF] hover:border-[#0084FF]/40 cursor-pointer transition-all"
                title={isPlaying ? "Pause (Space/k)" : "Play (Space/k)"}
              >
                {isPlaying ? <Pause className="w-5 h-5 fill-current" /> : <Play className="w-5 h-5 fill-current ml-0.5" />}
              </button>

              <button
                type="button"
                onClick={() => handleSkip(-10)}
                className="p-1 text-slate-300 hover:text-white transition-colors cursor-pointer"
                title="Rewind 10s (j / Left Arrow)"
              >
                <RotateCcw className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={() => handleSkip(10)}
                className="p-1 text-slate-300 hover:text-white transition-colors cursor-pointer"
                title="Forward 10s (l / Right Arrow)"
              >
                <RotateCw className="w-4 h-4" />
              </button>

              {/* Volume Slider & Mute Toggle */}
              <div className="flex items-center gap-2 group/vol">
                <button
                  type="button"
                  onClick={toggleMute}
                  className="p-1 text-slate-300 hover:text-white transition-colors cursor-pointer"
                  title={isMuted ? "Unmute (m)" : "Mute (m)"}
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
                  step="0.05"
                  value={isMuted ? 0 : volume}
                  onChange={handleVolumeChange}
                  className="w-16 sm:w-20 h-1.5 bg-white/20 rounded-lg appearance-none cursor-pointer accent-[#0084FF]"
                  title={`Volume: ${Math.round((isMuted ? 0 : volume) * 100)}%`}
                />
              </div>

              {/* Timestamp */}
              <span className="font-mono text-xs text-slate-300 select-none hidden sm:inline-block">
                {formatTime(currentTime)} / {formatTime(duration)}
              </span>
            </div>

            {/* Right Section: Speed, Picture-in-Picture, Fullscreen */}
            <div className="flex items-center gap-2 sm:gap-3">
              {/* Playback Speed Menu */}
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowSpeedMenu((prev) => !prev)}
                  className="neu-raised px-2.5 py-1 rounded-xl text-xs font-semibold text-slate-300 hover:text-white flex items-center gap-1 transition-colors cursor-pointer"
                  title="Playback Speed"
                >
                  <span>{playbackRate}x</span>
                  <ChevronDown className="w-3 h-3" />
                </button>

                {showSpeedMenu && (
                  <div className="absolute bottom-full right-0 mb-2 w-24 py-1 rounded-xl neu-card shadow-2xl bg-[#0F172A] border border-white/10 text-xs z-50 animate-in fade-in">
                    {PLAYBACK_SPEEDS.map((speed) => (
                      <button
                        key={speed}
                        type="button"
                        onClick={() => {
                          setPlaybackRate(speed);
                          setShowSpeedMenu(false);
                        }}
                        className={`w-full px-3 py-1.5 text-left cursor-pointer transition-colors ${
                          playbackRate === speed
                            ? "text-[#0084FF] font-bold bg-[#0084FF]/10"
                            : "text-slate-300 hover:bg-white/10 hover:text-white"
                        }`}
                      >
                        {speed}x
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Fullscreen Button */}
              <button
                type="button"
                onClick={toggleFullscreen}
                className="p-1.5 rounded-xl neu-raised text-slate-300 hover:text-white transition-colors cursor-pointer"
                title={isFullscreen ? "Exit Fullscreen (f)" : "Fullscreen (f)"}
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
