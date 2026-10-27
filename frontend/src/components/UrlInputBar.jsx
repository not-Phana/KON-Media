import React, { useState } from "react";
import { Search, Clipboard, X, Loader2, AlertCircle } from "lucide-react";

export default function UrlInputBar({ onAnalyze, isLoading, error, onClearError }) {
  const [url, setUrl] = useState("");

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
    if (!url.trim() || isLoading) return;
    onAnalyze(url.trim());
  };

  return (
    <section className="space-y-3">
      <form onSubmit={handleSubmit} className="flex flex-col sm:flex-row items-stretch gap-3">
        {/* Recessed Input Well */}
        <div className="neu-recessed flex-1 flex items-center px-4 py-2.5 gap-2 border border-[#2D323B] focus-within:border-[#8BC5B0] transition-colors">
          <Search className="w-5 h-5 text-[#6B7280] shrink-0" />
          <input
            type="text"
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (onClearError) onClearError();
            }}
            placeholder="Paste media URL (e.g. YouTube, Vimeo, SoundCloud, or authorized web media)..."
            className="flex-1 bg-transparent border-none outline-none text-sm text-[#F3F4F6] placeholder-[#6B7280] font-mono"
            disabled={isLoading}
          />
          {url && (
            <button
              type="button"
              onClick={handleClear}
              className="text-[#6B7280] hover:text-[#F3F4F6] p-1 cursor-pointer"
              title="Clear input"
            >
              <X className="w-4 h-4" />
            </button>
          )}
          <button
            type="button"
            onClick={handlePaste}
            className="neu-raised flex items-center gap-1.5 px-2.5 py-1 text-xs text-[#A5ABB5] hover:text-[#8BC5B0] cursor-pointer"
            title="Paste from clipboard"
          >
            <Clipboard className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Paste</span>
          </button>
        </div>

        {/* Analyze Button */}
        <button
          type="submit"
          disabled={!url.trim() || isLoading}
          className="neu-accent px-6 py-2.5 flex items-center justify-center gap-2 cursor-pointer disabled:opacity-50 disabled:cursor-not-allowed shrink-0"
        >
          {isLoading ? (
            <>
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Analyzing...</span>
            </>
          ) : (
            <>
              <Search className="w-4 h-4" />
              <span>Analyze Media</span>
            </>
          )}
        </button>
      </form>

      {/* Error Alert Banner */}
      {error && (
        <div className="flex items-center gap-2.5 p-3 rounded-xl bg-[#2C1D20] border border-[#EF8585]/40 text-[#EF8585] text-xs">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span className="flex-1">{error}</span>
          <button onClick={onClearError} className="hover:text-white cursor-pointer">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}
    </section>
  );
}
