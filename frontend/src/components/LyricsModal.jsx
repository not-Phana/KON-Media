import React, { useEffect, useRef, useState } from "react";
import {
  X,
  Minimize2,
  Mic2,
  Music,
  Play,
  Pause,
  Volume2,
  VolumeX,
  Volume1,
  SkipBack,
  SkipForward,
  Loader2,
  AlertCircle,
  Sparkles,
} from "lucide-react";

function formatTime(seconds) {
  if (!seconds || isNaN(seconds) || seconds < 0) return "0:00";
  const s = Math.floor(seconds);
  const mins = Math.floor(s / 60);
  const secs = s % 60;
  return `${mins}:${secs < 10 ? "0" : ""}${secs}`;
}

export default function LyricsModal({
  isOpen,
  onClose,
  currentTrack,
  isPlaying,
  onTogglePlay,
  lyricsData,
  isLoadingLyrics,
  lyricsError,
}) {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [activeLineIndex, setActiveLineIndex] = useState(-1);
  const activeLineRef = useRef(null);
  const containerRef = useRef(null);
  const userScrolledRef = useRef(false);
  const userScrollTimeoutRef = useRef(null);

  // Listen to audio time updates from persistent player
  useEffect(() => {
    const handleTime = (e) => {
      const cur = e.detail?.currentTime || 0;
      const dur = e.detail?.duration || 0;
      setCurrentTime(cur);
      if (dur > 0) setDuration(dur);
    };

    window.addEventListener("kon_audio_timeupdate", handleTime);
    return () => window.removeEventListener("kon_audio_timeupdate", handleTime);
  }, []);

  // Keyboard shortcut: Escape to close
  useEffect(() => {
    if (!isOpen) return;
    const handleKey = (e) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.code === "Space" && e.target.tagName !== "INPUT") {
        e.preventDefault();
        if (onTogglePlay) onTogglePlay();
      }
    };
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [isOpen, onClose, onTogglePlay]);

  // Determine active line based on current time
  const lines = lyricsData?.lines || [];
  const isSynced = lyricsData?.synced && lines.length > 0;

  useEffect(() => {
    if (!isSynced || lines.length === 0) {
      setActiveLineIndex(-1);
      return;
    }

    let foundIdx = -1;
    for (let i = 0; i < lines.length; i++) {
      if (currentTime >= lines[i].time) {
        foundIdx = i;
      } else {
        break;
      }
    }

    setActiveLineIndex(foundIdx);
  }, [currentTime, lines, isSynced]);

  // Smooth auto-scroll to active line
  useEffect(() => {
    if (activeLineRef.current && containerRef.current && !userScrolledRef.current) {
      activeLineRef.current.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [activeLineIndex]);

  // Temporarily suspend auto-scroll if user manually scrolls, resume after 3.5s
  const handleScroll = () => {
    userScrolledRef.current = true;
    if (userScrollTimeoutRef.current) clearTimeout(userScrollTimeoutRef.current);
    userScrollTimeoutRef.current = setTimeout(() => {
      userScrolledRef.current = false;
    }, 3500);
  };

  const handleLineClick = (lineTime) => {
    window.dispatchEvent(new CustomEvent("kon_audio_seek", { detail: { time: lineTime } }));
    userScrolledRef.current = false;
  };

  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-[#090D14]/95 backdrop-blur-2xl text-[#F8FAFC] flex flex-col justify-between p-4 sm:p-8 md:p-10 select-none neu-popup-backdrop animate-in fade-in duration-200"
      role="dialog"
      aria-modal="true"
      aria-label="Full-screen Lyrics Theater"
    >
      {/* Ambient Radial Aura */}
      <div className="absolute inset-0 pointer-events-none overflow-hidden opacity-40">
        <div className="absolute -top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-to-b from-[#0084FF]/20 via-[#6366F1]/10 to-transparent blur-3xl rounded-full" />
      </div>

      {/* TOP BAR: Song Meta, Sync Badge & Close Controls */}
      <header className="relative z-10 flex items-center justify-between gap-4 pb-4 border-b border-slate-800/80">
        <div className="flex items-center gap-3.5 min-w-0">
          <div className="w-12 h-12 rounded-xl neu-recessed overflow-hidden shrink-0 flex items-center justify-center bg-slate-900 shadow-md">
            {currentTrack?.thumbnail ? (
              <img
                src={currentTrack.thumbnail}
                alt={currentTrack.title}
                className="w-full h-full object-cover"
                referrerPolicy="no-referrer"
              />
            ) : (
              <Music className="w-6 h-6 text-[#0084FF]" />
            )}
          </div>

          <div className="min-w-0">
            <h2 className="text-base sm:text-lg font-black text-[#F8FAFC] truncate m-0 leading-tight">
              {currentTrack?.clean_title || currentTrack?.title || "No Track Active"}
            </h2>
            <div className="flex items-center gap-2 mt-0.5">
              <p className="text-xs sm:text-sm text-[#94A3B8] font-medium truncate m-0">
                {currentTrack?.artist || currentTrack?.uploader || "Unknown Artist"}
              </p>
              {isSynced ? (
                <span className="neu-recessed px-2 py-0.5 rounded text-[10px] font-bold text-[#10B981] flex items-center gap-1 border border-[#10B981]/30">
                  <span className="w-1.5 h-1.5 rounded-full bg-[#10B981] animate-pulse" />
                  Synced
                </span>
              ) : lyricsData?.plain_lyrics ? (
                <span className="neu-recessed px-2 py-0.5 rounded text-[10px] font-bold text-[#F59E0B] border border-[#F59E0B]/30">
                  Plain Lyrics
                </span>
              ) : null}
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onClose}
            className="neu-raised p-2.5 rounded-xl text-[#94A3B8] hover:text-white cursor-pointer neu-btn-elastic group border border-slate-700/60"
            title="Exit Full-screen (Esc)"
          >
            <Minimize2 className="w-5 h-5 transition-transform duration-200 group-hover:scale-90" />
          </button>
          <button
            type="button"
            onClick={onClose}
            className="neu-raised p-2.5 rounded-xl text-[#94A3B8] hover:text-[#EF4444] cursor-pointer neu-btn-elastic group border border-slate-700/60"
            title="Close"
          >
            <X className="w-5 h-5 transition-transform duration-200 group-hover:rotate-90" />
          </button>
        </div>
      </header>

      {/* CENTER STAGE: LYRICS SCROLLER */}
      <main
        ref={containerRef}
        onScroll={handleScroll}
        className="relative z-10 flex-1 overflow-y-auto py-12 px-2 sm:px-8 space-y-6 neu-custom-scrollbar max-w-4xl mx-auto w-full text-center"
      >
        {isLoadingLyrics ? (
          <div className="h-full flex flex-col items-center justify-center space-y-3 py-20">
            <Loader2 className="w-8 h-8 text-[#0084FF] animate-spin" />
            <p className="text-sm font-semibold text-[#94A3B8]">
              Retrieving lyrics from LRCLIB...
            </p>
          </div>
        ) : lyricsError ? (
          <div className="h-full flex flex-col items-center justify-center space-y-3 py-20">
            <AlertCircle className="w-8 h-8 text-[#EF4444]" />
            <p className="text-sm font-semibold text-[#94A3B8] max-w-md">
              {lyricsError}
            </p>
          </div>
        ) : isSynced ? (
          <div className="space-y-4 py-8">
            {lines.map((line, idx) => {
              const isActive = idx === activeLineIndex;
              const isPast = idx < activeLineIndex;

              return (
                <div
                  key={`${line.time}_${idx}`}
                  ref={isActive ? activeLineRef : null}
                  onClick={() => handleLineClick(line.time)}
                  className={`transition-all duration-300 cursor-pointer rounded-2xl px-4 py-2.5 font-bold leading-relaxed tracking-tight ${
                    isActive
                      ? "text-2xl sm:text-3xl md:text-4xl text-[#38BDF8] scale-102 neu-recessed border border-[#0084FF]/40 bg-[#0084FF]/10 shadow-[0_0_24px_rgba(0,132,255,0.25)] font-black"
                      : isPast
                      ? "text-lg sm:text-xl md:text-2xl text-[#64748B] hover:text-[#CBD5E1]"
                      : "text-lg sm:text-xl md:text-2xl text-[#94A3B8] hover:text-[#F8FAFC]"
                  }`}
                  title={`Jump to ${formatTime(line.time)}`}
                >
                  <span className="block font-sans break-words">
                    {line.text || "..."}
                  </span>
                </div>
              );
            })}
          </div>
        ) : lyricsData?.plain_lyrics ? (
          <div className="py-8 space-y-3 text-left max-w-2xl mx-auto">
            <div className="neu-card p-6 rounded-2xl border border-slate-800 space-y-4">
              <span className="text-[11px] font-bold uppercase tracking-wider text-[#F59E0B] block">
                Unsynchronized Lyrics
              </span>
              <p className="text-base sm:text-lg text-[#CBD5E1] whitespace-pre-line leading-relaxed font-medium m-0 font-sans">
                {lyricsData.plain_lyrics}
              </p>
            </div>
          </div>
        ) : (
          <div className="h-full flex flex-col items-center justify-center space-y-3 py-20">
            <Mic2 className="w-10 h-10 text-[#64748B] opacity-50" />
            <p className="text-base font-bold text-[#CBD5E1]">
              No lyrics found for this song.
            </p>
            <p className="text-xs text-[#64748B]">
              Lyrics are queried from the open LRCLIB database by title and artist.
            </p>
          </div>
        )}
      </main>

      {/* BOTTOM COMPACT TRANSPORT BAR */}
      <footer className="relative z-10 pt-4 border-t border-slate-800/80 max-w-4xl mx-auto w-full space-y-2">
        {/* Scrubber row */}
        <div className="flex items-center gap-3 text-xs font-mono font-semibold text-[#94A3B8]">
          <span>{formatTime(currentTime)}</span>
          <div
            className="flex-1 h-2 bg-slate-800 rounded-full overflow-hidden cursor-pointer relative"
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const pct = (e.clientX - rect.left) / rect.width;
              const target = pct * (duration || 1);
              handleLineClick(target);
            }}
          >
            <div
              className="h-full bg-[#0084FF] transition-all duration-150 rounded-full"
              style={{ width: `${Math.min(100, Math.max(0, (currentTime / (duration || 1)) * 100))}%` }}
            />
          </div>
          <span>{formatTime(duration)}</span>
        </div>

        {/* Transport row & shortcuts hint */}
        <div className="flex items-center justify-between pt-1">
          <p className="text-[11px] text-[#64748B] m-0 hidden sm:block">
            Tip: Click any lyric line to jump to that moment · [Space] Play/Pause · [Esc] Close
          </p>

          <div className="flex items-center gap-3 mx-auto sm:mx-0">
            <button
              type="button"
              onClick={onTogglePlay}
              className="neu-accent p-2.5 rounded-xl text-white cursor-pointer neu-btn-elastic shadow-md"
              title={isPlaying ? "Pause (Space)" : "Play (Space)"}
            >
              {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
            </button>
          </div>
        </div>
      </footer>
    </div>
  );
}
