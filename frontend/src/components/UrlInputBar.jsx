import { KonFlashIcon, KonPrecisionIcon } from "./KonIcons";
import React, { useState, useEffect, useRef, useCallback } from "react";
import {
  Search,
  Clipboard,
  X,
  Loader2,
  AlertCircle,
  Music,
  Film,
  Globe,
  Cpu,
  Zap,
  Sparkles,
  ChevronRight,
  User,
  Layers,
  Compass,
  CornerDownLeft,
} from "lucide-react";
import { fetchSearchSuggestions } from "../api";
import {
  getSearchQueryHistory,
  addSearchQueryHistory,
  clearSearchQueryHistory,
} from "../utils/playerStorage";
import { History, Clock } from "lucide-react";

export default function UrlInputBar({
  onAnalyze,
  isLoading,
  error,
  onClearError,
  onOpenModelModal,
  engineMode: propEngineMode,
  onEngineModeChange,
}) {
  const [url, setUrl] = useState("");
  const [searchMode, setSearchMode] = useState("audio"); // "audio", "video", "all"
  const [internalEngineMode, setInternalEngineMode] = useState(() => {
    try {
      return localStorage.getItem("kon_search_engine_mode") || "rei";
    } catch {
      return "rei";
    }
  });
  const activeEngineMode = propEngineMode || internalEngineMode;

  const handleEngineModeSelect = (mode) => {
    try {
      localStorage.setItem("kon_search_engine_mode", mode);
    } catch (_) {}
    if (onEngineModeChange) {
      onEngineModeChange(mode);
    } else {
      setInternalEngineMode(mode);
    }
  };

  const [suggestions, setSuggestions] = useState([]);
  const [isOpen, setIsOpen] = useState(false);
  const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const [recentSearches, setRecentSearches] = useState(() => getSearchQueryHistory());
  const [isInputFocused, setIsInputFocused] = useState(false);

  useEffect(() => {
    const handleHistoryChanged = (e) => {
      setRecentSearches(e.detail || []);
    };
    window.addEventListener("kon_search_history_changed", handleHistoryChanged);
    return () => window.removeEventListener("kon_search_history_changed", handleHistoryChanged);
  }, []);

  const wrapperRef = useRef(null);
  const inputRef = useRef(null);
  const abortControllerRef = useRef(null);
  const debounceTimerRef = useRef(null);
  const requestIdRef = useRef(0);
  const suppressSuggestionsRef = useRef(false);

  const isUrl = url.trim().startsWith("http://") || url.trim().startsWith("https://");

  // Immediately dismiss suggestions, cancel debounces, and blur input
  const dismissSuggestions = useCallback(() => {
    suppressSuggestionsRef.current = true;
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    requestIdRef.current++;
    setIsOpen(false);
    setSuggestions([]);
    setSelectedIndex(-1);
    setIsLoadingSuggestions(false);
    inputRef.current?.blur();
  }, []);

  // Dismiss suggestions when clicking outside
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setIsOpen(false);
        setSelectedIndex(-1);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Force suggestions closed whenever an active search is running
  useEffect(() => {
    if (isLoading) {
      dismissSuggestions();
    }
  }, [isLoading, dismissSuggestions]);

  // Request suggestions as the user types with short debounce and stale cancellation
  useEffect(() => {
    // If the input update came from selecting a suggestion or submitting search, skip fetching
    if (suppressSuggestionsRef.current) {
      suppressSuggestionsRef.current = false;
      setSuggestions([]);
      setIsOpen(false);
      setIsLoadingSuggestions(false);
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      return;
    }

    const cleanQ = url.trim();

    // Direct URLs or empty strings do not trigger autocomplete
    if (!cleanQ || isUrl) {
      setSuggestions([]);
      setIsOpen(false);
      setIsLoadingSuggestions(false);
      setSelectedIndex(-1);
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
      return;
    }

    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // 120ms debounce enables ultra-responsive typing with sub-50ms backend latency
    debounceTimerRef.current = setTimeout(async () => {
      const currentRequestId = ++requestIdRef.current;
      const controller = new AbortController();
      abortControllerRef.current = controller;
      setIsLoadingSuggestions(true);

      try {
        const data = await fetchSearchSuggestions(cleanQ, {
          mediaType: searchMode,
          engineMode: activeEngineMode,
          signal: controller.signal,
          limit: 6,
        });

        // Ignore stale responses or if search has been submitted
        if (requestIdRef.current !== currentRequestId || suppressSuggestionsRef.current) return;

        const results = data.suggestions || [];
        setSuggestions(results);
        setIsOpen(results.length > 0);
        setSelectedIndex(-1);
      } catch (err) {
        if (err.name === "AbortError") return;
        setSuggestions([]);
        setIsOpen(false);
      } finally {
        if (requestIdRef.current === currentRequestId && !suppressSuggestionsRef.current) {
          setIsLoadingSuggestions(false);
        }
      }
    }, 120);

    return () => {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, [url, searchMode, activeEngineMode, isUrl]);

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        suppressSuggestionsRef.current = false;
        setUrl(text.trim());
        if (onClearError) onClearError();
      }
    } catch (_) {
      // Clipboard access denied or unsupported
    }
  };

  const handleClear = () => {
    dismissSuggestions();
    setUrl("");
    if (onClearError) onClearError();
  };

  const handleSelectSuggestion = (sug) => {
    const queryToSearch = sug.query || sug.title;
    dismissSuggestions();
    setUrl(queryToSearch);
    addSearchQueryHistory(queryToSearch, activeEngineMode);
    if (onClearError) onClearError();
    onAnalyze(queryToSearch, searchMode, activeEngineMode);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    dismissSuggestions();
    addSearchQueryHistory(url.trim(), activeEngineMode);
    onAnalyze(url.trim(), searchMode, activeEngineMode);
  };

  const handleKeyDown = (e) => {
    if (!isOpen || suggestions.length === 0) {
      if (e.key === "ArrowDown" && suggestions.length > 0) {
        setIsOpen(true);
        e.preventDefault();
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1));
    } else if (e.key === "Enter") {
      if (selectedIndex >= 0 && selectedIndex < suggestions.length) {
        e.preventDefault();
        handleSelectSuggestion(suggestions[selectedIndex]);
      }
    } else if (e.key === "Escape") {
      e.preventDefault();
      setIsOpen(false);
      setSelectedIndex(-1);
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds || seconds <= 0) return "";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  const getPlaceholder = () => {
    if (isUrl) return "Paste media URL (YouTube, SoundCloud, Vimeo)...";
    if (searchMode === "audio") {
      return "Search any song, artist, or keyword (e.g. Bankai, I Wanna Be, Shelter)...";
    }
    if (searchMode === "video") {
      return "Search videos, music videos, or paste video URL...";
    }
    return "Search any song, artist, video, or paste URL...";
  };

  return (
    <section ref={wrapperRef} className="space-y-3 relative">
      {/* Segmented Mode & Dual Search Engine Track */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        {/* Media Filter Tabs */}
        <div className="neu-recessed p-1.5 flex items-center gap-1 rounded-2xl">
          <button
            type="button"
            onClick={() => setSearchMode("audio")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold cursor-pointer transition-all ${
              searchMode === "audio"
                ? "neu-raised text-[#0084FF]"
                : "text-[#64748B] hover:text-[#1E293B] dark:text-[#94A3B8] dark:hover:text-[#F1F5F9]"
            }`}
          >
            <Music className="w-3.5 h-3.5" />
            <span>Song &amp; Music</span>
          </button>

          <button
            type="button"
            onClick={() => setSearchMode("video")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold cursor-pointer transition-all ${
              searchMode === "video"
                ? "neu-raised text-[#0084FF]"
                : "text-[#64748B] hover:text-[#1E293B] dark:text-[#94A3B8] dark:hover:text-[#F1F5F9]"
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>Video</span>
          </button>

          <button
            type="button"
            onClick={() => setSearchMode("all")}
            className={`flex items-center gap-2 px-3.5 py-1.5 rounded-xl text-xs font-semibold cursor-pointer transition-all ${
              searchMode === "all"
                ? "neu-raised text-[#0084FF]"
                : "text-[#64748B] hover:text-[#1E293B] dark:text-[#94A3B8] dark:hover:text-[#F1F5F9]"
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            <span>All Sources</span>
          </button>
        </div>

        {/* Dual Search Engine Selector: Rei vs Rei Flash */}
        <div className="flex flex-col sm:items-end gap-1">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-bold text-[#64748B] dark:text-[#94A3B8] hidden xs:inline uppercase tracking-wider">
              Search Engine
            </span>
            <div
              role="tablist"
              aria-label="Search Engine Selector"
              className="neu-recessed p-1 flex items-center gap-1 rounded-2xl"
            >
              <button
                type="button"
                role="tab"
                aria-selected={activeEngineMode === "rei"}
                tabIndex={0}
                onClick={() => handleEngineModeSelect("rei")}
                onKeyDown={(e) => {
                  if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                    e.preventDefault();
                    handleEngineModeSelect("flash");
                  }
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-all ${
                  activeEngineMode === "rei"
                    ? "neu-raised text-[#0084FF] border border-[#0084FF]/35 bg-[#0084FF]/10 shadow-xs"
                    : "text-[#64748B] hover:text-[#1E293B] dark:text-[#94A3B8] dark:hover:text-[#F1F5F9]"
                }`}
                title="Rei — Precision: Maximum precision. Better discovery and deeper matching."
              >
                <KonPrecisionIcon className="w-3.5 h-3.5 shrink-0" />
                <span>Rei — Precision</span>
              </button>

              <button
                type="button"
                role="tab"
                aria-selected={activeEngineMode === "flash"}
                tabIndex={0}
                onClick={() => handleEngineModeSelect("flash")}
                onKeyDown={(e) => {
                  if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                    e.preventDefault();
                    handleEngineModeSelect("rei");
                  }
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer transition-all ${
                  activeEngineMode === "flash"
                    ? "neu-raised text-[#F59E0B] border border-[#F59E0B]/35 bg-[#F59E0B]/10 shadow-xs"
                    : "text-[#64748B] hover:text-[#1E293B] dark:text-[#94A3B8] dark:hover:text-[#F1F5F9]"
                }`}
                title="Rei Flash — Speed: Faster results. Lightweight matching and lower latency."
              >
                <KonFlashIcon className="w-3.5 h-3.5 shrink-0" />
                <span>Rei Flash — Speed</span>
              </button>
            </div>
          </div>
          {/* Active Mode Dynamic Description */}
          <p className="text-[10px] text-[#64748B] dark:text-[#94A3B8] m-0 px-1 font-medium select-none">
            {activeEngineMode === "flash"
              ? "Faster results. Lightweight matching and lower latency."
              : "Maximum precision. Better discovery and deeper matching."}
          </p>
        </div>
      </div>

      {/* Error Feedback Banner */}
      {error && (
        <div className="neu-recessed p-3 rounded-2xl border border-red-500/30 bg-red-500/5 flex items-center justify-between gap-3 text-xs text-[#EF4444] animate-fade-in">
          <div className="flex items-center gap-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span className="font-semibold">{error}</span>
          </div>
          {onClearError && (
            <button
              type="button"
              onClick={onClearError}
              className="text-[#EF4444] hover:text-red-700 cursor-pointer p-1 rounded-lg"
              title="Dismiss error"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}

      {/* Main Search Input Form */}
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row items-stretch gap-3.5 relative">
        {/* Recessed Sculpted Input Well */}
        <div className="neu-recessed flex-1 flex items-center px-4 py-3 gap-2.5 relative">
          {isLoadingSuggestions ? (
            <Loader2 className="w-5 h-5 text-[#0084FF] animate-spin shrink-0" />
          ) : (
            <Search className="w-5 h-5 text-[#0084FF] shrink-0" />
          )}
          <input
            ref={inputRef}
            type="text"
            value={url}
            onChange={(e) => {
              suppressSuggestionsRef.current = false;
              setUrl(e.target.value);
              if (onClearError) onClearError();
            }}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              setIsInputFocused(true);
              if (!suppressSuggestionsRef.current && suggestions.length > 0 && !isUrl) {
                setIsOpen(true);
              }
            }}
            onBlur={() => {
              // Delay so chip clicks can register
              setTimeout(() => setIsInputFocused(false), 200);
            }}
            placeholder={getPlaceholder()}
            className="flex-1 bg-transparent border-none outline-none text-sm text-[#1E293B] placeholder-[#94A3B8] font-medium"
            disabled={isLoading}
            autoComplete="off"
            spellCheck="false"
          />
          {url && (
            <button
              type="button"
              onClick={handleClear}
              className="text-[#94A3B8] hover:text-[#1E293B] p-1 cursor-pointer transition-colors"
              title="Clear input"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <button
            type="button"
            onClick={handlePaste}
            className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#475569] hover:text-[#0084FF] cursor-pointer"
            title="Paste from clipboard"
          >
            <Clipboard className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Paste</span>
          </button>
        </div>

        {/* Primary Action Button */}
        <button
          type="submit"
          disabled={isLoading || !url.trim()}
          className="neu-accent px-7 py-3 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed text-sm font-semibold whitespace-nowrap"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin text-white" />
              <span>Searching...</span>
            </>
          ) : isUrl ? (
            <>
              <Search className="w-4 h-4" />
              <span>Inspect Media</span>
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              <span>Search &amp; Find</span>
            </>
          )}
        </button>
      </form>

      {/* Recent Searches Chips Shelf */}
      {recentSearches.length > 0 && !url.trim() && (
        <div className="flex flex-wrap items-center gap-2 pt-1 animate-fade-in">
          <span className="text-[11px] font-bold text-[#64748B] dark:text-[#94A3B8] flex items-center gap-1">
            <Clock className="w-3 h-3 text-[#0084FF]" />
            <span>Recent:</span>
          </span>
          <div className="flex flex-wrap items-center gap-1.5 flex-1">
            {recentSearches.slice(0, 6).map((item, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => {
                  setUrl(item.query);
                  if (item.engine_mode && onEngineModeChange) {
                    onEngineModeChange(item.engine_mode);
                  }
                  onAnalyze(item.query, searchMode, item.engine_mode || activeEngineMode);
                }}
                className="neu-raised px-2.5 py-1 rounded-lg text-xs text-[#334155] dark:text-[#CBD5E1] hover:text-[#0084FF] transition-colors cursor-pointer flex items-center gap-1"
                title={`Search "${item.query}"`}
              >
                <span>{item.query}</span>
                {item.engine_mode === "flash" ? (
                  <KonFlashIcon className="w-2.5 h-2.5 text-[#F59E0B]" />
                ) : (
                  <KonPrecisionIcon className="w-2.5 h-2.5 text-[#0084FF]" />
                )}
              </button>
            ))}
            <button
              type="button"
              onClick={() => {
                clearSearchQueryHistory();
                setRecentSearches([]);
              }}
              className="text-[10px] text-[#94A3B8] hover:text-[#EF4444] px-1 cursor-pointer transition-colors"
              title="Clear search history"
            >
              Clear
            </button>
          </div>
        </div>
      )}

      {/* Intelligent Search Suggestions & Song Discovery Dropdown */}
      {isOpen && suggestions.length > 0 && (
        <div
          className="absolute left-0 right-0 top-full mt-2 z-50 neu-card p-2 space-y-1 shadow-2xl border border-[#0084FF]/25 animate-fade-in max-h-[420px] overflow-y-auto"
          role="listbox"
          aria-label="Search suggestions"
        >
          <div className="flex items-center justify-between px-3 py-1.5 text-[11px] font-bold text-[#64748B] dark:text-[#94A3B8] border-b border-slate-200/40 dark:border-slate-700/40 pb-1.5 mb-1">
            <span className="flex items-center gap-1.5">
              <Sparkles className="w-3 h-3 text-[#0084FF]" />
              <span>Intelligent Discovery · KON Search 1.2 Rei</span>
            </span>
            <span className="text-[10px] font-mono text-[#94A3B8] hidden sm:inline">
              ↑↓ navigate · Enter select · Esc close
            </span>
          </div>

          {suggestions.map((sug, idx) => {
            const isSelected = selectedIndex === idx;
            const isArtist = sug.type === "artist" || sug.category === "artist";
            const isVersion = sug.category === "version";
            const isContext = sug.category === "context";
            const isPartial = sug.category === "partial";
            const isSong = sug.type === "song" || (!sug.type && !isArtist);
            const isVideo = sug.type === "video";
            const isMedia = isSong || isVideo || isArtist;

            if (isArtist) {
              return (
                <div
                  key={sug.id || `sug_${idx}`}
                  role="option"
                  aria-selected={isSelected}
                  onMouseDown={(e) => { e.preventDefault(); handleSelectSuggestion(sug); }} onClick={() => handleSelectSuggestion(sug)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`p-2.5 rounded-xl cursor-pointer transition-all flex items-center justify-between gap-3 ${
                    isSelected
                      ? "neu-raised text-[#8B5CF6] border border-[#8B5CF6]/35 bg-[#8B5CF6]/5"
                      : "hover:neu-raised"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <div className="w-10 h-10 rounded-lg neu-recessed p-0.5 shrink-0 overflow-hidden flex items-center justify-center bg-[#8B5CF6]/10 text-[#8B5CF6]">
                      <User className="w-5 h-5 text-[#8B5CF6]" />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[#1E293B] dark:text-[#E2E8F0] truncate">
                          {sug.title || sug.artist}
                        </span>
                        <span className="neu-recessed px-1.5 py-0.2 rounded text-[9px] font-bold text-[#8B5CF6] border border-[#8B5CF6]/30 uppercase">
                          Artist
                        </span>
                      </div>
                      <p className="text-[11px] text-[#8B5CF6] font-semibold truncate m-0 mt-0.5 flex items-center gap-1">
                        <User className="w-3 h-3 text-[#8B5CF6] shrink-0" />
                        <span>Artist · Click to explore songs</span>
                      </p>
                    </div>
                  </div>
                  <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#8B5CF6] border border-[#8B5CF6]/30 bg-[#8B5CF6]/10 shrink-0 truncate max-w-[170px] hidden sm:inline-flex items-center gap-1">
                    <User className="w-3 h-3 text-[#8B5CF6]" />
                    <span>Artist Discovery</span>
                  </span>
                </div>
              );
            }

            if (isMedia) {
              return (
                <div
                  key={sug.id || `sug_${idx}`}
                  role="option"
                  aria-selected={isSelected}
                  onMouseDown={(e) => { e.preventDefault(); handleSelectSuggestion(sug); }} onClick={() => handleSelectSuggestion(sug)}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  className={`p-2.5 rounded-xl cursor-pointer transition-all flex items-center justify-between gap-3 ${
                    isSelected
                      ? "neu-raised text-[#0084FF] border border-[#0084FF]/35 bg-[#0084FF]/5"
                      : "hover:neu-raised"
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    {/* Verified Media Thumbnail or Music/Video/Version Icon */}
                    <div className="w-10 h-10 rounded-lg neu-recessed p-0.5 shrink-0 overflow-hidden flex items-center justify-center relative">
                      {sug.thumbnail ? (
                        <img
                          src={sug.thumbnail}
                          alt=""
                          className="w-full h-full object-cover rounded-md"
                          referrerPolicy="no-referrer"
                        />
                      ) : isVideo ? (
                        <Film className="w-4 h-4 text-[#EF4444]" />
                      ) : isVersion ? (
                        <Layers className="w-4 h-4 text-[#EC4899]" />
                      ) : isContext ? (
                        <Compass className="w-4 h-4 text-[#10B981]" />
                      ) : (
                        <Music className="w-4 h-4 text-[#0084FF]" />
                      )}
                      {/* Platform indicator chip overlay if video */}
                      {isVideo && (
                        <span className="absolute bottom-0.5 right-0.5 bg-[#EF4444] text-[8px] font-black text-white px-1 py-0.2 rounded shadow-sm">
                          YT
                        </span>
                      )}
                    </div>

                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-[#1E293B] dark:text-[#E2E8F0] truncate">
                          {sug.title}
                        </span>
                        {sug.duration && (
                          <span className="text-[10px] text-[#94A3B8] font-mono shrink-0">
                            {formatDuration(sug.duration)}
                          </span>
                        )}
                      </div>
                      {isVideo ? (
                        <p className="text-[11px] font-semibold truncate m-0 mt-0.5 flex items-center gap-1.5">
                          <span className="inline-flex items-center gap-1 text-[#EF4444] font-bold">
                            <Film className="w-3 h-3 text-[#EF4444]" />
                            <span>YouTube Video</span>
                          </span>
                          {sug.artist && (
                            <>
                              <span className="text-[#94A3B8]">·</span>
                              <span className="text-[#64748B] dark:text-[#94A3B8] truncate">{sug.artist}</span>
                            </>
                          )}
                        </p>
                      ) : isVersion ? (
                        <p className="text-[11px] text-[#EC4899] font-semibold truncate m-0 mt-0.5 flex items-center gap-1">
                          <Layers className="w-3 h-3 text-[#EC4899] shrink-0" />
                          <span>{sug.artist || sug.version_hint || "Version Match"}</span>
                        </p>
                      ) : isContext ? (
                        <p className="text-[11px] text-[#10B981] font-semibold truncate m-0 mt-0.5 flex items-center gap-1">
                          <Compass className="w-3 h-3 text-[#10B981] shrink-0" />
                          <span>{sug.artist || sug.context_clue || "Soundtrack"}</span>
                        </p>
                      ) : sug.artist ? (
                        <p className="text-[11px] text-[#10B981] font-semibold truncate m-0 mt-0.5 flex items-center gap-1">
                          <Music className="w-3 h-3 text-[#10B981] shrink-0" />
                          <span>{sug.artist}</span>
                        </p>
                      ) : null}
                    </div>
                  </div>

                  {isVideo ? (
                    <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#EF4444] border border-[#EF4444]/30 bg-[#EF4444]/10 shrink-0 truncate max-w-[170px] hidden sm:inline-flex items-center gap-1">
                      <Film className="w-3 h-3 text-[#EF4444]" />
                      <span>{sug.match_reason || "YouTube Video"}</span>
                    </span>
                  ) : isVersion ? (
                    <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#EC4899] border border-[#EC4899]/30 bg-[#EC4899]/10 shrink-0 truncate max-w-[170px] hidden sm:inline-flex items-center gap-1">
                      <Layers className="w-3 h-3 text-[#EC4899]" />
                      <span>{sug.version_hint || sug.match_reason || "Version Clue"}</span>
                    </span>
                  ) : isContext ? (
                    <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#10B981] border border-[#10B981]/30 bg-[#10B981]/10 shrink-0 truncate max-w-[170px] hidden sm:inline-flex items-center gap-1">
                      <Compass className="w-3 h-3 text-[#10B981]" />
                      <span>{sug.context_clue || sug.match_reason || "Soundtrack Clue"}</span>
                    </span>
                  ) : isPartial ? (
                    <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#F59E0B] border border-[#F59E0B]/30 bg-[#F59E0B]/10 shrink-0 truncate max-w-[170px] hidden sm:inline-flex items-center gap-1">
                      <Sparkles className="w-3 h-3 text-[#F59E0B]" />
                      <span>{sug.match_reason || "Partial Match"}</span>
                    </span>
                  ) : sug.match_reason ? (
                    <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#0084FF] shrink-0 truncate max-w-[170px] hidden sm:inline-flex items-center gap-1">
                      <Music className="w-3 h-3 text-[#0084FF]" />
                      <span>{sug.match_reason}</span>
                    </span>
                  ) : null}
                </div>
              );
            }

            // Query Refinement Suggestion
            return (
              <div
                key={sug.id || `sug_${idx}`}
                role="option"
                aria-selected={isSelected}
                onMouseDown={(e) => { e.preventDefault(); handleSelectSuggestion(sug); }} onClick={() => handleSelectSuggestion(sug)}
                onMouseEnter={() => setSelectedIndex(idx)}
                className={`px-3 py-2 rounded-xl cursor-pointer transition-all flex items-center justify-between gap-3 ${
                  isSelected
                    ? "neu-raised text-[#0084FF] border border-[#0084FF]/35 bg-[#0084FF]/5"
                    : "hover:neu-raised"
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1">
                  <Search className="w-3.5 h-3.5 text-[#94A3B8] shrink-0" />
                  <span className="text-xs font-medium text-[#1E293B] dark:text-[#E2E8F0] truncate">
                    {sug.query}
                  </span>
                </div>
                <div className="flex items-center gap-1 text-[10px] text-[#94A3B8] uppercase font-bold shrink-0">
                  <span>Search</span>
                  <ChevronRight className="w-3 h-3 text-[#94A3B8]" />
                </div>
              </div>
            );
          })}

          {/* Search As Typed Fallback Option */}
          {url.trim() && !isUrl && (
            <div
              role="option"
              onMouseDown={(e) => {
                e.preventDefault();
                dismissSuggestions();
                onAnalyze(url.trim(), searchMode, activeEngineMode);
              }}
              onClick={() => {
                dismissSuggestions();
                onAnalyze(url.trim(), searchMode, activeEngineMode);
              }}
              className="p-2.5 mt-1 rounded-xl cursor-pointer neu-recessed hover:neu-raised flex items-center justify-between text-xs text-[#64748B] hover:text-[#0084FF] border-t border-slate-200/50 dark:border-slate-700/50 transition-all"
            >
              <div className="flex items-center gap-2 min-w-0">
                <Search className="w-3.5 h-3.5 text-[#0084FF] shrink-0" />
                <span className="truncate">
                  Search for &ldquo;<strong>{url.trim()}</strong>&rdquo; as typed
                </span>
              </div>
              <span className="neu-raised px-2 py-0.5 rounded text-[10px] font-mono text-[#64748B] shrink-0 flex items-center gap-1">
                <span>Enter</span>
                <CornerDownLeft className="w-2.5 h-2.5 text-[#64748B]" />
              </span>
            </div>
          )}
        </div>
      )}

      {/* Dual Search Engine Model Spotlight Banner */}
      <div className="flex flex-wrap items-center justify-between gap-2 px-1 text-xs">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-[11px] text-[#94A3B8]">Active Engine:</span>
          <button
            type="button"
            onClick={onOpenModelModal}
            className={`neu-recessed px-2.5 py-1 rounded-lg text-[11px] font-bold cursor-pointer inline-flex items-center gap-1.5 transition-colors ${
              activeEngineMode === "flash"
                ? "text-[#F59E0B] hover:text-[#D97706] border border-[#F59E0B]/25"
                : "text-[#0084FF] hover:text-[#0074E0] border border-[#0084FF]/25"
            }`}
            title={`Active Search Engine: ${activeEngineMode === "flash" ? "KON Search 1.2 Rei Flash (Speed Mode)" : "KON Search 1.2 Rei (Precision Mode)"}`}
          >
            {activeEngineMode === "flash" ? (
              <KonFlashIcon className="w-3.5 h-3.5" />
            ) : (
              <KonPrecisionIcon className="w-3.5 h-3.5" />
            )}
            <span>{activeEngineMode === "flash" ? "KON Search 1.2 Rei Flash" : "KON Search 1.2 Rei"}</span>
            <span className="text-[10px] opacity-80 font-mono inline-flex items-center gap-1">
              {activeEngineMode === "flash" ? (
                <>
                  <KonFlashIcon className="w-2.5 h-2.5" />
                  <span>Speed</span>
                </>
              ) : (
                <>
                  <KonPrecisionIcon className="w-2.5 h-2.5" />
                  <span>Precision</span>
                </>
              )}
            </span>
          </button>
          <span className="text-[11px] text-[#94A3B8] hidden sm:inline">
            {activeEngineMode === "flash"
              ? "· Lightweight Token Scoring · Bounded Network Retrieval · Zero Lag"
              : "· Supervised ML Ranker · Deep Contextual Discovery · 4,972 Associations"}
          </span>
        </div>

        <span className="text-[10px] font-mono text-[#94A3B8] hidden md:inline">
          {activeEngineMode === "flash" ? "<0.05ms Native Rust Ranking" : "<0.20ms Native Rust Core"}
        </span>
      </div>

      {/* Error Message */}
      {error && (
        <div className="neu-card p-4 text-xs text-[#DC2626] flex items-start gap-2.5 bg-[#FEE2E2]/60 border border-[#FCA5A5]">
          <AlertCircle className="w-4 h-4 shrink-0 mt-0.5 text-[#DC2626]" />
          <div className="flex-1 font-medium">{error}</div>
        </div>
      )}
    </section>
  );
}
