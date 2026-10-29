import React, { useState } from "react";
import {
  Search,
  Sparkles,
  Clock,
  User,
  X,
  CheckCircle2,
  ThumbsDown,
  Download,
  Film,
  Music,
  SlidersHorizontal,
  ChevronRight,
  Cpu,
} from "lucide-react";

export default function SearchResultsCard({
  query,
  results,
  onSelectCandidate,
  onDirectDownload,
  onDismiss,
  onFeedback,
  onOpenLearnModal,
  onOpenModelModal,
}) {
  const [reportedIds, setReportedIds] = useState(new Set());

  if (!results || results.length === 0) {
    return (
      <div className="neu-card p-6 space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold text-[#1E293B]">
            <Search className="w-4 h-4 text-[#0084FF]" />
            <span>Search Results for "{query}"</span>
          </div>
          <button
            onClick={onDismiss}
            className="neu-raised p-1.5 text-[#64748B] hover:text-[#1E293B] cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-[#64748B] m-0 font-medium">
          No media candidates found matching this query. Try a different title or paste a direct URL.
        </p>
      </div>
    );
  }

  const handleReportMismatch = (e, cand) => {
    e.stopPropagation();
    setReportedIds((prev) => new Set(prev).add(cand.id));
    if (onFeedback) {
      onFeedback({
        query,
        selected_id: cand.id,
        selected_title: cand.title,
        selected_url: cand.url,
        is_mismatch: true,
        reason: "User flagged as irrelevant",
        provider: cand.platform,
      });
    }
  };

  const formatDuration = (seconds) => {
    if (!seconds || seconds <= 0) return "";
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
  };

  return (
    <div className="neu-card p-6 space-y-4 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between gap-3 pb-1">
        <div className="flex flex-wrap items-center gap-2.5">
          <div className="w-2.5 h-2.5 rounded-full bg-[#0084FF]"></div>
          <h3 className="text-base font-bold text-[#1E293B] m-0">
            Results for <span className="text-[#0084FF]">"{query}"</span>
          </h3>
          <span className="neu-recessed px-2.5 py-0.5 rounded-full text-xs font-semibold text-[#64748B]">
            {results.length} found
          </span>

          {/* Model Attribution Pill */}
          <button
            type="button"
            onClick={onOpenModelModal}
            className="neu-recessed px-2.5 py-1 rounded-full text-[11px] font-bold text-[#0084FF] hover:text-[#0074E0] cursor-pointer inline-flex items-center gap-1.5 transition-colors"
            title="Our Search Model: Scored and ranked by KON Search 1 Rei (Click for model architecture & live weights)"
          >
            <Cpu className="w-3 h-3 text-[#0084FF]" />
            <span>Ranked by KON Search 1 Rei</span>
          </button>
        </div>

        <button
          onClick={onDismiss}
          className="neu-raised p-2 text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl"
          title="Dismiss search results"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Candidate List */}
      <div className="space-y-3.5">
        {results.map((cand, idx) => {
          const isTopRanked = idx === 0;
          const isReported = reportedIds.has(cand.id);

          return (
            <div
              key={cand.id}
              className={`p-4 rounded-2xl transition-all ${
                isTopRanked
                  ? "neu-raised border border-[#0084FF]/25"
                  : "neu-raised"
              } flex flex-col md:flex-row items-start md:items-center justify-between gap-4`}
            >
              {/* Media Info */}
              <div className="flex items-start gap-4 min-w-0 flex-1">
                {/* Thumbnail */}
                <div className="w-16 h-16 rounded-xl neu-recessed p-1 shrink-0 overflow-hidden flex items-center justify-center">
                  {cand.thumbnail ? (
                    <img
                      src={cand.thumbnail}
                      alt={cand.title}
                      className="w-full h-full object-cover rounded-lg"
                      referrerPolicy="no-referrer"
                    />
                  ) : (
                    <Music className="w-6 h-6 text-[#0084FF]" />
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    {isTopRanked && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-[#0084FF]">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Top Match
                      </span>
                    )}
                    <span className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wide">
                      {cand.platform}
                    </span>
                  </div>

                  <h4
                    className="text-sm font-bold text-[#1E293B] truncate m-0"
                    title={cand.title}
                  >
                    {cand.title}
                  </h4>

                  <div className="flex flex-wrap items-center gap-3 mt-1.5 text-xs text-[#64748B] font-medium">
                    {cand.uploader && (
                      <span className="flex items-center gap-1">
                        <User className="w-3.5 h-3.5 text-[#94A3B8]" />
                        <span className="truncate max-w-[180px]">{cand.uploader}</span>
                      </span>
                    )}
                    {cand.duration && (
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5 text-[#94A3B8]" />
                        <span>{formatDuration(cand.duration)}</span>
                      </span>
                    )}
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-wrap items-center gap-2.5 shrink-0 self-stretch sm:self-end md:self-center justify-end">
                {/* Download Song Button */}
                <button
                  type="button"
                  onClick={() => onDirectDownload(cand, "audio")}
                  className="neu-accent px-4 py-2.5 flex items-center gap-2 text-xs font-semibold cursor-pointer rounded-xl"
                  title="Direct 1-click download as MP3 audio"
                >
                  <Music className="w-3.5 h-3.5" />
                  <span>Download Song</span>
                </button>

                {/* Video Button */}
                <button
                  type="button"
                  onClick={() => onDirectDownload(cand, "video")}
                  className="neu-raised px-3.5 py-2.5 flex items-center gap-1.5 text-xs font-semibold text-[#334155] hover:text-[#0084FF] cursor-pointer rounded-xl"
                  title="Direct 1-click download as MP4 video"
                >
                  <Film className="w-3.5 h-3.5" />
                  <span>Video</span>
                </button>

                {/* Format Inspector */}
                <button
                  type="button"
                  onClick={() => onSelectCandidate(cand)}
                  className="neu-raised p-2.5 text-xs text-[#64748B] hover:text-[#0084FF] cursor-pointer rounded-xl"
                  title="Open format options & stream pairing"
                >
                  <SlidersHorizontal className="w-3.5 h-3.5" />
                </button>

                {/* Report Mismatch */}
                <button
                  type="button"
                  onClick={(e) => handleReportMismatch(e, cand)}
                  disabled={isReported}
                  className={`neu-raised p-2.5 text-xs rounded-xl cursor-pointer ${
                    isReported
                      ? "opacity-40 cursor-not-allowed text-[#EF4444]"
                      : "text-[#94A3B8] hover:text-[#EF4444]"
                  }`}
                  title={isReported ? "Reported" : "Flag as irrelevant"}
                >
                  <ThumbsDown className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
