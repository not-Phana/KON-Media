import React, { useState } from "react";
import { Search, Clipboard, X, Loader2, AlertCircle, Music, Film, Globe, Brain } from "lucide-react";

export default function UrlInputBar({ onAnalyze, isLoading, error, onClearError, onOpenLearnModal }) {
  const [url, setUrl] = useState("");
  const [searchMode, setSearchMode] = useState("audio"); // "audio", "video", "all"

  const handlePaste = async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        setUrl(text.trim());
        if (onClearError) onClearError();
      }
    } catch (e) {
      // Clipboard access denied or unsupported
    }
  };

  const handleClear = () => {
    setUrl("");
    if (onClearError) onClearError();
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!url.trim()) return;
    onAnalyze(url.trim(), searchMode);
  };

  const isUrl = url.trim().startsWith("http://") || url.trim().startsWith("https://");

  const getPlaceholder = () => {
    if (isUrl) return "Paste media URL (YouTube, SoundCloud, Vimeo)...";
    if (searchMode === "audio") {
      return "Search any song, artist, or soundtrack (e.g. Titanic, Cyberpunk, Blinding Lights)...";
    }
    if (searchMode === "video") {
      return "Search videos, music videos, or paste video URL...";
    }
    return "Search any song, artist, video, or paste URL...";
  };

  return (
    <section className="space-y-3">
      {/* Segmented Mode Selector Track */}
      <div className="flex flex-wrap items-center justify-between gap-3 px-1">
        <div className="neu-recessed p-1.5 flex items-center gap-1 rounded-2xl">
          <button
            type="button"
            onClick={() => setSearchMode("audio")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-all ${
              searchMode === "audio"
                ? "neu-raised text-[#0084FF]"
                : "text-[#64748B] hover:text-[#1E293B]"
            }`}
          >
            <Music className="w-3.5 h-3.5" />
            <span>Song &amp; Music</span>
          </button>

          <button
            type="button"
            onClick={() => setSearchMode("video")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-all ${
              searchMode === "video"
                ? "neu-raised text-[#0084FF]"
                : "text-[#64748B] hover:text-[#1E293B]"
            }`}
          >
            <Film className="w-3.5 h-3.5" />
            <span>Video</span>
          </button>

          <button
            type="button"
            onClick={() => setSearchMode("all")}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-all ${
              searchMode === "all"
                ? "neu-raised text-[#0084FF]"
                : "text-[#64748B] hover:text-[#1E293B]"
            }`}
          >
            <Globe className="w-3.5 h-3.5" />
            <span>All Sources</span>
          </button>
        </div>

        {onOpenLearnModal && (
          <button
            type="button"
            onClick={onOpenLearnModal}
            className="neu-raised flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-[#334155] hover:text-[#0084FF] cursor-pointer transition-colors"
            title="Import or teach search engine from Google Drive or Google Docs"
          >
            <Brain className="w-3.5 h-3.5 text-[#0084FF]" />
            <span>Knowledge &amp; Docs</span>
          </button>
        )}
      </div>

      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row items-stretch gap-3.5">
        {/* Recessed Sculpted Input Well */}
        <div className="neu-recessed flex-1 flex items-center px-4 py-3 gap-2.5">
          <Search className="w-5 h-5 text-[#0084FF] shrink-0" />
          <input
            type="text"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (onClearError) onClearError();
            }}
            placeholder={getPlaceholder()}
            className="flex-1 bg-transparent border-none outline-none text-sm text-[#1E293B] placeholder-[#94A3B8] font-medium"
            disabled={isLoading}
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
