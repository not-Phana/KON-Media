import React, { useState } from "react";
import { History, FolderOpen, Trash2, Video, Music, Calendar, HardDrive, Download } from "lucide-react";
import { getDownloadUrl } from "../api";

export default function HistoryWorkspace({ history, onOpenFile, onDeleteItem, onClearAll }) {
  const [showConfirmClear, setShowConfirmClear] = useState(false);
  const [openingItemId, setOpeningItemId] = useState(null);

  const handleOpenFolder = async (filePath, itemId) => {
    setOpeningItemId(itemId);
    try {
      await onOpenFile(filePath);
    } finally {
      setTimeout(() => setOpeningItemId(null), 1200);
    }
  };

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
    <section className="neu-card p-6 space-y-4">
      <div className="flex items-center justify-between pb-1">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-[#0084FF]"></div>
          <h2 className="text-base font-bold text-[#1E293B] m-0">
            Download History
          </h2>
          <span className="neu-recessed px-2.5 py-0.5 rounded-full text-xs font-semibold text-[#64748B]">
            {history.length}
          </span>
        </div>

        {history.length > 0 && (
          <div>
            {showConfirmClear ? (
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-[#EF4444]">Clear history?</span>
                <button
                  onClick={() => {
                    onClearAll();
                    setShowConfirmClear(false);
                  }}
                  className="px-2.5 py-1 rounded-xl bg-[#FEE2E2] text-[#EF4444] text-xs font-bold cursor-pointer"
                >
                  Yes, Clear
                </button>
                <button
                  onClick={() => setShowConfirmClear(false)}
                  className="neu-raised px-2.5 py-1 text-[#64748B] text-xs font-medium cursor-pointer"
                >
                  Cancel
                </button>
              </div>
            ) : (
              <button
                onClick={() => setShowConfirmClear(true)}
                className="neu-raised px-3 py-1.5 text-xs text-[#64748B] hover:text-[#EF4444] flex items-center gap-1.5 cursor-pointer rounded-xl font-medium"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span>Clear All</span>
              </button>
            )}
          </div>
        )}
      </div>

      {history.length === 0 ? (
        <div className="neu-recessed p-8 text-center text-[#94A3B8] text-sm font-medium rounded-2xl">
          No downloaded files recorded yet. Completed media downloads will appear here.
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((item) => (
            <div
              key={item.id}
              className="neu-raised p-4 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3"
            >
              <div className="flex items-start sm:items-center gap-3.5 flex-1 min-w-0">
                <div className="w-12 h-12 rounded-xl neu-recessed p-0.5 flex items-center justify-center shrink-0 overflow-hidden relative">
                  {item.thumbnail ? (
                    <img
                      src={item.thumbnail}
                      alt={item.title || item.filename}
                      className="w-full h-full object-cover rounded-lg"
                      referrerPolicy="no-referrer"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                        const fallback = e.currentTarget.parentElement?.querySelector(".history-icon-fallback");
                        if (fallback) fallback.classList.remove("hidden");
                      }}
                    />
                  ) : null}
                  <div
                    className={`history-icon-fallback w-full h-full flex items-center justify-center text-[#0084FF] ${
                      item.thumbnail ? "hidden" : ""
                    }`}
                  >
                    {item.media_type === "audio" ? (
                      <Music className="w-5 h-5" />
                    ) : (
                      <Video className="w-5 h-5" />
                    )}
                  </div>
                </div>

                <div className="flex-1 min-w-0">
                  <h3
                    className="text-sm font-bold text-[#1E293B] truncate m-0 leading-tight"
                    title={item.title || item.filename}
                  >
                    {item.title || item.filename}
                  </h3>

                  <div className="flex flex-wrap items-center gap-2 mt-1 text-xs text-[#64748B] font-medium">
                    <span className="uppercase font-semibold tracking-wider text-[11px] text-[#0084FF]">
                      {item.ext || "MEDIA"}
                    </span>
                    <span>·</span>
                    <span>{formatBytes(item.filesize || item.total_bytes)}</span>
                    {item.completed_at && (
                      <>
                        <span>·</span>
                        <span>{formatDate(item.completed_at)}</span>
                      </>
                    )}
                    {item.has_video && item.has_audio && (
                      <span className="neu-recessed px-2 py-0.5 rounded-md text-[11px] font-semibold text-[#10B981]">
                        Sound Verified
                      </span>
                    )}
                  </div>
                </div>
              </div>

              <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                {item.filename && (
                  <a
                    href={getDownloadUrl(item.filename)}
                    download={item.filename}
                    className="neu-accent flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold cursor-pointer no-underline rounded-xl"
                    title="Save to browser downloads"
                  >
                    <Download className="w-3.5 h-3.5 text-white" />
                    <span>Save</span>
                  </a>
                )}

                {item.file_path && onOpenFile && (
                  <button
                    onClick={() => handleOpenFolder(item.file_path, item.id)}
                    disabled={openingItemId === item.id}
                    className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#334155] hover:text-[#0084FF] cursor-pointer disabled:opacity-50 rounded-xl"
                    title="Show in Windows File Explorer"
                  >
                    <FolderOpen className="w-3.5 h-3.5 text-[#0084FF]" />
                    <span>{openingItemId === item.id ? "Opening..." : "Folder"}</span>
                  </button>
                )}

                {onDeleteItem && (
                  <button
                    onClick={() => onDeleteItem(item.id)}
                    className="neu-raised p-2 text-[#94A3B8] hover:text-[#EF4444] cursor-pointer rounded-xl"
                    title="Delete record from history"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
