import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  Volume1,
  VolumeX,
  Shuffle,
  Repeat,
  Repeat1,
  Download,
  Loader2,
  AlertCircle,
  CheckCircle2,
  FolderOpen,
  X,
  Music,
} from "lucide-react";
import { KonFlashIcon, KonPrecisionIcon } from "./KonIcons";
import { getAudioStreamUrl } from "../api";

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
 * Persistent Bottom Music Player component (VLC-inspired controls).
 * Remains visible and continues playing across searches, query changes, and navigation.
 */
export default function BottomMusicPlayer({
  currentTrack,
  isPlaying,
  isLoading,
  error,
  playbackQueue = [],
  queueIndex = -1,
  onPlay,
  onPause,
  onTogglePlay,
  onNext,
  onPrevious,
  onClose,
  onDirectDownload,
  onOpenFile,
  activeTasks = [],
  history = [],
}) {
  const audioRef = useRef(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [bufferedPercent, setBufferedPercent] = useState(0);
  const [volume, setVolume] = useState(() => {
    try {
      const v = localStorage.getItem("kon_player_volume");
      return v !== null ? parseFloat(v) : 0.85;
    } catch {
      return 0.85;
    }
  });
  const [isMuted, setIsMuted] = useState(false);
  const [prevVolume, setPrevVolume] = useState(0.85);
  const [isShuffle, setIsShuffle] = useState(false);
  const [repeatMode, setRepeatMode] = useState("none"); // 'none' | 'all' | 'one'
  const [isSeeking, setIsSeeking] = useState(false);
  const [seekValue, setSeekValue] = useState(0);

  // Sync volume with audio element
  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = isMuted ? 0 : volume;
    }
  }, [volume, isMuted]);

  // Handle play/pause state synchronization
  useEffect(() => {
    const el = audioRef.current;
    if (!el || !currentTrack) return;

    if (isPlaying) {
      const playPromise = el.play();
      if (playPromise !== undefined) {
        playPromise.catch((err) => {
          // Ignore abort error caused by rapid track changes
          if (err.name !== "AbortError") {
            console.warn("Playback error:", err);
          }
        });
      }
    } else {
      el.pause();
    }
  }, [isPlaying, currentTrack]);

  // Audio event listeners
  const handleTimeUpdate = useCallback(() => {
    if (isSeeking || !audioRef.current) return;
    const cur = audioRef.current.currentTime || 0;
    setCurrentTime(cur);

    // Calculate buffer
    const el = audioRef.current;
    if (el.buffered.length > 0 && el.duration > 0) {
      const end = el.buffered.end(el.buffered.length - 1);
      setBufferedPercent(Math.min(100, (end / el.duration) * 100));
    }
  }, [isSeeking]);

  const handleLoadedMetadata = useCallback(() => {
    if (!audioRef.current) return;
    const dur = audioRef.current.duration;
    if (dur && !isNaN(dur) && dur > 0) {
      setDuration(dur);
    } else if (currentTrack?.duration) {
      setDuration(currentTrack.duration);
    }
  }, [currentTrack]);

  const handleEnded = useCallback(() => {
    if (repeatMode === "one") {
      if (audioRef.current) {
        audioRef.current.currentTime = 0;
        audioRef.current.play().catch(() => {});
      }
    } else if (onNext) {
      onNext({ shuffle: isShuffle, repeat: repeatMode });
    } else if (onPause) {
      onPause();
    }
  }, [repeatMode, onNext, isShuffle, onPause]);

  // Seek bar interaction
  const handleSeekChange = (e) => {
    const val = parseFloat(e.target.value);
    setSeekValue(val);
    setCurrentTime(val);
  };

  const handleSeekMouseDown = () => {
    setIsSeeking(true);
  };

  const handleSeekMouseUp = (e) => {
    const val = parseFloat(e.target.value);
    setIsSeeking(false);
    if (audioRef.current) {
      audioRef.current.currentTime = val;
      setCurrentTime(val);
    }
  };

  // Volume interaction
  const handleVolumeChange = (e) => {
    const val = parseFloat(e.target.value);
    setVolume(val);
    if (val > 0 && isMuted) {
      setIsMuted(false);
    }
    try {
      localStorage.setItem("kon_player_volume", String(val));
    } catch (_) {}
  };

  const toggleMute = () => {
    if (isMuted) {
      setIsMuted(false);
      setVolume(prevVolume || 0.85);
    } else {
      setPrevVolume(volume);
      setIsMuted(true);
    }
  };

  const cycleRepeatMode = () => {
    if (repeatMode === "none") setRepeatMode("all");
    else if (repeatMode === "all") setRepeatMode("one");
    else setRepeatMode("none");
  };

  // Check download status of the currently playing track
  const getTrackDownloadStatus = () => {
    if (!currentTrack) return { status: "idle" };

    // Check active tasks
    const activeTask = activeTasks.find(
      (t) =>
        t.url === currentTrack.url ||
        (currentTrack.id && t.url?.includes(currentTrack.id)) ||
        t.id === currentTrack.id
    );
    if (activeTask) {
      return {
        status: activeTask.status,
        percent: Math.min(100, Math.max(0, Math.round(activeTask.percentage || 0))),
        filePath: activeTask.file_path,
      };
    }

    // Check history
    const historyItem = history.find(
      (h) =>
        (h.url === currentTrack.url ||
          (currentTrack.id && h.url?.includes(currentTrack.id)) ||
          h.id === currentTrack.id) &&
        h.status === "completed"
    );
    if (historyItem || currentTrack.is_local) {
      return {
        status: "completed",
        percent: 100,
        filePath: historyItem?.file_path || currentTrack.file_path,
      };
    }

    return { status: "idle" };
  };

  if (!currentTrack) return null;

  const downloadStatus = getTrackDownloadStatus();
  const rawStreamUrl = currentTrack.stream_url || currentTrack.direct_url;
  const audioSrc = rawStreamUrl ? getAudioStreamUrl(rawStreamUrl) : "";
  const effectiveDuration = duration || currentTrack.duration || 0;
  const progressPercent =
    effectiveDuration > 0 ? Math.min(100, (currentTime / effectiveDuration) * 100) : 0;
  const isFlash =
    currentTrack.engine_mode === "flash" || currentTrack.model?.toLowerCase().includes("flash");

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-40 bg-white/95 dark:bg-[#0F172A]/95 backdrop-blur-md border-t border-slate-200/80 dark:border-slate-800 shadow-[0_-8px_25px_rgba(0,0,0,0.12)] transition-all animate-fade-in"
      role="region"
      aria-label="Persistent Audio Player"
    >
      {/* Hidden Native Audio Element */}
      {audioSrc && (
        <audio
          ref={audioRef}
          src={audioSrc}
          preload="auto"
          onTimeUpdate={handleTimeUpdate}
          onLoadedMetadata={handleLoadedMetadata}
          onEnded={handleEnded}
        />
      )}

      {/* Scrubber Progress Bar on top edge of the player */}
      <div className="relative w-full h-1.5 bg-slate-200/80 dark:bg-slate-800 cursor-pointer group">
        {/* Buffered Bar */}
        <div
          className="absolute inset-y-0 left-0 bg-slate-300 dark:bg-slate-700/60 transition-all duration-300"
          style={{ width: `${bufferedPercent}%` }}
        />
        {/* Playback Progress Fill */}
        <div
          className="absolute inset-y-0 left-0 bg-[#0084FF] transition-all duration-75"
          style={{ width: `${progressPercent}%` }}
        />
        {/* Interactive Range Input overlay */}
        <input
          type="range"
          min={0}
          max={effectiveDuration || 100}
          step={0.5}
          value={currentTime}
          onChange={handleSeekChange}
          onMouseDown={handleSeekMouseDown}
          onMouseUp={handleSeekMouseUp}
          onTouchStart={handleSeekMouseDown}
          onTouchEnd={handleSeekMouseUp}
          className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
          aria-label="Seek track position"
        />
      </div>

      <div className="max-w-7xl mx-auto px-4 py-2.5 flex items-center justify-between gap-4">
        {/* LEFT SECTION: Track Artwork & Metadata */}
        <div className="flex items-center gap-3.5 min-w-0 max-w-[280px] sm:max-w-[340px] md:max-w-[380px] shrink-0">
          {/* Thumbnail */}
          <div className="w-12 h-12 rounded-xl neu-recessed p-0.5 shrink-0 overflow-hidden flex items-center justify-center relative shadow-sm">
            {currentTrack.thumbnail ? (
              <img
                src={currentTrack.thumbnail}
                alt={currentTrack.title}
                className="w-full h-full object-cover rounded-lg"
                referrerPolicy="no-referrer"
                onError={(e) => {
                  e.currentTarget.style.display = "none";
                  const fallback = e.currentTarget.parentElement?.querySelector(".player-fallback");
                  if (fallback) fallback.classList.remove("hidden");
                }}
              />
            ) : null}
            <div
              className={`player-fallback w-full h-full flex items-center justify-center ${
                currentTrack.thumbnail ? "hidden" : ""
              }`}
            >
              <Music className="w-5 h-5 text-[#0084FF]" />
            </div>

            {/* Live Playing Soundwave Equalizer Indicator */}
            {isPlaying && (
              <div className="absolute inset-0 bg-black/40 backdrop-blur-[1px] flex items-center justify-center gap-0.5 rounded-lg pointer-events-none">
                <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:0ms] h-4"></span>
                <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:150ms] h-6"></span>
                <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:300ms] h-3"></span>
              </div>
            )}
          </div>

          {/* Title, Artist, & Engine Tag */}
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <h4
                className="text-xs sm:text-sm font-bold text-[#1E293B] dark:text-[#E2E8F0] truncate m-0"
                title={currentTrack.title}
              >
                {currentTrack.title || "Unknown Song"}
              </h4>

              {/* Engine Badge */}
              <span
                className={`neu-recessed px-1.5 py-0.5 rounded text-[9px] font-bold shrink-0 hidden sm:inline-flex items-center gap-1 ${
                  isFlash ? "text-[#F59E0B]" : "text-[#0084FF]"
                }`}
                title={isFlash ? "Ranked by Rei Flash (Speed)" : "Ranked by Rei (Precision)"}
              >
                {isFlash ? (
                  <KonFlashIcon className="w-2.5 h-2.5" />
                ) : (
                  <KonPrecisionIcon className="w-2.5 h-2.5" />
                )}
                <span>{isFlash ? "Flash" : "Rei"}</span>
              </span>
            </div>

            <p
              className="text-[11px] text-[#64748B] dark:text-[#94A3B8] truncate m-0 mt-0.5 font-medium"
              title={currentTrack.artist || currentTrack.uploader}
            >
              {currentTrack.artist || currentTrack.uploader || "Unknown Artist"}
              {currentTrack.is_local && (
                <span className="ml-1.5 text-[10px] text-[#10B981] font-semibold">
                  (Local File)
                </span>
              )}
            </p>
          </div>
        </div>

        {/* CENTER SECTION: VLC Transport Controls & Scrubber Timestamps */}
        <div className="flex flex-col items-center gap-1.5 flex-1 max-w-xl px-2">
          {/* Controls Row */}
          <div className="flex items-center gap-3 sm:gap-5">
            {/* Shuffle */}
            <button
              type="button"
              onClick={() => setIsShuffle((prev) => !prev)}
              className={`p-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                isShuffle
                  ? "text-[#0084FF] neu-recessed"
                  : "text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#E2E8F0]"
              }`}
              title={isShuffle ? "Shuffle on" : "Shuffle off"}
            >
              <Shuffle className="w-3.5 h-3.5" />
            </button>

            {/* Previous */}
            <button
              type="button"
              onClick={() => onPrevious && onPrevious({ shuffle: isShuffle })}
              disabled={!playbackQueue.length || queueIndex <= 0}
              className={`neu-raised p-2 rounded-xl text-[#334155] dark:text-[#CBD5E1] transition-all ${
                !playbackQueue.length || queueIndex <= 0
                  ? "opacity-40 cursor-not-allowed"
                  : "hover:text-[#0084FF] active:scale-95 cursor-pointer"
              }`}
              title="Previous song"
            >
              <SkipBack className="w-4 h-4" />
            </button>

            {/* Main Play / Pause / Loading Button */}
            <button
              type="button"
              onClick={onTogglePlay}
              disabled={isLoading}
              className="neu-accent w-10 h-10 sm:w-11 sm:h-11 rounded-2xl flex items-center justify-center text-white cursor-pointer active:scale-95 transition-all shadow-[0_4px_14px_rgba(0,132,255,0.35)]"
              title={isPlaying ? "Pause" : "Play"}
            >
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : isPlaying ? (
                <Pause className="w-5 h-5 fill-current" />
              ) : (
                <Play className="w-5 h-5 fill-current ml-0.5" />
              )}
            </button>

            {/* Next */}
            <button
              type="button"
              onClick={() => onNext && onNext({ shuffle: isShuffle, repeat: repeatMode })}
              disabled={!playbackQueue.length || queueIndex >= playbackQueue.length - 1}
              className={`neu-raised p-2 rounded-xl text-[#334155] dark:text-[#CBD5E1] transition-all ${
                !playbackQueue.length || queueIndex >= playbackQueue.length - 1
                  ? "opacity-40 cursor-not-allowed"
                  : "hover:text-[#0084FF] active:scale-95 cursor-pointer"
              }`}
              title="Next song"
            >
              <SkipForward className="w-4 h-4" />
            </button>

            {/* Repeat Mode */}
            <button
              type="button"
              onClick={cycleRepeatMode}
              className={`p-1.5 rounded-lg text-xs cursor-pointer transition-colors ${
                repeatMode !== "none"
                  ? "text-[#0084FF] neu-recessed"
                  : "text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#E2E8F0]"
              }`}
              title={`Repeat: ${repeatMode}`}
            >
              {repeatMode === "one" ? (
                <Repeat1 className="w-3.5 h-3.5" />
              ) : (
                <Repeat className="w-3.5 h-3.5" />
              )}
            </button>
          </div>

          {/* Time Displays */}
          <div className="flex items-center justify-between w-full text-[11px] font-mono font-semibold text-[#64748B] dark:text-[#94A3B8] px-1">
            <span>{formatTime(currentTime)}</span>
            {error ? (
              <span className="text-[#EF4444] text-[10px] font-sans font-semibold inline-flex items-center gap-1">
                <AlertCircle className="w-3 h-3" />
                <span>{error}</span>
              </span>
            ) : null}
            <span>{formatTime(effectiveDuration)}</span>
          </div>
        </div>

        {/* RIGHT SECTION: Volume Slider, Direct Download & Dismiss */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Volume Control */}
          <div className="hidden md:flex items-center gap-2">
            <button
              type="button"
              onClick={toggleMute}
              className="text-[#64748B] hover:text-[#0084FF] p-1.5 cursor-pointer rounded-lg transition-colors"
              title={isMuted ? "Unmute" : "Mute"}
            >
              {isMuted || volume === 0 ? (
                <VolumeX className="w-4 h-4 text-[#EF4444]" />
              ) : volume < 0.5 ? (
                <Volume1 className="w-4 h-4" />
              ) : (
                <Volume2 className="w-4 h-4" />
              )}
            </button>
            <input
              type="range"
              min={0}
              max={1}
              step={0.01}
              value={isMuted ? 0 : volume}
              onChange={handleVolumeChange}
              className="w-16 sm:w-20 h-1.5 accent-[#0084FF] cursor-pointer rounded-lg bg-slate-200 dark:bg-slate-700"
              aria-label="Volume slider"
            />
          </div>

          {/* Direct "Download Song" Action from Bottom Player */}
          {downloadStatus.status === "completed" ? (
            <button
              type="button"
              onClick={() =>
                downloadStatus.filePath && onOpenFile && onOpenFile(downloadStatus.filePath)
              }
              className="neu-recessed px-3 py-1.5 flex items-center gap-1.5 text-xs font-bold text-[#10B981] rounded-xl border border-[#10B981]/30 hover:bg-[#10B981]/10 transition-all cursor-pointer"
              title="Song downloaded! Click to open folder"
            >
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Downloaded</span>
              <FolderOpen className="w-3 h-3 ml-0.5 opacity-80" />
            </button>
          ) : downloadStatus.status === "downloading" ? (
            <div className="neu-recessed px-3 py-1.5 flex items-center gap-1.5 text-xs font-bold text-[#0084FF] rounded-xl border border-[#0084FF]/30 animate-pulse">
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              <span>{downloadStatus.percent}%</span>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => onDirectDownload && onDirectDownload(currentTrack, "audio")}
              className="neu-raised px-3 py-1.5 flex items-center gap-1.5 text-xs font-semibold text-[#0084FF] hover:text-white hover:bg-[#0084FF] rounded-xl transition-all cursor-pointer shadow-sm active:scale-95"
              title="Download this song as MP3"
            >
              <Download className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Download</span>
            </button>
          )}

          {/* Close Player */}
          <button
            type="button"
            onClick={onClose}
            className="neu-raised p-1.5 text-[#64748B] hover:text-[#EF4444] rounded-xl cursor-pointer transition-colors"
            title="Close audio player"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

