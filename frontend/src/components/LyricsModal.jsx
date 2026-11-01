import React, { useEffect, useRef, useState, useCallback } from "react";
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
  Search,
  RotateCcw,
  ArrowDown,
  ArrowUp,
  Target,
} from "lucide-react";
import { fetchLyrics, saveLyricsOffset } from "../api";

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
  lyricsData: initialLyricsData,
  isLoadingLyrics: initialLoading,
  lyricsError: initialError,
  glassMode = false,
}) {
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [syncOffset, setSyncOffset] = useState(0);
  const [activeLineIndex, setActiveLineIndex] = useState(-1);

  // Load saved timing offset for current track
  useEffect(() => {
    if (!currentTrack?.id && !currentTrack?.url) {
      setSyncOffset(0);
      return;
    }
    const key = `kon_lyric_offset_${currentTrack.id || currentTrack.url}`;
    try {
      const saved = parseFloat(localStorage.getItem(key) || "0") || 0;
      setSyncOffset(saved);
    } catch (_) {
      setSyncOffset(0);
    }
  }, [currentTrack]);

  const handleSetOffset = (newOffset) => {
    const rounded = Math.round(newOffset * 10) / 10;
    setSyncOffset(rounded);
    const key = `kon_lyric_offset_${currentTrack?.id || currentTrack?.url}`;
    try {
      if (key) localStorage.setItem(key, String(rounded));
    } catch (_) {}
    if (currentTrack) {
      saveLyricsOffset({
        title: currentTrack.song_title || currentTrack.clean_title || currentTrack.title,
        artist: currentTrack.artist || currentTrack.uploader || "",
        offset: rounded,
        filePath: currentTrack.file_path,
      });
    }
  };

  const handleAdjustOffset = (delta) => {
    handleSetOffset(syncOffset + delta);
  };

  const handleSyncLineToNow = (line) => {
    if (!line) return;
    const delta = currentTime - line.time;
    handleSetOffset(delta);
  };
  const containerRef = useRef(null);
  const userScrolledRef = useRef(false);
  const isProgrammaticScrollRef = useRef(false);
  const userScrollTimeoutRef = useRef(null);
  const animFrameIdRef = useRef(null);
  const [isScrolledAway, setIsScrolledAway] = useState(false);
  const [scrollDirection, setScrollDirection] = useState("down");

  // Local override state for instant in-modal search & retries
  const [lyricsData, setLyricsData] = useState(initialLyricsData);
  const [isLoading, setIsLoading] = useState(initialLoading);
  const [errorMsg, setErrorMsg] = useState(initialError);
  const [searchQuery, setSearchQuery] = useState("");
  const [isSearchingManually, setIsSearchingManually] = useState(false);

  // Sync with prop updates
  useEffect(() => {
    setLyricsData(initialLyricsData);
    if (initialLyricsData?.found) {
      setErrorMsg(null);
    }
  }, [initialLyricsData]);

  useEffect(() => {
    setIsLoading(initialLoading);
  }, [initialLoading]);

  useEffect(() => {
    setErrorMsg(initialError);
  }, [initialError]);

  // Sync state whenever modal is opened
  useEffect(() => {
    if (isOpen) {
      setLyricsData(initialLyricsData);
      setIsLoading(initialLoading);
      setErrorMsg(initialLyricsData?.found ? null : initialError);
    }
  }, [isOpen, initialLyricsData, initialLoading, initialError]);

  useEffect(() => {
    if (currentTrack) {
      const defaultQ = `${currentTrack.clean_title || currentTrack.title || ""} ${currentTrack.artist || currentTrack.uploader || ""}`.trim();
      setSearchQuery(defaultQ);
    }
  }, [currentTrack]);

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

    const effectiveTime = Math.max(0, currentTime - syncOffset);
    let foundIdx = -1;
    for (let i = 0; i < lines.length; i++) {
      if (effectiveTime >= lines[i].time) {
        foundIdx = i;
      } else {
        break;
      }
    }

    setActiveLineIndex(foundIdx);
  }, [currentTime, syncOffset, lines, isSynced]);

  // Smooth glide to the currently active lyric line
  const scrollToActiveLine = useCallback(() => {
    userScrolledRef.current = false;
    isProgrammaticScrollRef.current = true;
    setIsScrolledAway(false);
    if (userScrollTimeoutRef.current) clearTimeout(userScrollTimeoutRef.current);

    const container = containerRef.current;
    if (!container || activeLineIndex < 0) {
      isProgrammaticScrollRef.current = false;
      return;
    }

    const lineElements = container.querySelectorAll("[data-theater-line]");
    const activeEl = lineElements[activeLineIndex];
    if (!activeEl) {
      isProgrammaticScrollRef.current = false;
      return;
    }

    const containerHeight = container.clientHeight;
    const elOffsetTop = activeEl.offsetTop;
    const elHeight = activeEl.clientHeight;
    const targetScroll = Math.max(0, elOffsetTop - (containerHeight / 2) + (elHeight / 2));

    if (animFrameIdRef.current) {
      cancelAnimationFrame(animFrameIdRef.current);
    }

    const startY = container.scrollTop;
    const distance = targetScroll - startY;

    if (Math.abs(distance) < 2) {
      isProgrammaticScrollRef.current = false;
      return;
    }

    const duration = 750; // 750ms gentle, slow cinematic glide
    const startTime = performance.now();
    const easeOutCubic = (t) => 1 - Math.pow(1 - t, 3);

    const step = (now) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOutCubic(progress);

      container.scrollTop = startY + distance * eased;

      if (progress < 1) {
        animFrameIdRef.current = requestAnimationFrame(step);
      } else {
        animFrameIdRef.current = null;
        isProgrammaticScrollRef.current = false;
        setIsScrolledAway(false);
      }
    };

    animFrameIdRef.current = requestAnimationFrame(step);
  }, [activeLineIndex]);

  // Detect physical user manual scrolling (wheel/touch/pointer/keys)
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const onUserInteraction = () => {
      userScrolledRef.current = true;
      isProgrammaticScrollRef.current = false;
      if (animFrameIdRef.current) {
        cancelAnimationFrame(animFrameIdRef.current);
        animFrameIdRef.current = null;
      }
    };

    container.addEventListener("wheel", onUserInteraction, { passive: true });
    container.addEventListener("touchstart", onUserInteraction, { passive: true });
    container.addEventListener("pointerdown", onUserInteraction, { passive: true });

    return () => {
      container.removeEventListener("wheel", onUserInteraction);
      container.removeEventListener("touchstart", onUserInteraction);
      container.removeEventListener("pointerdown", onUserInteraction);
    };
  }, []);

  // Check scroll position to determine if user has scrolled away from the active line
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    const checkScrollPosition = () => {
      // If auto-scrolling normally or user hasn't manually scrolled, never show "Jump to playing"
      if (isProgrammaticScrollRef.current || !userScrolledRef.current || activeLineIndex < 0) {
        setIsScrolledAway(false);
        return;
      }

      const lineElements = container.querySelectorAll("[data-theater-line]");
      const activeEl = lineElements[activeLineIndex];
      if (!activeEl) return;

      const containerHeight = container.clientHeight;
      const elOffsetTop = activeEl.offsetTop;
      const elHeight = activeEl.clientHeight;
      const targetScroll = Math.max(0, elOffsetTop - (containerHeight / 2) + (elHeight / 2));

      const diff = targetScroll - container.scrollTop;
      // Only show pill if user manually scrolled more than 50px away from active line
      if (Math.abs(diff) > 50) {
        setIsScrolledAway(true);
        setScrollDirection(diff > 0 ? "down" : "up");
      } else {
        setIsScrolledAway(false);
        userScrolledRef.current = false;
      }
    };

    container.addEventListener("scroll", checkScrollPosition, { passive: true });
    return () => container.removeEventListener("scroll", checkScrollPosition);
  }, [activeLineIndex]);

  // Silky-smooth continuous glide when line updates and user is not manually reading elsewhere
  useEffect(() => {
    if (!userScrolledRef.current && activeLineIndex >= 0) {
      scrollToActiveLine();
    }
  }, [activeLineIndex, scrollToActiveLine]);

  // Reset scroll state on modal open
  useEffect(() => {
    if (isOpen) {
      userScrolledRef.current = false;
      setIsScrolledAway(false);
      setTimeout(() => {
        scrollToActiveLine();
      }, 100);
    }
  }, [isOpen, scrollToActiveLine]);

  const handleLineClick = (lineTime) => {
    userScrolledRef.current = false;
    setIsScrolledAway(false);
    if (userScrollTimeoutRef.current) clearTimeout(userScrollTimeoutRef.current);
    const targetAudioTime = Math.max(0, lineTime + syncOffset);
    window.dispatchEvent(new CustomEvent("kon_audio_seek", { detail: { time: targetAudioTime } }));
  };

  // Perform in-modal manual search / retry
  const handleManualSearch = async (e) => {
    if (e) e.preventDefault();
    const q = searchQuery.trim();
    if (!q) return;

    setIsLoading(true);
    setErrorMsg(null);

    try {
      // Split artist if query contains ' - ' or by words
      let t = q;
      let a = "";
      if (q.includes(" - ")) {
        const parts = q.split(" - ");
        a = parts[0].trim();
        t = parts[1].trim();
      } else if (currentTrack?.artist) {
        a = currentTrack.artist;
      }

      const res = await fetchLyrics({
        title: t,
        artist: a,
        duration: currentTrack?.duration,
      });

      setIsLoading(false);
      if (res && res.found) {
        setLyricsData(res);
        setErrorMsg(null);
        setIsSearchingManually(false);
      } else {
        setErrorMsg(res?.error || "No lyrics found. Try refining title or artist.");
      }
    } catch (err) {
      setIsLoading(false);
      setErrorMsg(err.message || "Failed to search lyrics");
    }
  };

  if (!isOpen) return null;

  return (
    <div
      className={`fixed inset-0 z-50 text-[#F8FAFC] flex flex-col justify-between p-4 sm:p-8 md:p-10 select-none neu-popup-backdrop animate-in fade-in duration-200 overflow-hidden ${
        glassMode ? "bg-[#090D14]/85 backdrop-blur-3xl" : "bg-[#090D14]/95 backdrop-blur-2xl"
      }`}
      role="dialog"
      aria-modal="true"
      aria-label="Full-screen Lyrics Theater"
    >
      {/* Ambient Artwork Reflection Backdrop for Glass Mode Theater */}
      {glassMode && currentTrack?.thumbnail ? (
        <div
          className="absolute inset-0 pointer-events-none opacity-25 filter blur-3xl scale-110"
          style={{
            backgroundImage: `url(${JSON.stringify(currentTrack.thumbnail)})`,
            backgroundSize: "cover",
            backgroundPosition: "center",
          }}
          aria-hidden="true"
        />
      ) : (
        <div className="absolute inset-0 pointer-events-none overflow-hidden opacity-40">
          <div className="absolute -top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-gradient-to-b from-[#0084FF]/20 via-[#6366F1]/10 to-transparent blur-3xl rounded-full" />
        </div>
      )}

      {/* TOP BAR: Song Meta, Sync Badge, Search Toggle & Close Controls */}
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
          {/* Quick Manual Search Toggle */}
          <button
            type="button"
            onClick={() => setIsSearchingManually((prev) => !prev)}
            className={`p-2.5 rounded-xl transition-all cursor-pointer neu-btn-elastic border ${
              isSearchingManually
                ? "neu-recessed text-[#0084FF] border-[#0084FF]/40 bg-[#0084FF]/10"
                : "neu-raised text-[#94A3B8] hover:text-[#0084FF] border-slate-700/60"
            }`}
            title="Refine Lyrics Search"
          >
            <Search className="w-4 h-4" />
          </button>

          {/* Minimize */}
          <button
            type="button"
            onClick={onClose}
            className="neu-raised p-2.5 rounded-xl text-[#94A3B8] hover:text-white cursor-pointer neu-btn-elastic group border border-slate-700/60"
            title="Exit Full-screen (Esc)"
          >
            <Minimize2 className="w-5 h-5 transition-transform duration-200 group-hover:scale-90" />
          </button>

          {/* Close */}
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

      {/* MANUAL SEARCH DRAWER / BAR */}
      {isSearchingManually && (
        <form
          onSubmit={handleManualSearch}
          className="relative z-20 mt-4 max-w-xl mx-auto w-full flex items-center gap-2 p-1.5 rounded-2xl neu-recessed border border-[#0084FF]/30 bg-[#090D14]/90 animate-in fade-in duration-200"
        >
          <Search className="w-4 h-4 text-[#0084FF] ml-3 shrink-0" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Type song title or artist (e.g., Thank You!! Home Made Kazoku)..."
            className="flex-1 bg-transparent border-none text-xs sm:text-sm text-white placeholder-slate-500 focus:outline-none px-2 py-1.5"
            autoFocus
          />
          <button
            type="submit"
            className="neu-accent px-4 py-1.5 rounded-xl text-xs font-bold text-white cursor-pointer neu-btn-elastic shrink-0 shadow-md"
          >
            Search
          </button>
        </form>
      )}

      {/* CENTER STAGE: LYRICS SCROLLER */}
      <main
        ref={containerRef}
        className="relative z-10 flex-1 overflow-y-auto px-4 sm:px-8 neu-custom-scrollbar max-w-4xl mx-auto w-full text-center"
      >
        {isLoading ? (
          <div className="h-full flex flex-col items-center justify-center space-y-3 py-20">
            <Loader2 className="w-8 h-8 text-[#0084FF] animate-spin" />
            <p className="text-sm font-semibold text-[#94A3B8]">
              Retrieving lyrics from LRCLIB...
            </p>
          </div>
        ) : errorMsg && !lyricsData?.lines?.length && !lyricsData?.plain_lyrics ? (
          <div className="h-full flex flex-col items-center justify-center space-y-4 py-16 max-w-md mx-auto">
            <div className="w-14 h-14 rounded-2xl neu-recessed flex items-center justify-center text-[#94A3B8] border border-slate-700/60 shadow-inner">
              <Mic2 className="w-7 h-7 opacity-70" />
            </div>

            <div className="space-y-1">
              <h3 className="text-base font-bold text-[#F8FAFC] m-0">
                {errorMsg}
              </h3>
              <p className="text-xs text-[#94A3B8] m-0">
                You can search with the artist name or refine the title below.
              </p>
            </div>

            <form
              onSubmit={handleManualSearch}
              className="w-full flex items-center gap-2 p-1.5 rounded-2xl neu-recessed border border-slate-700/60"
            >
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Song title or artist..."
                className="flex-1 bg-transparent border-none text-xs text-white placeholder-slate-500 focus:outline-none px-3 py-1.5"
              />
              <button
                type="submit"
                className="neu-accent px-3 py-1.5 rounded-xl text-xs font-bold text-white cursor-pointer neu-btn-elastic shrink-0"
              >
                Find
              </button>
            </form>
          </div>
        ) : isSynced ? (
          <div className="pt-[28vh] pb-[40vh] space-y-4">
            {/* Instrumental Intro Indicator */}
            {lines.length > 0 && currentTime < (lines[0].time + syncOffset) && (
              <div className="inline-flex items-center gap-2.5 px-5 py-2.5 rounded-full bg-[#0084FF]/15 border border-[#0084FF]/35 text-[#38BDF8] text-sm sm:text-base font-bold animate-pulse mx-auto mb-6 shadow-lg shadow-[#0084FF]/10 select-none">
                <Music className="w-4 h-4 shrink-0" />
                <span>Instrumental Intro ({Math.max(0, Math.ceil((lines[0].time + syncOffset) - currentTime))}s until vocals)</span>
              </div>
            )}
            {lines.map((line, idx) => {
              const isActive = idx === activeLineIndex;
              const isPast = idx < activeLineIndex;

              return (
                <div
                  key={`${line.time}_${idx}`}
                  data-theater-line={idx}
                  onClick={() => handleLineClick(line.time)}
                  className={`group relative transition-all duration-500 ease-out cursor-pointer rounded-2xl px-4 py-3 leading-relaxed tracking-tight select-none text-2xl sm:text-3xl md:text-4xl ${
                    isActive
                      ? glassMode
                        ? "text-[#FDE68A] font-black opacity-100 drop-shadow-[0_2px_28px_rgba(245,158,11,0.45)]"
                        : "text-white font-black opacity-100 drop-shadow-[0_2px_24px_rgba(255,255,255,0.45)]"
                      : isPast
                      ? "text-slate-400 font-bold opacity-30 hover:opacity-75"
                      : "text-slate-300 font-bold opacity-45 hover:opacity-85"
                  }`}
                  title={`Jump to ${formatTime(line.time + syncOffset)}`}
                >
                  <span className="block font-sans break-words">
                    {line.text || "..."}
                  </span>
                  <div className="opacity-0 group-hover:opacity-100 transition-opacity duration-200 mt-1 flex items-center justify-center">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleSyncLineToNow(line);
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-semibold bg-slate-900/90 border border-slate-700/80 text-emerald-400 hover:text-white hover:bg-emerald-600 cursor-pointer shadow-md"
                      title={`Align this lyric line to current playback time (${formatTime(currentTime)})`}
                    >
                      <Target className="w-3.5 h-3.5" />
                      <span>Sync this line to now ({formatTime(currentTime)})</span>
                    </button>
                  </div>
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
          <div className="h-full flex flex-col items-center justify-center space-y-4 py-16 max-w-md mx-auto">
            <Mic2 className="w-10 h-10 text-[#64748B] opacity-50" />
            <p className="text-sm font-bold text-[#CBD5E1] m-0">
              No lyrics found for this song.
            </p>
            <form
              onSubmit={handleManualSearch}
              className="w-full flex items-center gap-2 p-1.5 rounded-2xl neu-recessed border border-slate-700/60"
            >
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search song title or artist..."
                className="flex-1 bg-transparent border-none text-xs text-white placeholder-slate-500 focus:outline-none px-3 py-1.5"
              />
              <button
                type="submit"
                className="neu-accent px-3 py-1.5 rounded-xl text-xs font-bold text-white cursor-pointer neu-btn-elastic shrink-0"
              >
                Find
              </button>
            </form>
          </div>
        )}
      </main>

      {/* FROSTED GLASS "JUMP TO PLAYING" PILL (Placed right where user drew in lower third) */}
      {isSynced && isScrolledAway && (
        <div className="absolute bottom-28 left-1/2 -translate-x-1/2 z-40 animate-in fade-in zoom-in-95 duration-200">
          <button
            type="button"
            onClick={scrollToActiveLine}
            className={`px-5 py-2.5 rounded-full bg-slate-900/60 dark:bg-black/50 backdrop-blur-2xl border text-white transition-all duration-300 cursor-pointer neu-btn-elastic flex items-center gap-2.5 font-bold text-xs sm:text-sm select-none group ${
              glassMode
                ? "border-white/20 hover:border-[#F59E0B]/70 shadow-[0_12px_40px_rgba(0,0,0,0.6),0_0_24px_rgba(217,119,6,0.25)] hover:shadow-[0_12px_44px_rgba(245,158,11,0.45)]"
                : "border-white/20 hover:border-[#38BDF8]/70 shadow-[0_12px_40px_rgba(0,0,0,0.6),0_0_24px_rgba(56,189,248,0.25)] hover:shadow-[0_12px_44px_rgba(56,189,248,0.45)]"
            }`}
            title="Jump to currently playing lyric line"
          >
            <span className="w-2 h-2 rounded-full bg-[#10B981] shadow-[0_0_8px_#10B981] animate-pulse shrink-0" />
            {scrollDirection === "down" ? (
              <ArrowDown className={`w-4 h-4 transition-transform duration-300 group-hover:translate-y-0.5 shrink-0 ${
                glassMode ? "text-[#F59E0B]" : "text-[#38BDF8]"
              }`} />
            ) : (
              <ArrowUp className={`w-4 h-4 transition-transform duration-300 group-hover:-translate-y-0.5 shrink-0 ${
                glassMode ? "text-[#F59E0B]" : "text-[#38BDF8]"
              }`} />
            )}
            <span className="tracking-wide">Jump to playing</span>
          </button>
        </div>
      )}

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
              className={`h-full transition-all duration-150 rounded-full ${
                glassMode ? "bg-[#F59E0B]" : "bg-[#0084FF]"
              }`}
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
            {/* Timing Sync Calibration Pill */}
            {isSynced && (
              <div className="flex items-center gap-1 neu-recessed px-2.5 py-1.5 rounded-xl border border-slate-700/60 text-xs">
                <span className="text-[10px] uppercase font-bold text-[#94A3B8] tracking-wider mr-1">
                  Sync:
                </span>
                <button
                  type="button"
                  onClick={() => handleAdjustOffset(-5.0)}
                  className="px-1.5 py-0.5 rounded text-[11px] font-mono font-bold neu-raised hover:text-[#0084FF] cursor-pointer transition-colors"
                  title="Shift lyrics 5.0s earlier"
                >
                  -5s
                </button>
                <button
                  type="button"
                  onClick={() => handleAdjustOffset(-1.0)}
                  className="px-1.5 py-0.5 rounded text-[11px] font-mono font-bold neu-raised hover:text-[#0084FF] cursor-pointer transition-colors"
                  title="Shift lyrics 1.0s earlier"
                >
                  -1s
                </button>
                <button
                  type="button"
                  onClick={() => handleAdjustOffset(-0.5)}
                  className="px-1.5 py-0.5 rounded text-[11px] font-mono font-bold neu-raised hover:text-[#0084FF] cursor-pointer transition-colors"
                  title="Shift lyrics 0.5s earlier"
                >
                  -0.5s
                </button>
                <span
                  className={`font-mono font-bold text-xs px-1.5 ${
                    syncOffset !== 0 ? "text-[#F59E0B]" : "text-slate-300"
                  }`}
                  title={`Timing offset: ${syncOffset > 0 ? `+${syncOffset.toFixed(1)}s` : `${syncOffset.toFixed(1)}s`}`}
                >
                  {syncOffset !== 0 ? `${syncOffset > 0 ? "+" : ""}${syncOffset.toFixed(1)}s` : "0s"}
                </span>
                <button
                  type="button"
                  onClick={() => handleAdjustOffset(+0.5)}
                  className="px-1.5 py-0.5 rounded text-[11px] font-mono font-bold neu-raised hover:text-[#0084FF] cursor-pointer transition-colors"
                  title="Delay lyrics 0.5s later"
                >
                  +0.5s
                </button>
                <button
                  type="button"
                  onClick={() => handleAdjustOffset(+1.0)}
                  className="px-1.5 py-0.5 rounded text-[11px] font-mono font-bold neu-raised hover:text-[#0084FF] cursor-pointer transition-colors"
                  title="Delay lyrics 1.0s later"
                >
                  +1s
                </button>
                <button
                  type="button"
                  onClick={() => handleAdjustOffset(+5.0)}
                  className="px-1.5 py-0.5 rounded text-[11px] font-mono font-bold neu-raised hover:text-[#0084FF] cursor-pointer transition-colors"
                  title="Delay lyrics 5.0s later"
                >
                  +5s
                </button>
                <button
                  type="button"
                  onClick={() => handleSyncLineToNow(activeLineIndex >= 0 ? lines[activeLineIndex] : lines[0])}
                  className="px-2 py-0.5 rounded text-[11px] font-bold text-emerald-400 hover:text-white hover:bg-emerald-600/80 cursor-pointer transition-colors flex items-center gap-1"
                  title="Sync active lyric to current audio playback time"
                >
                  <Target className="w-3 h-3" />
                  <span>Sync Here</span>
                </button>
                {syncOffset !== 0 && (
                  <button
                    type="button"
                    onClick={() => handleSetOffset(0)}
                    className="ml-1 text-[11px] text-slate-400 hover:text-white underline cursor-pointer"
                    title="Reset offset to 0s"
                  >
                    Reset
                  </button>
                )}
              </div>
            )}

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
