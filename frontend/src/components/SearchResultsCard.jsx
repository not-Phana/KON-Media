import { KonFlashIcon, KonPrecisionIcon } from "./KonIcons";
import React, { useState } from "react";
import {
  Play,
  Pause,
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
  Zap,
  Loader2,
  AlertCircle,
  FolderOpen,
} from "lucide-react";

/**
 * Matches a search candidate item against an active task or history item.
 */
function isCandidateTaskMatch(cand, task, mediaType) {
  if (!cand || !task) return false;
  const taskMediaType = task.media_type || "video";
  if (taskMediaType !== mediaType) return false;
  if (task.url && cand.url && task.url === cand.url) return true;
  if (cand.id && cand.id.length >= 5 && task.url && (task.url.includes(cand.id) || task.id === cand.id)) {
    return true;
  }
  return false;
}

/**
 * Interactive Download Action Button for Songs (Audio) or Video
 * Displays real-time states: Idle -> Queued -> Downloading (with % and live fill bar) -> Processing -> Downloaded (with open folder) / Retry
 */
function DownloadActionButton({
  candidate,
  mediaType,
  statusInfo,
  onDownload,
  onOpenFile,
  isPrimary = false,
}) {
  const isAudio = mediaType === "audio";
  const { status, percent = 0, filePath } = statusInfo;
  const isSong = candidate.is_music !== false && candidate.content_type !== "video";
  const itemTypeLabel = isAudio ? (isSong ? "Song" : "Audio") : "Video";

  // 1. Queued / Starting state (instant click feedback)
  if (status === "starting" || status === "queued") {
    return (
      <button
        type="button"
        disabled
        className="neu-recessed px-3.5 py-2.5 flex items-center gap-2 text-xs font-bold text-[#0084FF] rounded-xl cursor-not-allowed select-none border border-[#0084FF]/30 animate-pulse"
        title={isAudio ? `Preparing ${itemTypeLabel.toLowerCase()} download...` : "Preparing video download..."}
      >
        <Loader2 className="w-3.5 h-3.5 animate-spin text-[#0084FF] shrink-0" />
        <span>Queued...</span>
      </button>
    );
  }

  // 2. Actively Downloading state with live percentage & animated fill track
  if (status === "downloading") {
    return (
      <div
        className={`relative overflow-hidden rounded-xl neu-recessed border border-[#0084FF]/40 flex items-center ${
          isAudio ? "min-w-[140px]" : "min-w-[125px]"
        }`}
        title={`Downloading ${itemTypeLabel.toLowerCase()}: ${percent}%`}
      >
        {/* Progress fill bar */}
        <div
          className="absolute inset-y-0 left-0 bg-[#0084FF]/25 transition-all duration-300 ease-out"
          style={{ width: `${percent}%` }}
        />
        <div className="relative px-3.5 py-2.5 flex items-center gap-2 text-xs font-bold text-[#0084FF] select-none z-10 w-full justify-center">
          <Loader2 className="w-3.5 h-3.5 animate-spin shrink-0 text-[#0084FF]" />
          <span>{isAudio ? (isSong ? "Downloading Song" : "Downloading Audio") : "Downloading Video"} {percent > 0 ? `${percent}%` : "..."}</span>
        </div>
      </div>
    );
  }

  // 3. Processing / Converting / Verifying state
  if (status === "processing" || status === "verifying") {
    return (
      <div
        className="neu-recessed px-3.5 py-2.5 rounded-xl flex items-center gap-2 text-xs font-bold text-[#F59E0B] border border-[#F59E0B]/30 select-none animate-pulse"
        title={isAudio ? "Encoding high-quality MP3 audio..." : "Merging video & audio streams..."}
      >
        <Sparkles className="w-3.5 h-3.5 animate-spin text-[#F59E0B] shrink-0" />
        <span>{isAudio ? "Converting MP3..." : "Merging streams..."}</span>
      </div>
    );
  }

  // 4. Completed / Downloaded state with quick folder reveal & re-download
  if (status === "completed") {
    return (
      <div className="flex items-center gap-1.5 animate-fade-in">
        <button
          type="button"
          onClick={() => filePath && onOpenFile && onOpenFile(filePath)}
          className="neu-recessed px-3.5 py-2.5 flex items-center gap-2 text-xs font-bold text-[#10B981] rounded-xl border border-[#10B981]/35 hover:border-[#10B981]/60 hover:bg-[#10B981]/10 transition-all cursor-pointer group shadow-[0_0_12px_rgba(16,185,129,0.15)]"
          title={`${itemTypeLabel} downloaded! Click to reveal in folder`}
        >
          <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981] shrink-0" />
          <span>{isAudio ? (isSong ? "Song Ready" : "Audio Ready") : "MP4 Ready"}</span>
          <FolderOpen className="w-3 h-3 text-[#10B981] opacity-75 group-hover:opacity-100 transition-opacity ml-0.5" />
        </button>
        <button
          type="button"
          onClick={() => onDownload(candidate, mediaType, true)}
          className="neu-raised p-2.5 text-[#64748B] hover:text-[#0084FF] rounded-xl cursor-pointer text-xs transition-colors"
          title={`Download ${isAudio ? (isSong ? "Song (MP3)" : "Audio (MP3)") : "Video (MP4)"} again`}
        >
          <Download className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }

  // 5. Failed state with retry option
  if (status === "failed") {
    return (
      <button
        type="button"
        onClick={() => onDownload(candidate, mediaType, true)}
        className="neu-raised px-3.5 py-2.5 flex items-center gap-1.5 text-xs font-semibold text-[#EF4444] rounded-xl cursor-pointer hover:bg-red-500/10 border border-red-500/20 transition-all"
        title="Download failed. Click to retry"
      >
        <AlertCircle className="w-3.5 h-3.5 text-[#EF4444] shrink-0" />
        <span>Retry {itemTypeLabel}</span>
      </button>
    );
  }

  // 6. Default idle button
  const primaryClass = "neu-accent px-4 py-2.5 flex items-center gap-2 text-xs font-semibold cursor-pointer rounded-xl hover:brightness-110 active:scale-95 transition-all shadow-[0_4px_12px_rgba(0,132,255,0.25)]";
  const secondaryClass = "neu-raised px-3.5 py-2.5 flex items-center gap-1.5 text-xs font-semibold text-[#334155] dark:text-[#CBD5E1] hover:text-[#0084FF] cursor-pointer rounded-xl active:scale-95 transition-all";

  if (isAudio) {
    const label = isSong ? "Download Song" : "Download Audio";
    return (
      <button
        type="button"
        onClick={() => onDownload(candidate, "audio")}
        className={isPrimary ? primaryClass : secondaryClass}
        title={isSong ? "Direct 1-click download as MP3 song" : "Extract & download audio as MP3"}
      >
        <Music className="w-3.5 h-3.5" />
        <span>{label}</span>
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={() => onDownload(candidate, "video")}
      className={isPrimary ? primaryClass : secondaryClass}
      title="Direct 1-click download as MP4 video"
    >
      <Film className="w-3.5 h-3.5" />
      <span>{isPrimary ? "Download Video" : "Video"}</span>
    </button>
  );
}

export default function SearchResultsCard({
  query,
  results,
  searchMode = "audio",
  engineMode = "rei",
  searchState = "complete",
  searchStage = null,
  searchMeta = null,
  activeTasks = [],
  history = [],
  onOpenFile,
  onSelectCandidate,
  onDirectDownload,
  onDismiss,
  onFeedback,
  onOpenModelModal,
  onPlayCandidate,
  currentPlayingTrack,
  isPlaying = false,
  isLoadingAudio = false,
}) {
  const [reportedIds, setReportedIds] = useState(new Set());
  const [localPending, setLocalPending] = useState({});

  const isFlash =
    engineMode === "flash" ||
    searchMeta?.engine_mode === "flash" ||
    searchMeta?.model?.includes("Flash") ||
    results?.[0]?.engine_mode === "flash" ||
    results?.[0]?.model?.includes("Flash");

  // Helper to resolve live status for candidate & mediaType
  const getCandidateStatus = (cand, mediaType) => {
    const key = `${cand.id || cand.url}_${mediaType}`;
    const pending = localPending[key];

    // 1. Check live active tasks (SSE-updated)
    const activeTask = activeTasks?.find((t) => isCandidateTaskMatch(cand, t, mediaType));
    if (activeTask) {
      return {
        status: activeTask.status, // 'queued', 'downloading', 'processing', 'verifying', 'completed', 'failed', 'cancelled'
        percent: Math.min(100, Math.max(0, Math.round(activeTask.percentage || 0))),
        stage: activeTask.stage,
        filePath: activeTask.file_path,
        task: activeTask,
      };
    }

    // 2. Check local pending state (instant click responsiveness)
    if (pending) {
      if (pending.status === "starting" || pending.status === "queued") {
        return {
          status: pending.status,
          percent: pending.percent || 0,
          task: null,
        };
      }
      if (pending.status === "failed") {
        return {
          status: "failed",
          percent: 0,
          error: pending.error,
          task: null,
        };
      }
    }

    // 3. Check persistent history for completed downloads
    const historyItem = history?.find(
      (h) => isCandidateTaskMatch(cand, h, mediaType) && h.status === "completed"
    );
    if (historyItem) {
      return {
        status: "completed",
        percent: 100,
        filePath: historyItem.file_path,
        task: historyItem,
        fromHistory: true,
      };
    }

    return { status: "idle" };
  };

  const handleDownloadClick = async (cand, mediaType, isRetry = false) => {
    const key = `${cand.id || cand.url}_${mediaType}`;
    if (
      !isRetry &&
      (localPending[key]?.status === "starting" || localPending[key]?.status === "queued")
    ) {
      return; // Prevent duplicate rapid clicks
    }

    // Optimistically mark starting immediately
    setLocalPending((prev) => ({
      ...prev,
      [key]: { status: "starting", percent: 0, timestamp: Date.now() },
    }));

    try {
      const res = await onDirectDownload(cand, mediaType);
      if (res?.task_id) {
        setLocalPending((prev) => ({
          ...prev,
          [key]: { status: "queued", taskId: res.task_id, percent: 0, timestamp: Date.now() },
        }));
      }
    } catch (err) {
      setLocalPending((prev) => ({
        ...prev,
        [key]: { status: "failed", error: err.message || "Could not queue download" },
      }));
    }
  };

  // Distinct lifecycle state: actively querying providers with zero results arrived yet
  if ((searchState === "searching" || searchState === "updating") && (!results || results.length === 0)) {
    const details = searchStage?.details || {};
    return (
      <div className="neu-card p-6 space-y-4 animate-fade-in">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Loader2 className="w-5 h-5 text-[#0084FF] animate-spin shrink-0" />
            <div>
              <h3 className="text-sm font-bold text-[#1E293B] dark:text-[#E2E8F0] m-0">
                {searchStage?.stage === "understanding" && "Understanding your search..."}
                {searchStage?.stage === "searching" && "Searching providers..."}
                {searchStage?.stage === "collecting" && "Collecting candidates..."}
                {(searchStage?.stage === "matching" || searchStage?.stage === "ranking") && "Matching & ranking results..."}
                {!searchStage?.stage && `Searching for "${query}"`}
              </h3>
              <p className="text-[11px] text-[#64748B] dark:text-[#94A3B8] font-medium m-0 mt-0.5">
                {searchStage?.message || "Querying YouTube, SoundCloud & media providers concurrently..."}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onOpenModelModal}
            className={`neu-recessed px-2.5 py-1 rounded-full text-[11px] font-bold cursor-pointer inline-flex items-center gap-1.5 transition-colors ${
              isFlash ? "text-[#F59E0B] hover:text-[#D97706]" : "text-[#0084FF] hover:text-[#0074E0]"
            }`}
          >
            {isFlash ? <Zap className="w-3 h-3 text-[#F59E0B]" /> : <Cpu className="w-3 h-3 text-[#0084FF]" />}
            <span>{isFlash ? "KON Search 1.2 Rei Flash" : "KON Search 1.2 Rei"}</span>
          </button>
        </div>

        {/* Structured Query Intent Badges if detected */}
        {(details.detected_title || details.detected_artist || details.version_hint || details.qualifier) && (
          <div className="flex flex-wrap items-center gap-1.5 pt-1">
            {details.detected_title && (
              <span className="neu-recessed px-2.5 py-0.5 rounded-full text-[10px] font-bold text-[#0084FF]">
                Title: {details.detected_title}
              </span>
            )}
            {details.detected_artist && (
              <span className="neu-recessed px-2.5 py-0.5 rounded-full text-[10px] font-bold text-[#10B981]">
                Artist: {details.detected_artist}
              </span>
            )}
            {details.version_hint && (
              <span className="neu-recessed px-2.5 py-0.5 rounded-full text-[10px] font-bold text-[#8B5CF6]">
                Type: {details.version_hint}
              </span>
            )}
            {details.qualifier && (
              <span className="neu-recessed px-2.5 py-0.5 rounded-full text-[10px] font-bold text-[#EC4899]">
                Qualifier: {details.qualifier}
              </span>
            )}
          </div>
        )}

        {/* Indeterminate progress bar */}
        <div className="w-full h-1 bg-slate-200/50 dark:bg-slate-700/50 rounded-full overflow-hidden">
          <div className="h-full bg-[#0084FF] rounded-full animate-pulse w-3/4" />
        </div>

        {/* Tactile animated progress skeleton */}
        <div className="space-y-3 pt-1">
          <div className="p-4 rounded-2xl neu-raised flex items-center gap-3 animate-pulse">
            <div className="w-14 h-14 rounded-xl neu-recessed shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3.5 bg-slate-200/60 dark:bg-slate-700/60 rounded-md w-3/4" />
              <div className="h-2.5 bg-slate-200/40 dark:bg-slate-700/40 rounded-md w-1/2" />
            </div>
          </div>
          <div className="p-4 rounded-2xl neu-raised flex items-center gap-3 animate-pulse opacity-75">
            <div className="w-14 h-14 rounded-xl neu-recessed shrink-0" />
            <div className="flex-1 space-y-2">
              <div className="h-3.5 bg-slate-200/60 dark:bg-slate-700/60 rounded-md w-2/3" />
              <div className="h-2.5 bg-slate-200/40 dark:bg-slate-700/40 rounded-md w-1/3" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  // Distinct lifecycle state: search completed with no results found
  if (searchState === "no_results" || !results || results.length === 0) {
    return (
      <div className="neu-card p-6 space-y-3 animate-fade-in">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold text-[#1E293B] dark:text-[#E2E8F0]">
            <Search className="w-4 h-4 text-[#0084FF]" />
            <span>Search Results for "{query}"</span>
          </div>
          <button
            onClick={onDismiss}
            className="neu-raised p-1.5 text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#E2E8F0] cursor-pointer rounded-xl"
            title="Dismiss search results"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
        <p className="text-xs text-[#64748B] dark:text-[#94A3B8] m-0 font-medium">
          No good matches found for "{query}". The search completed across queried providers, but no sufficiently relevant candidate songs were identified. Try a different title or paste a direct URL.
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
            className={`neu-recessed px-2.5 py-1 rounded-full text-[11px] font-bold cursor-pointer inline-flex items-center gap-1.5 transition-colors ${
              isFlash ? "text-[#F59E0B] hover:text-[#D97706]" : "text-[#0084FF] hover:text-[#0074E0]"
            }`}
            title={
              isFlash
                ? "Active Search Engine: Ranked by KON Search 1.2 Rei Flash (Speed mode)"
                : "Active Search Engine: Ranked by KON Search 1.2 Rei (Precision mode)"
            }
          >
            {isFlash ? <KonFlashIcon className="w-3.5 h-3.5" /> : <KonPrecisionIcon className="w-3.5 h-3.5" />}
            <span>Ranked by {isFlash ? "KON Search 1.2 Rei Flash" : "KON Search 1.2 Rei"}</span>
            <span className="text-[10px] opacity-80 font-mono inline-flex items-center gap-1">
              {isFlash ? (
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
        </div>

        <button
          onClick={onDismiss}
          className="neu-raised p-2 text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl"
          title="Dismiss search results"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Live Stream Active Status Banner */}
      {(searchState === "updating" || searchState === "searching") && (
        <div className="neu-recessed p-3 rounded-2xl flex items-center justify-between gap-3 animate-fade-in border border-[#0084FF]/20">
          <div className="flex items-center gap-2.5 min-w-0">
            <Loader2 className="w-4 h-4 text-[#0084FF] animate-spin shrink-0" />
            <div className="min-w-0">
              <p className="text-xs font-bold text-[#0084FF] m-0 truncate">
                {searchStage?.message || "Updating live results..."}
              </p>
              <p className="text-[10px] text-[#64748B] dark:text-[#94A3B8] m-0 font-medium">
                {searchStage?.providers_pending?.length
                  ? `Still querying: ${searchStage.providers_pending.join(", ")}`
                  : "Streaming new candidates directly into view"}
              </p>
            </div>
          </div>
          <span className="neu-raised px-2.5 py-0.5 rounded-full text-[10px] font-extrabold text-[#0084FF] uppercase tracking-wider shrink-0">
            Live Stream
          </span>
        </div>
      )}

      {/* Partial Provider Timeout Banner */}
      {searchMeta?.timedOut?.length > 0 && (
        <div className="neu-recessed px-3 py-2 rounded-xl text-[11px] text-[#F59E0B] flex items-center justify-between gap-2 font-medium">
          <span>Note: {searchMeta.timedOut.join(", ")} timed out; displaying available candidates.</span>
        </div>
      )}

      {/* Candidate List */}
      <div className="space-y-3.5">
        {results.map((cand, idx) => {
          const isTopRanked = idx === 0;
          const isReported = reportedIds.has(cand.id);

          const audioStatus = getCandidateStatus(cand, "audio");
          const videoStatus = getCandidateStatus(cand, "video");
          const isCandidateDownloading =
            audioStatus.status === "downloading" ||
            videoStatus.status === "downloading" ||
            audioStatus.status === "starting" ||
            videoStatus.status === "starting" ||
            audioStatus.status === "queued" ||
            videoStatus.status === "queued" ||
            audioStatus.status === "processing" ||
            videoStatus.status === "processing";
          const isCandidateCompleted =
            (audioStatus.status === "completed" || videoStatus.status === "completed") &&
            !isCandidateDownloading;

          let cardBorderClass = "neu-raised";
          if (isCandidateDownloading) {
            cardBorderClass = "neu-raised border border-[#0084FF]/40 shadow-[0_0_15px_rgba(0,132,255,0.12)]";
          } else if (isCandidateCompleted) {
            cardBorderClass = "neu-raised border border-[#10B981]/35 shadow-[0_0_12px_rgba(16,185,129,0.08)]";
          } else if (isTopRanked) {
            cardBorderClass = "neu-raised border border-[#0084FF]/25";
          }

          return (
            <div
              key={cand.id}
              className={`p-4 rounded-2xl transition-all ${cardBorderClass} flex flex-col md:flex-row items-start md:items-center justify-between gap-4`}
            >
              {/* Media Info */}
              <div className="flex items-start gap-4 min-w-0 flex-1">
                {/* Thumbnail */}
                <div className="w-16 h-16 rounded-xl neu-recessed p-1 shrink-0 overflow-hidden flex items-center justify-center relative">
                  {cand.thumbnail ? (
                    <img
                      src={cand.thumbnail}
                      alt={cand.title}
                      className="w-full h-full object-cover rounded-lg"
                      referrerPolicy="no-referrer"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                        const fallback = e.currentTarget.parentElement?.querySelector(".cand-icon-fallback");
                        if (fallback) fallback.classList.remove("hidden");
                      }}
                    />
                  ) : null}
                  <div
                    className={`cand-icon-fallback w-full h-full flex items-center justify-center ${
                      cand.thumbnail ? "hidden" : ""
                    }`}
                  >
                    {cand.content_type === "video" || cand.is_music === false ? (
                      <Film className="w-6 h-6 text-[#EF4444]" />
                    ) : (
                      <Music className="w-6 h-6 text-[#0084FF]" />
                    )}
                  </div>
                  {/* Small platform chip on thumbnail for videos */}
                  {(cand.content_type === "video" || cand.is_music === false) && (
                    <span className="absolute bottom-1 right-1 bg-[#EF4444] text-[8px] font-black text-white px-1 py-0.2 rounded shadow-sm">
                      {cand.platform === "youtube" ? "YT" : "VID"}
                    </span>
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2 mb-1">
                    {isTopRanked && (
                      <span className="inline-flex items-center gap-1 text-[11px] font-bold text-[#0084FF]">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Top Match
                      </span>
                    )}

                    {/* Platform & Media Type Badge */}
                    {cand.content_type === "soundtrack" ? (
                      <span className="inline-flex items-center gap-1 neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#0084FF] border border-[#0084FF]/25 bg-[#0084FF]/5">
                        <Music className="w-3 h-3 text-[#0084FF]" />
                        <span>Soundtrack</span>
                      </span>
                    ) : (cand.is_music === false || cand.content_type === "video") ? (
                      <span className="inline-flex items-center gap-1 neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#EF4444] border border-[#EF4444]/25 bg-[#EF4444]/5">
                        <Film className="w-3 h-3 text-[#EF4444]" />
                        <span>{cand.platform === "youtube" ? "YouTube Video" : "Video"}</span>
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#10B981] border border-[#10B981]/25 bg-[#10B981]/5">
                        <Music className="w-3 h-3 text-[#10B981]" />
                        <span>Song</span>
                      </span>
                    )}

                    <span className="text-[11px] font-semibold text-[#64748B] uppercase tracking-wide">
                      {cand.platform}
                    </span>
                    {cand.context_source && (
                      <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#0084FF] truncate max-w-[240px]">
                        {cand.context_source}
                      </span>
                    )}
                    {isCandidateDownloading && (
                      <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#0084FF] inline-flex items-center gap-1">
                        <Loader2 className="w-3 h-3 animate-spin text-[#0084FF]" />
                        Active Download
                      </span>
                    )}
                    {isCandidateCompleted && (
                      <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#10B981] inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3 text-[#10B981]" />
                        Saved
                      </span>
                    )}
                  </div>

                  <h4
                    className="text-sm font-bold text-[#1E293B] truncate m-0"
                    title={cand.is_cluttered && cand.clean_title ? cand.clean_title : cand.title}
                  >
                    {cand.is_cluttered && cand.clean_title ? cand.clean_title : cand.title}
                  </h4>
                  {cand.is_cluttered && cand.clean_title && cand.clean_title !== cand.title && (
                    <p className="text-[11px] text-[#94A3B8] truncate m-0 mt-0.5" title={cand.title}>
                      Original: {cand.title}
                    </p>
                  )}

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
                {/* Built-in Audio Play / Preview Button */}
                {(() => {
                  const isThisPlaying =
                    currentPlayingTrack &&
                    (currentPlayingTrack.id === cand.id || currentPlayingTrack.url === cand.url);
                  const isThisLoading = isThisPlaying && isLoadingAudio;
                  const isSong = cand.is_music !== false && cand.content_type !== "video";

                  return (
                    <button
                      type="button"
                      onClick={() => onPlayCandidate && onPlayCandidate(cand)}
                      className={`px-3.5 py-2.5 flex items-center gap-2 text-xs font-bold rounded-xl cursor-pointer transition-all active:scale-95 ${
                        isThisPlaying && isPlaying
                          ? "neu-recessed text-[#0084FF] border border-[#0084FF]/40 bg-[#0084FF]/10 shadow-[0_0_12px_rgba(0,132,255,0.2)]"
                          : "neu-raised text-[#334155] dark:text-[#CBD5E1] hover:text-[#0084FF] hover:border-[#0084FF]/30"
                      }`}
                      title={
                        isThisPlaying && isPlaying
                          ? "Pause preview playback"
                          : isSong
                          ? "Listen to song preview before downloading"
                          : "Preview audio playback"
                      }
                    >
                      {isThisLoading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-[#0084FF]" />
                      ) : isThisPlaying && isPlaying ? (
                        <Pause className="w-3.5 h-3.5 fill-current text-[#0084FF]" />
                      ) : (
                        <Play className="w-3.5 h-3.5 fill-current text-[#0084FF]" />
                      )}
                      <span>
                        {isThisLoading
                          ? "Loading..."
                          : isThisPlaying && isPlaying
                          ? "Playing"
                          : "Preview"}
                      </span>
                    </button>
                  );
                })()}

                {/* Download Audio / Song Button with Live Feedback */}
                <DownloadActionButton
                  candidate={cand}
                  mediaType="audio"
                  statusInfo={audioStatus}
                  onDownload={handleDownloadClick}
                  onOpenFile={onOpenFile}
                  isPrimary={searchMode !== "video" && (cand.is_music !== false || searchMode === "audio")}
                />

                {/* Video Button with Live Feedback */}
                <DownloadActionButton
                  candidate={cand}
                  mediaType="video"
                  statusInfo={videoStatus}
                  onDownload={handleDownloadClick}
                  onOpenFile={onOpenFile}
                  isPrimary={searchMode === "video" || (cand.is_music === false && searchMode === "all")}
                />

                {/* Format Inspector */}
                <button
                  type="button"
                  onClick={() => onSelectCandidate(cand)}
                  className="neu-raised p-2.5 text-xs text-[#64748B] hover:text-[#0084FF] cursor-pointer rounded-xl transition-colors"
                  title="Open format options & stream pairing"
                >
                  <SlidersHorizontal className="w-3.5 h-3.5" />
                </button>

                {/* Report Mismatch */}
                <button
                  type="button"
                  onClick={(e) => handleReportMismatch(e, cand)}
                  disabled={isReported}
                  className={`neu-raised p-2.5 text-xs rounded-xl cursor-pointer transition-colors ${
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
