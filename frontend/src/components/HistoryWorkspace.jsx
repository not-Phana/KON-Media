import React, { useState } from "react";
import { History, FolderOpen, Trash2, Video, Music, Calendar, HardDrive } from "lucide-react";

export default function HistoryWorkspace({ history, onOpenFile, onDeleteItem, onClearAll }) {
  const [showConfirmClear, setShowConfirmClear] = useState(false);

  const formatBytes = (bytes) => {
    if (!bytes || bytes <= 0) return "--";
    const units = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(1024));
    return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
  };

  const formatDate = (isoStr) => {
    if (!isoStr) return "";
    try {
      const d = new Date(isoStr);
      return d.toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (_) {
      return isoStr;
    }
  };

  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-[#F3F4F6] uppercase tracking-wider flex items-center gap-2 m-0">
          <History className="w-4 h-4 text-[#8BC5B0]" />
          <span>Download History ({history.length})</span>
        </h2>

        {history.length > 0 && (
          <div>
            {showConfirmClear ? (
              <div className="flex items-center gap-2">
                <span className="text-xs text-[#EF8585]">Clear history?</span>
                <button
                  onClick={() => {
                    onClearAll();
                    setShowConfirmClear(false);
                  }}
                  className="px-2 py-1 rounded bg-[#2C1D20] text-[#EF8585] text-xs font-semibold cursor-pointer"
                >
                  Yes, Clear
                </button>
                <button
                  onClick={() => setShowConfirmClear(false)}
                  className="px-2 py-1 rounded bg-[#202329] text-[#A5ABB5] text-xs cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowConfirmClear(true)}
                className="text-xs text-[#6B7280] hover:text-[#EF8585] flex items-center gap-1 cursor-pointer"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear All</span>
              </button>
            )}
          </div>
        )}
      </div>

      {history.length === 0 ? (
        <div className="neu-card p-8 text-center text-[#6B7280] text-sm">
          No downloaded files recorded yet. Completed media downloads will appear here.
        </div>
      ) : (
        <div className="space-y-2">
          {history.map((item) => (
            <div
              key={item.id}
              className="neu-card p-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-3 hover:border-[#383D46] transition-colors"
            >
              <div className="flex items-start sm:items-center gap-3 flex-1 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-[#272B32] border border-[#383D46] flex items-center justify-center text-[#8BC5B0] shrink-0 mt-0.5 sm:mt-0">
                  {item.media_type === "audio" ? (
                    <Music className="w-4 h-4" />
                  ) : (
                    <Video className="w-4 h-4" />
                  )}
                </div>

                <div className="flex-1 min-w-0">
                  <h3
                    className="text-sm font-medium text-[#F3F4F6] truncate m-0"
                    title={item.filename || item.title}
                  >
                    {item.filename || item.title}
                  </h3>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 mt-1 text-[11px] text-[#A5ABB5] font-mono">
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3 h-3 text-[#6B7280]" />
                      {formatDate(item.completed_at || item.created_at)}
                    </span>
                    {item.filesize && (
                      <span className="flex items-center gap-1">
                        <HardDrive className="w-3 h-3 text-[#6B7280]" />
                        {formatBytes(item.filesize)}
                      </span>
                    )}
                    <span className="px-1.5 py-0.2 rounded bg-[#131418] text-[#8BC5B0]">
                      {item.ext?.toUpperCase() || "MEDIA"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                {item.file_path && (
                  <button
                    onClick={() => onOpenFile(item.file_path)}
                    className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#F3F4F6] hover:text-[#8BC5B0] cursor-pointer"
                    title="Open in Windows File Explorer"
                  >
                    <FolderOpen className="w-3.5 h-3.5 text-[#8BC5B0]" />
                    <span>Open in Folder</span>
                  </button>
                )}

                <button
                  onClick={() => onDeleteItem(item.id)}
                  className="text-[#6B7280] hover:text-[#EF8585] p-1.5 cursor-pointer"
                  title="Remove from history"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
