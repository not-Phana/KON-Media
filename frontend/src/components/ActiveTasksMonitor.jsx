import React, { useState, useCallback } from "react";
import {
  ArrowDown,
  Loader2,
  CheckCircle2,
  AlertCircle,
  XCircle,
  Ban,
  FolderOpen,
  Download,
  X,
  RotateCcw,
  Trash2,
  Sparkles,
  Clock,
  Film,
  Music,
} from "lucide-react";
import { getDownloadUrl } from "../api";

const getPlatformInfo = (url) => {
  if (!url) return { name: "Web", color: "#64748B" };
  const lower = url.toLowerCase();
  if (lower.includes("youtube.com") || lower.includes("youtu.be")) {
    return { name: "YouTube", color: "#EF4444" };
  }
  if (lower.includes("spotify.com")) {
    return { name: "Spotify Match", color: "#10B981" };
  }
  if (lower.includes("soundcloud.com")) {
    return { name: "SoundCloud", color: "#F97316" };
  }
  if (lower.includes("bandcamp.com")) {
    return { name: "Bandcamp", color: "#00A0DC" };
  }
  if (lower.includes("vimeo.com")) {
    return { name: "Vimeo", color: "#1AB7EA" };
  }
  return { name: "Media Source", color: "#0084FF" };
};

const getFormatBadge = (task) => {
  const isAudio = task.media_type === "audio";
  const ext = (task.ext || (isAudio ? "mp3" : "mp4")).toUpperCase();
  const isMerged = task.format_id && String(task.format_id).includes("+");

  if (isAudio) {
    if (task.audio_bitrate) {
      return `${ext} · ${task.audio_bitrate}k`;
    }
    return `${ext} Audio`;
  }
  if (isMerged || task.substate === "merging") {
    return `Merged ${ext}`;
  }
  return `${ext} Video`;
};

const formatBytes = (bytes) => {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
};

const formatSpeed = (bytesPerSec) => {
  if (!bytesPerSec || bytesPerSec <= 0) return "";
  return `${formatBytes(bytesPerSec)}/s`;
};

const formatEta = (seconds) => {
  if (seconds === null || seconds === undefined || seconds < 0) return "";
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
};

