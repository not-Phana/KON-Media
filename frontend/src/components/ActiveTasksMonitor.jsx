import React from "react";
import { Loader2, CheckCircle2, AlertCircle, XCircle, Ban, ArrowDown, FolderOpen } from "lucide-react";

export default function ActiveTasksMonitor({ tasks, onCancelTask, onOpenFile }) {
  if (!tasks || tasks.length === 0) return null;

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

  const getStatusBadge = (status) => {
    switch (status) {
      case "queued":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-[#272B32] text-[#A5ABB5] border border-[#383D46]">
            Queued
          </span>
        );
      case "downloading":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-[#1F2E28] text-[#72C69A] border border-[#72C69A]/40">
            <Loader2 className="w-3 h-3 animate-spin" />
            Downloading
          </span>
        );
      case "processing":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-[#2D281E] text-[#E8BE72] border border-[#E8BE72]/40">
            <Loader2 className="w-3 h-3 animate-spin" />
            Merging / FFmpeg
          </span>
        );
      case "completed":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-[#1F2E28] text-[#72C69A] border border-[#72C69A]/40">
            <CheckCircle2 className="w-3 h-3" />
            Completed
          </span>
        );
      case "failed":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-[#2C1D20] text-[#EF8585] border border-[#EF8585]/40">
            <AlertCircle className="w-3 h-3" />
            Failed
          </span>
        );
      case "cancelled":
        return (
          <span className="flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-[#202329] text-[#6B7280] border border-[#2D323B]">
            <Ban className="w-3 h-3" />
            Cancelled
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold text-[#F3F4F6] uppercase tracking-wider flex items-center gap-2 m-0">
        <ArrowDown className="w-4 h-4 text-[#8BC5B0]" />
        <span>Active Queue ({tasks.length})</span>
      </h2>

      <div className="space-y-2.5">
        {tasks.map((task) => {
          const isOngoing = task.status === "downloading" || task.status === "processing" || task.status === "queued";
          const percent = Math.min(100, Math.max(0, task.percentage || 0));

          return (
            <div key={task.id} className="neu-card p-4 space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div className="flex-1 min-w-0">
                  <h3 className="text-sm font-medium text-[#F3F4F6] truncate m-0" title={task.title}>
                    {task.title}
                  </h3>
                  <div className="flex items-center gap-2 mt-1 text-[11px] text-[#A5ABB5] font-mono">
                    <span>{task.media_type === "audio" ? "MP3 Audio" : "MP4 Video"}</span>
                    {task.speed > 0 && <span>· {formatSpeed(task.speed)}</span>}
                    {task.eta && <span>· ETA: {task.eta}s</span>}
                    {task.total_bytes > 0 && (
                      <span>· {formatBytes(task.downloaded_bytes)} / {formatBytes(task.total_bytes)}</span>
                    )}
                  </div>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {getStatusBadge(task.status)}

                  {isOngoing && (
                    <button
                      onClick={() => onCancelTask(task.id)}
                      className="neu-raised p-1.5 text-xs text-[#EF8585] hover:bg-[#2C1D20] cursor-pointer"
                      title="Cancel download"
                    >
                      <XCircle className="w-4 h-4" />
                    </button>
                  )}

                  {task.status === "completed" && task.file_path && (
                    <button
                      onClick={() => onOpenFile(task.file_path)}
                      className="neu-raised flex items-center gap-1 px-2.5 py-1 text-xs text-[#8BC5B0] cursor-pointer"
                      title="Show in Folder"
                    >
                      <FolderOpen className="w-3.5 h-3.5" />
                      <span>Folder</span>
                    </button>
                  )}
                </div>
              </div>

              {/* Progress Bar Trough */}
              {isOngoing && (
                <div className="space-y-1">
                  <div className="neu-recessed h-2.5 overflow-hidden p-0.5">
                    <div
                      className="h-full bg-gradient-to-r from-[#72C69A] to-[#8BC5B0] rounded-sm transition-all duration-300"
                      style={{ width: `${percent}%` }}
                    />
                  </div>
                  <div className="flex justify-between text-[10px] font-mono text-[#6B7280]">
                    <span>{task.status === "processing" ? "Merging audio/video streams..." : "Downloading data"}</span>
                    <span>{percent.toFixed(1)}%</span>
                  </div>
                </div>
              )}

              {/* Error Message */}
              {task.status === "failed" && task.error && (
                <div className="p-2 rounded bg-[#2C1D20] text-[#EF8585] text-xs font-mono">
                  {task.error}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
