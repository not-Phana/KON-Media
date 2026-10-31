import React, { useState, useEffect, useRef } from "react";
import {
  Music,
  Play,
  Pause,
  Heart,
  Download,
  ListMusic,
  Clock,
  FolderOpen,
  Loader2,
  CheckCircle2,
  AlertCircle,
  X,
  Volume2,
  Film,
  Sparkles,
  Mic2,
  Maximize2,
} from "lucide-react";
import { KonFlashIcon, KonPrecisionIcon } from "./KonIcons";

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

function formatBytes(bytes) {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

export default function RightSidebar({
  currentTrack,
  isPlaying,
  isLoadingAudio,
  onTogglePlay,
  onPlayCandidate,
  onToggleFavorite,
  isFavorite = false,
  onDirectDownload,
  playbackQueue = [],
  queueIndex = -1,
  onToggleQueue,
  activeTasks = [],
  onCancelTask,
  onOpenFile,
  lyricsData,
  isLoadingLyrics = false,
  lyricsError = null,
  onOpenFullscreenLyrics,
}) {
  const isFlash =
    currentTrack?.engine_mode === "flash" ||
    currentTrack?.model?.toLowerCase().includes("flash");

  // Active synced lyric line tracking - strictly isolated to avoid unnecessary re-renders
  const [activeLineIndex, setActiveLineIndex] = useState(-1);
  const lyricsContainerRef = useRef(null);
  const linesRef = useRef([]);
  linesRef.current = lyricsData?.lines || [];

  // Reset active line when track or lyrics payload changes
  useEffect(() => {
    setActiveLineIndex(-1);
  }, [lyricsData]);

  // Audio timeupdate listener: ONLY updates state when active lyric line actually changes
  useEffect(() => {
    let lastIndex = -1;

    const handleTime = (e) => {
      const cur = e.detail?.currentTime || 0;
      const lines = linesRef.current;
      if (!lines || lines.length === 0) return;

      let found = -1;
      for (let i = 0; i < lines.length; i++) {
        if (cur >= lines[i].time) {
          found = i;
        } else {
          break;
        }
      }

      if (found !== lastIndex) {
        lastIndex = found;
        setActiveLineIndex(found);
      }
    };

    window.addEventListener("kon_audio_timeupdate", handleTime);
    return () => window.removeEventListener("kon_audio_timeupdate", handleTime);
  }, []);

  const lines = lyricsData?.lines || [];
  const isSynced = lyricsData?.synced && lines.length > 0;

  // Smooth auto-scroll sidebar lyrics - ISOLATED to container, never shakes parent aside
  useEffect(() => {
    const container = lyricsContainerRef.current;
    if (!container || activeLineIndex < 0) return;

    const lineElements = container.querySelectorAll("[data-sidebar-lyric]");
    const activeEl = lineElements[activeLineIndex];
    if (activeEl) {
      const containerHeight = container.clientHeight;
      const elOffsetTop = activeEl.offsetTop;
      const elHeight = activeEl.clientHeight;
      const targetScroll = elOffsetTop - (containerHeight / 2) + (elHeight / 2);

      container.scrollTo({
        top: Math.max(0, targetScroll),
        behavior: "smooth",
      });
    }
  }, [activeLineIndex]);

  const handleLineClick = (lineTime) => {
    window.dispatchEvent(new CustomEvent("kon_audio_seek", { detail: { time: lineTime } }));
  };

  // Next up items in queue (excluding current)
  const upNextItems =
    playbackQueue.length > 0 && queueIndex >= 0
      ? playbackQueue.slice(queueIndex + 1, queueIndex + 4)
      : playbackQueue.slice(0, 3);

  // Active downloads in progress
  const inProgressTasks = activeTasks.filter((t) =>
    ["queued", "downloading", "processing", "verifying"].includes(t.status)
  );

  return (
    <aside
      className="hidden xl:flex flex-col w-72 2xl:w-80 shrink-0 space-y-4 select-none sticky top-5 self-start max-h-[calc(100vh-2.5rem)] overflow-y-auto pr-1 neu-custom-scrollbar"
      aria-label="Playback Spotlight & Queue Sidebar"
    >
      {/* 1. Now Playing Spotlight Card */}
      <div className="neu-card p-4 space-y-3.5 border border-slate-200/60 dark:border-slate-800">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#64748B] dark:text-[#94A3B8] flex items-center gap-1.5">
            <Volume2 className="w-3.5 h-3.5 text-[#0084FF]" />
            Now Playing Spotlight
          </span>

          {currentTrack && (
            <span
              className={`neu-recessed px-2 py-0.5 rounded text-[9px] font-bold flex items-center gap-1 ${
                isFlash ? "text-[#F59E0B]" : "text-[#0084FF]"
              }`}
            >
              {isFlash ? <KonFlashIcon className="w-2.5 h-2.5" /> : <KonPrecisionIcon className="w-2.5 h-2.5" />}
              <span>{isFlash ? "Flash" : "Rei"}</span>
            </span>
          )}
        </div>

        {currentTrack ? (
          <div className="space-y-3">
            {/* Artwork Spotlight with Living Equalizer Aura */}
            <div className="relative aspect-video rounded-xl neu-recessed overflow-hidden flex items-center justify-center p-1 group shadow-sm">
              {currentTrack.thumbnail ? (
                <img
                  src={currentTrack.thumbnail}
                  alt={currentTrack.title}
                  className="w-full h-full object-cover rounded-lg transition-transform duration-300 group-hover:scale-104"
                  referrerPolicy="no-referrer"
                />
              ) : (
                <div className="w-full h-full flex items-center justify-center bg-slate-200/50 dark:bg-slate-800/50 rounded-lg">
                  <Music className="w-8 h-8 text-[#0084FF]" />
                </div>
              )}

              {/* Sleek playing indicator badge in corner, keeping artwork clear */}
              {isPlaying && !isLoadingAudio && (
                <div className="absolute bottom-2 right-2 bg-slate-900/85 backdrop-blur-md px-2 py-1 rounded-md flex items-center gap-1 pointer-events-none border border-slate-700/60 shadow-md">
                  <span className="w-1 bg-[#0084FF] rounded-full equalizer-bar-1"></span>
                  <span className="w-1 bg-[#0084FF] rounded-full equalizer-bar-2"></span>
                  <span className="w-1 bg-[#0084FF] rounded-full equalizer-bar-3"></span>
                  <span className="w-1 bg-[#0084FF] rounded-full equalizer-bar-4"></span>
                </div>
              )}

              {isLoadingAudio && (
                <div className="absolute inset-0 bg-black/50 flex items-center justify-center rounded-lg">
                  <Loader2 className="w-6 h-6 text-[#0084FF] animate-spin" />
                </div>
              )}
            </div>

            {/* Song Metadata */}
            <div className="space-y-1">
              <h3
                className="text-xs font-bold text-[#1E293B] dark:text-[#F8FAFC] truncate m-0 leading-tight"
                title={currentTrack.title}
              >
                {currentTrack.title}
              </h3>
              <p
                className="text-[11px] text-[#64748B] dark:text-[#94A3B8] font-medium truncate m-0"
                title={currentTrack.artist || currentTrack.uploader}
              >
                {currentTrack.artist || currentTrack.uploader || "Unknown Artist"}
              </p>
            </div>

            {/* Quick Transport & Actions Row */}
            <div className="flex items-center justify-between gap-2 pt-1 border-t border-slate-200/60 dark:border-slate-800/60">
              <div className="flex items-center gap-1.5">
                {/* Play / Pause Toggle */}
                <button
                  type="button"
                  onClick={onTogglePlay}
                  className="neu-accent p-2 rounded-xl text-white cursor-pointer neu-btn-elastic"
                  title={isPlaying ? "Pause" : "Play"}
                >
                  {isPlaying ? (
                    <Pause className="w-4 h-4 fill-current" />
                  ) : (
                    <Play className="w-4 h-4 fill-current ml-0.5" />
                  )}
                </button>

                {/* Favorite Toggle */}
                <button
                  type="button"
                  onClick={onToggleFavorite}
                  className={`neu-raised p-2 rounded-xl text-xs cursor-pointer neu-btn-tactile ${
                    isFavorite ? "text-[#EF4444]" : "text-[#64748B] hover:text-[#EF4444]"
                  }`}
                  title={isFavorite ? "Remove from Favorites" : "Save to Favorites"}
                >
                  <Heart className={`w-4 h-4 ${isFavorite ? "fill-current" : ""}`} />
                </button>
              </div>

              {/* Direct Download Action */}
              {onDirectDownload && (
                <button
                  type="button"
                  onClick={() => onDirectDownload(currentTrack, "audio")}
                  className="neu-raised px-3 py-1.5 rounded-xl text-xs font-bold text-[#0084FF] hover:text-white hover:bg-[#0084FF] cursor-pointer neu-btn-tactile flex items-center gap-1.5"
                  title="Download song as MP3"
                >
                  <Download className="w-3.5 h-3.5" />
                  <span>Download</span>
                </button>
              )}
            </div>
          </div>
        ) : (
          <div className="neu-recessed p-5 rounded-xl text-center space-y-2">
            <Music className="w-6 h-6 text-[#94A3B8] mx-auto opacity-60" />
            <p className="text-xs font-medium text-[#64748B] dark:text-[#94A3B8] m-0">
              No track currently active.
            </p>
            <p className="text-[10px] text-[#94A3B8] m-0">
              Click Preview on any search result to listen before downloading.
            </p>
          </div>
        )}
      </div>

      {/* 2. LIVE SYNCHRONIZED LYRICS CARD (Easy to find, right under spotlight!) */}
      <div className="neu-card p-4 space-y-3 border border-slate-200/60 dark:border-slate-800">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#0084FF] flex items-center gap-1.5">
            <Mic2 className="w-3.5 h-3.5 text-[#0084FF]" />
            Live Lyrics
            {isSynced && (
              <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse ml-0.5" />
            )}
          </span>

          {currentTrack && onOpenFullscreenLyrics && (
            <button
              type="button"
              onClick={onOpenFullscreenLyrics}
              className="neu-raised px-2 py-1 rounded-lg text-[10px] font-bold text-[#0084FF] hover:text-white hover:bg-[#0084FF] transition-all cursor-pointer flex items-center gap-1 neu-btn-tactile"
              title="Expand Lyrics to Full Screen"
            >
              <Maximize2 className="w-3 h-3" />
              <span>Full Screen</span>
            </button>
          )}
        </div>

        {/* Lyrics Content Display */}
        {isLoadingLyrics ? (
          <div className="neu-recessed p-4 rounded-xl text-center space-y-2">
            <Loader2 className="w-4 h-4 text-[#0084FF] animate-spin mx-auto" />
            <p className="text-[11px] font-medium text-[#64748B] dark:text-[#94A3B8] m-0">
              Loading lyrics...
            </p>
          </div>
        ) : lyricsError ? (
          <div className="neu-recessed p-3.5 rounded-xl text-center">
            <p className="text-[11px] text-[#94A3B8] m-0">
              {lyricsError}
            </p>
          </div>
        ) : !currentTrack ? (
          <div className="neu-recessed p-3.5 rounded-xl text-center">
            <p className="text-[11px] text-[#94A3B8] m-0">
              Play a song to view live lyrics here.
            </p>
          </div>
        ) : isSynced ? (
          <div
            ref={lyricsContainerRef}
            className="relative neu-recessed p-2.5 rounded-xl max-h-48 overflow-y-auto space-y-1 neu-custom-scrollbar"
          >
            {lines.map((line, idx) => {
              const isActive = idx === activeLineIndex;
              return (
                <div
                  key={`${line.time}_${idx}`}
                  data-sidebar-lyric={idx}
                  onClick={() => handleLineClick(line.time)}
                  className={`text-xs rounded-lg px-2.5 py-1.5 transition-colors duration-150 cursor-pointer border ${
                    isActive
                      ? "neu-raised text-[#0084FF] font-bold border-[#0084FF]/30 bg-[#0084FF]/10 shadow-xs"
                      : "text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B] dark:hover:text-[#F8FAFC] font-medium border-transparent"
                  }`}
                  title={`Jump to ${formatDuration(line.time)}`}
                >
                  <p className="m-0 leading-snug truncate">
                    {line.text || "..."}
                  </p>
                </div>
              );
            })}
          </div>
        ) : lyricsData?.plain_lyrics ? (
          <div className="neu-recessed p-3 rounded-xl max-h-48 overflow-y-auto neu-custom-scrollbar">
            <span className="text-[9px] font-bold uppercase tracking-wider text-[#F59E0B] block mb-1">
              Unsynchronized
            </span>
            <p className="text-xs text-[#64748B] dark:text-[#94A3B8] whitespace-pre-line m-0 font-medium leading-relaxed">
              {lyricsData.plain_lyrics.slice(0, 400)}
              {lyricsData.plain_lyrics.length > 400 ? "..." : ""}
            </p>
          </div>
        ) : (
          <div className="neu-recessed p-3.5 rounded-xl text-center space-y-1">
            <p className="text-[11px] text-[#94A3B8] m-0">
              No lyrics found for this song.
            </p>
          </div>
        )}
      </div>

      {/* 3. Listening Queue Quick Peek */}
      <div className="neu-card p-4 space-y-3 border border-slate-200/60 dark:border-slate-800">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#64748B] dark:text-[#94A3B8] flex items-center gap-1.5">
            <ListMusic className="w-3.5 h-3.5 text-[#8B5CF6]" />
            Up Next Queue ({playbackQueue.length})
          </span>

          {playbackQueue.length > 0 && (
            <button
              type="button"
              onClick={onToggleQueue}
              className="text-[10px] text-[#8B5CF6] hover:underline font-bold cursor-pointer"
            >
              View All
            </button>
          )}
        </div>

        {upNextItems.length > 0 ? (
          <div className="space-y-1.5">
            {upNextItems.map((track, idx) => (
              <div
                key={track.id || `${track.url}_${idx}`}
                onClick={() => onPlayCandidate && onPlayCandidate(track)}
                className="p-2 rounded-xl neu-raised neu-card-hover flex items-center gap-2.5 cursor-pointer group transition-all"
                title={`Play next: ${track.title}`}
              >
                <div className="w-8 h-8 rounded-lg neu-recessed overflow-hidden shrink-0 relative flex items-center justify-center">
                  {track.thumbnail ? (
                    <img
                      src={track.thumbnail}
                      alt={track.title}
                      className="w-full h-full object-cover"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <Music className="w-4 h-4 text-[#8B5CF6]" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <h4 className="text-[11px] font-bold text-[#1E293B] dark:text-[#F8FAFC] truncate m-0">
                    {track.clean_title || track.title}
                  </h4>
                  <p className="text-[10px] text-[#64748B] dark:text-[#94A3B8] truncate m-0">
                    {track.artist || track.uploader || "Track"}
                  </p>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="neu-recessed p-3.5 rounded-xl text-center">
            <p className="text-[11px] text-[#94A3B8] m-0">
              Queue is empty. Songs you preview will queue up here.
            </p>
          </div>
        )}
      </div>

      {/* 4. Active Downloads Stream Widget */}
      <div className="neu-card p-4 space-y-3 border border-slate-200/60 dark:border-slate-800">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-black uppercase tracking-wider text-[#64748B] dark:text-[#94A3B8] flex items-center gap-1.5">
            <Download className="w-3.5 h-3.5 text-[#10B981]" />
            Downloads Stream
          </span>
          {inProgressTasks.length > 0 && (
            <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-[#10B981]/20 text-[#10B981] animate-pulse">
              {inProgressTasks.length} active
            </span>
          )}
        </div>

        {inProgressTasks.length > 0 ? (
          <div className="space-y-2">
            {inProgressTasks.slice(0, 3).map((task) => {
              const pct = Math.min(100, Math.max(0, Math.round(task.percentage || 0)));
              return (
                <div key={task.id} className="neu-recessed p-2.5 rounded-xl space-y-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[11px] font-bold text-[#1E293B] dark:text-[#F8FAFC] truncate flex-1">
                      {task.title}
                    </span>
                    <span className="text-[10px] font-mono font-bold text-[#0084FF] shrink-0">
                      {pct}%
                    </span>
                  </div>

                  {/* Progress bar */}
                  <div className="w-full h-1.5 bg-slate-300 dark:bg-slate-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-[#0084FF] transition-all duration-300 rounded-full"
                      style={{ width: `${pct}%` }}
                    />
                  </div>

                  <div className="flex items-center justify-between text-[9px] text-[#64748B] font-mono">
                    <span>{task.status}</span>
                    {task.speed > 0 && <span>{formatBytes(task.speed)}/s</span>}
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <div className="neu-recessed p-3.5 rounded-xl text-center">
            <p className="text-[11px] text-[#94A3B8] m-0">
              No active downloads. 1-click download any song from search.
            </p>
          </div>
        )}
      </div>
    </aside>
  );
}