const TaskCard = React.memo(function TaskCard({
  task,
  onCancelTask,
  onOpenFile,
  onDismissTask,
  onRetryTask,
  openingTaskId,
  onOpenFolderClick,
}) {
  const isOngoing =
    task.status === "downloading" ||
    task.status === "processing" ||
    task.status === "verifying" ||
    task.status === "queued";
  const isProcessing = task.status === "processing" || task.status === "verifying";
  const percent = Math.min(100, Math.max(0, task.percentage || 0));
  const platform = getPlatformInfo(task.url);
  const formatLabel = getFormatBadge(task);

  const getStatusBadge = () => {
    switch (task.status) {
      case "queued":
        return (
          <span className="neu-recessed px-2.5 py-1 rounded-full text-xs font-semibold text-[#F59E0B] inline-flex items-center gap-1.5">
            <Clock className="w-3 h-3 animate-pulse text-[#F59E0B]" />
            Queued
          </span>
        );
      case "downloading":
        return (
          <span className="neu-recessed px-2.5 py-1 rounded-full text-xs font-semibold text-[#0084FF] inline-flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin text-[#0084FF]" />
            Downloading
          </span>
        );
      case "processing":
        return (
          <span className="neu-recessed px-2.5 py-1 rounded-full text-xs font-semibold text-[#F59E0B] inline-flex items-center gap-1.5">
            <Sparkles className="w-3 h-3 animate-spin text-[#F59E0B]" />
            Merging Streams
          </span>
        );
      case "verifying":
        return (
          <span className="neu-recessed px-2.5 py-1 rounded-full text-xs font-semibold text-[#0084FF] inline-flex items-center gap-1.5">
            <Loader2 className="w-3 h-3 animate-spin text-[#0084FF]" />
            Verifying
          </span>
        );
      case "completed":
        return (
          <span className="neu-recessed px-2.5 py-1 rounded-full text-xs font-semibold text-[#10B981] inline-flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5 text-[#10B981]" />
            Ready
          </span>
        );
      case "failed":
        return (
          <span className="neu-recessed px-2.5 py-1 rounded-full text-xs font-semibold text-[#EF4444] inline-flex items-center gap-1.5">
            <AlertCircle className="w-3 h-3 text-[#EF4444]" />
            Failed
          </span>
        );
      case "cancelled":
        return (
          <span className="neu-recessed px-2.5 py-1 rounded-full text-xs font-semibold text-[#64748B] inline-flex items-center gap-1.5">
            <Ban className="w-3 h-3 text-[#64748B]" />
            Cancelled
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="neu-raised p-4 rounded-2xl space-y-3 transition-colors duration-200 neu-card-hover neu-stagger-item">
      <div className="flex items-start justify-between gap-3">
        {/* Left: Thumbnail & Media Info */}
        <div className="flex items-start gap-3.5 min-w-0 flex-1">
          <div className="w-14 h-14 rounded-xl neu-recessed p-1 flex items-center justify-center shrink-0 overflow-hidden">
            {task.thumbnail ? (
              <img
                src={task.thumbnail}
                alt={task.title}
                className="w-full h-full object-cover rounded-lg"
                referrerPolicy="no-referrer"
              />
            ) : task.media_type === "audio" ? (
              <Music className="w-5 h-5 text-[#0084FF]" />
            ) : (
              <Film className="w-5 h-5 text-[#0084FF]" />
            )}
          </div>

          <div className="min-w-0 flex-1">
            <h3
              className="text-sm font-bold text-[#1E293B] truncate m-0 leading-tight"
              title={task.title}
            >
              {task.title}
            </h3>

            {/* Badges & Meta */}
            <div className="flex flex-wrap items-center gap-2 mt-1.5 text-xs text-[#64748B] font-medium">
              <span
                className="font-semibold uppercase tracking-wider text-[11px]"
                style={{ color: platform.color }}
              >
                {platform.name}
              </span>

              <span>·</span>
              <span className="neu-recessed px-2 py-0.5 rounded-md text-[11px] font-semibold text-[#334155]">
                {formatLabel}
              </span>

              {task.status === "downloading" && (
                <>
                  {task.speed > 0 && <span>· {formatSpeed(task.speed)}</span>}
                  {task.eta !== null && task.eta !== undefined && (
                    <span>· ETA {formatEta(task.eta)}</span>
                  )}
                  {task.total_bytes > 0 && (
                    <span>
                      · {formatBytes(task.downloaded_bytes)} / {formatBytes(task.total_bytes)}
                    </span>
                  )}
                </>
              )}

              {task.status === "completed" && task.total_bytes > 0 && (
                <span>· {formatBytes(task.total_bytes)}</span>
              )}
            </div>
          </div>
        </div>

        {/* Right: Status Badge & Actions */}
        <div className="flex items-center gap-2 shrink-0">
          {getStatusBadge()}

          {/* Active cancel action */}
          {isOngoing && onCancelTask && (
            <button
              onClick={() => onCancelTask(task.id)}
              className="neu-raised p-2 text-xs text-[#EF4444] cursor-pointer rounded-xl"
              title="Cancel download"
            >
              <XCircle className="w-4 h-4" />
            </button>
          )}

          {/* Completed file actions */}
          {task.status === "completed" && (
            <>
              {task.filename && (
                <a
                  href={getDownloadUrl(task.filename)}
                  download={task.filename}
                  className="neu-accent flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold cursor-pointer no-underline rounded-xl"
                  title="Save to browser downloads"
                >
                  <Download className="w-3.5 h-3.5 text-white" />
                  <span>Save</span>
                </a>
              )}

              {task.file_path && onOpenFile && (
                <button
                  onClick={() => onOpenFolderClick(task.file_path, task.id)}
                  disabled={openingTaskId === task.id}
                  className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#334155] hover:text-[#0084FF] cursor-pointer disabled:opacity-50 rounded-xl"
                  title="Show in Windows File Explorer"
                >
                  <FolderOpen className="w-3.5 h-3.5 text-[#0084FF]" />
                  <span>{openingTaskId === task.id ? "Opening..." : "Folder"}</span>
                </button>
              )}
            </>
          )}

          {/* Failed / Cancelled retry action */}
          {(task.status === "failed" || task.status === "cancelled") && onRetryTask && (
            <button
              onClick={() => onRetryTask(task.id)}
              className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#0084FF] cursor-pointer rounded-xl"
              title="Retry download task"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Retry</span>
            </button>
          )}

          {/* Dismiss action for non-ongoing tasks */}
          {!isOngoing && onDismissTask && (
            <button
              onClick={() => onDismissTask(task.id)}
              className="neu-raised p-2 text-[#94A3B8] hover:text-[#1E293B] cursor-pointer rounded-xl"
              title="Dismiss from queue"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Progress Bar & Substate Message */}
      {isOngoing && (
        <div className="space-y-2 pt-1">
          <div className="neu-recessed h-2.5 overflow-hidden p-0.5 rounded-full">
            {isProcessing ? (
              <div className="h-full bg-gradient-to-r from-[#F59E0B] to-[#0084FF] rounded-full animate-pulse w-full" />
            ) : task.status === "queued" ? (
              <div className="h-full bg-[#F59E0B]/40 rounded-full animate-pulse w-1/4" />
            ) : (
              <div
                className="h-full bg-[#0084FF] rounded-full transition-all duration-200"
                style={{ width: `${percent}%` }}
              />
            )}
          </div>

          <div className="flex items-center justify-between text-xs text-[#64748B] font-medium">
            <span className="truncate pr-2">
              {task.status === "processing"
                ? task.substate_message || "Merging video and audio streams..."
                : task.status === "verifying"
                ? task.substate_message || "Verifying download integrity..."
                : task.status === "queued"
                ? "Waiting in queue..."
                : `${percent.toFixed(1)}% downloaded`}
            </span>
            <span className="shrink-0 text-[#1E293B] font-bold">
              {task.status === "downloading" ? `${percent.toFixed(1)}%` : ""}
            </span>
          </div>
        </div>
      )}

      {/* Actionable Error Box */}
      {task.status === "failed" && task.error && (
        <div className="p-3.5 rounded-xl bg-[#FEE2E2]/60 border border-[#FCA5A5] text-[#DC2626] text-xs font-medium leading-relaxed">
          <div className="flex items-center gap-1.5 font-bold mb-1 text-[#DC2626]">
            <AlertCircle className="w-3.5 h-3.5 shrink-0" />
            <span>Download Error:</span>
          </div>
          <p className="m-0 text-[11px] text-[#DC2626]/90">{task.error}</p>
        </div>
      )}
    </div>
  );
});

export default function ActiveTasksMonitor({
  tasks,
  onCancelTask,
  onOpenFile,
  onDismissTask,
  onRetryTask,
  onClearFinished,
}) {
  const [openingTaskId, setOpeningTaskId] = useState(null);

  const handleOpenFolderClick = useCallback(
    async (filePath, taskId) => {
      setOpeningTaskId(taskId);
      try {
        await onOpenFile(filePath);
      } finally {
        setTimeout(() => setOpeningTaskId(null), 1200);
      }
    },
    [onOpenFile]
  );

  if (!tasks || tasks.length === 0) return null;

  const activeCount = tasks.filter((t) =>
    ["queued", "downloading", "processing", "verifying"].includes(t.status)
  ).length;
  const finishedCount = tasks.length - activeCount;

  return (
    <section className="neu-card p-6 space-y-4">
      {/* Dynamic Queue Header */}
      <div className="flex items-center justify-between gap-3 pb-1">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-[#0084FF]"></div>
          <h2 className="text-base font-bold text-[#1E293B] m-0">
            Active Queue
          </h2>

          {activeCount > 0 && (
            <span className="neu-recessed px-3 py-1 rounded-full text-xs font-semibold text-[#0084FF]">
              {activeCount} active
            </span>
          )}

          {finishedCount > 0 && (
            <span className="neu-recessed px-3 py-1 rounded-full text-xs font-semibold text-[#64748B]">
              {finishedCount} finished
            </span>
          )}
        </div>

        {finishedCount > 0 && onClearFinished && (
          <button
            onClick={onClearFinished}
            className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl"
            title="Clear all completed, failed, and cancelled tasks from queue"
          >
            <Trash2 className="w-3.5 h-3.5" />
            <span>Clear Finished</span>
          </button>
        )}
      </div>

      {/* Task Cards List */}
      <div className="space-y-3">
        {tasks.map((task) => (
          <TaskCard
            key={task.id}
            task={task}
            onCancelTask={onCancelTask}
            onOpenFile={onOpenFile}
            onDismissTask={onDismissTask}
            onRetryTask={onRetryTask}
            openingTaskId={openingTaskId}
            onOpenFolderClick={handleOpenFolderClick}
          />
        ))}
      </div>
    </section>
  );
}
