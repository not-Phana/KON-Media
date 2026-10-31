import React from "react";
import {
  ListMusic,
  Play,
  Pause,
  Trash2,
  X,
  Music,
  Download,
  CheckCircle2,
  FolderOpen,
  Clock,
} from "lucide-react";

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

export default function PlaybackQueueDrawer({
  isOpen,
  onClose,
  queue = [],
  currentIndex = -1,
  currentTrack = null,
  isPlaying = false,
  onPlayTrack,
  onRemoveTrack,
  onClearQueue,
  onDirectDownload,
  onOpenFile,
  history = [],
}) {
  if (!isOpen) return null;

  return (
    <div
      className="fixed inset-0 z-50 bg-black/50 backdrop-blur-xs flex justify-end animate-fade-in"
      onClick={onClose}
      role="dialog"
      aria-label="Listening Queue"
    >
      <div
        className="w-full max-w-md h-full bg-white dark:bg-[#0B1120] border-l border-slate-200/80 dark:border-slate-800 shadow-2xl flex flex-col justify-between overflow-hidden animate-slide-in-right"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drawer Header */}
        <div className="p-4 border-b border-slate-200/80 dark:border-slate-800 flex items-center justify-between gap-3 bg-slate-50/50 dark:bg-slate-900/50">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl neu-recessed text-[#0084FF]">
              <ListMusic className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-[#1E293B] dark:text-[#E2E8F0] m-0">
                Listening Queue
              </h3>
              <p className="text-[11px] text-[#64748B] dark:text-[#94A3B8] m-0 font-medium">
                {queue.length} {queue.length === 1 ? "track" : "tracks"} in queue
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1.5">
            {queue.length > 0 && (
              <button
                type="button"
                onClick={onClearQueue}
                className="neu-raised px-2.5 py-1.5 text-xs text-[#EF4444] hover:bg-red-500/10 rounded-xl cursor-pointer transition-colors flex items-center gap-1"
                title="Clear all tracks from queue"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span className="text-[11px] font-semibold">Clear</span>
              </button>
            )}
            <button
              type="button"
              onClick={onClose}
              className="neu-raised p-1.5 text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F1F5F9] rounded-xl cursor-pointer"
              title="Close queue"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Queue Content Scrollable Area */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* NOW PLAYING SECTION */}
          {currentTrack && (
            <div className="space-y-2">
              <span className="text-[10px] font-black uppercase tracking-wider text-[#0084FF] px-1">
                Now Playing
              </span>
              <div className="neu-recessed p-3 rounded-2xl border border-[#0084FF]/30 bg-[#0084FF]/5 flex items-center justify-between gap-3">
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <div className="w-12 h-12 rounded-xl neu-recessed overflow-hidden shrink-0 relative flex items-center justify-center">
                    {currentTrack.thumbnail ? (
                      <img
                        src={currentTrack.thumbnail}
                        alt={currentTrack.title}
                        className="w-full h-full object-cover"
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <Music className="w-5 h-5 text-[#0084FF]" />
                    )}
                    {isPlaying && (
                      <div className="absolute inset-0 bg-black/40 flex items-center justify-center gap-0.5 pointer-events-none">
                        <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:0ms] h-3.5"></span>
                        <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:150ms] h-5"></span>
                        <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:300ms] h-3"></span>
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <h4
                      className="text-xs font-bold text-[#1E293B] dark:text-[#E2E8F0] truncate m-0"
                      title={currentTrack.title}
                    >
                      {currentTrack.title}
                    </h4>
                    <p
                      className="text-[11px] text-[#64748B] dark:text-[#94A3B8] truncate m-0 mt-0.5"
                      title={currentTrack.artist || currentTrack.uploader}
                    >
                      {currentTrack.artist || currentTrack.uploader || "Unknown Artist"}
                    </p>
                  </div>
                </div>

                {onDirectDownload && (
                  <button
                    type="button"
                    onClick={() => onDirectDownload(currentTrack, "audio")}
                    className="neu-raised p-2 text-[#0084FF] hover:text-white hover:bg-[#0084FF] rounded-xl transition-all cursor-pointer shrink-0"
                    title="Download current track"
                  >
                    <Download className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          )}

          {/* UP NEXT QUEUE LIST */}
          <div className="space-y-2">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#64748B] dark:text-[#94A3B8] px-1">
              Up Next ({queue.length})
            </span>

            {queue.length === 0 ? (
              <div className="neu-card p-6 text-center space-y-2">
                <Music className="w-8 h-8 text-[#94A3B8] mx-auto opacity-50" />
                <p className="text-xs font-medium text-[#64748B] dark:text-[#94A3B8] m-0">
                  Your queue is currently empty.
                </p>
                <p className="text-[11px] text-[#94A3B8] m-0">
                  Click "Preview" or "Queue" on any search result to add songs.
                </p>
              </div>
            ) : (
              <div className="space-y-1.5">
                {queue.map((track, idx) => {
                  const isCurrent =
                    currentTrack &&
                    (currentTrack.id === track.id || currentTrack.url === track.url);
                  const isDownloaded = history.some(
                    (h) =>
                      (h.url === track.url || (track.id && h.url?.includes(track.id))) &&
                      h.status === "completed"
                  );

                  return (
                    <div
                      key={track.id || `${track.url}_${idx}`}
                      className={`p-2.5 rounded-xl neu-card-hover transition-all flex items-center justify-between gap-3 group ${
                        isCurrent
                          ? "neu-recessed border border-[#0084FF]/40 bg-[#0084FF]/5"
                          : "neu-raised hover:border-slate-300 dark:hover:border-slate-700"
                      }`}
                    >
                      {/* Left: Index & Artwork & Titles */}
                      <div
                        className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                        onClick={() => onPlayTrack && onPlayTrack(track)}
                      >
                        <span className="w-5 text-center text-[10px] font-mono text-[#94A3B8] shrink-0 font-bold">
                          {idx + 1}
                        </span>

                        <div className="w-10 h-10 rounded-lg neu-recessed overflow-hidden shrink-0 relative flex items-center justify-center">
                          {track.thumbnail ? (
                            <img
                              src={track.thumbnail}
                              alt={track.title}
                              className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-106"
                              referrerPolicy="no-referrer"
                            />
                          ) : (
                            <Music className="w-4 h-4 text-[#0084FF]" />
                          )}
                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                            <Play className="w-3.5 h-3.5 fill-white text-white ml-0.5" />
                          </div>
                        </div>

                        <div className="min-w-0 flex-1">
                          <h4
                            className={`text-xs font-bold truncate m-0 ${
                              isCurrent
                                ? "text-[#0084FF]"
                                : "text-[#1E293B] dark:text-[#E2E8F0]"
                            }`}
                            title={track.title}
                          >
                            {track.title}
                          </h4>
                          <div className="flex items-center gap-2 mt-0.5">
                            <span
                              className="text-[10px] text-[#64748B] dark:text-[#94A3B8] truncate"
                              title={track.artist || track.uploader}
                            >
                              {track.artist || track.uploader || "Unknown"}
                            </span>
                            {track.duration ? (
                              <span className="text-[10px] text-[#94A3B8] font-mono shrink-0">
                                {formatDuration(track.duration)}
                              </span>
                            ) : null}
                            {isDownloaded && (
                              <span className="text-[9px] text-[#10B981] font-bold shrink-0">
                                Saved
                              </span>
                            )}
                          </div>
                        </div>
                      </div>

                      {/* Right: Actions */}
                      <div className="flex items-center gap-1 shrink-0">
                        {onDirectDownload && (
                          <button
                            type="button"
                            onClick={() => onDirectDownload(track, "audio")}
                            className="p-1.5 text-[#64748B] hover:text-[#0084FF] rounded-lg transition-colors cursor-pointer"
                            title="Download track"
                          >
                            <Download className="w-3.5 h-3.5" />
                          </button>
                        )}
                        {onRemoveTrack && (
                          <button
                            type="button"
                            onClick={() => onRemoveTrack(idx, track)}
                            className="p-1.5 text-[#64748B] hover:text-[#EF4444] rounded-lg transition-colors cursor-pointer"
                            title="Remove from queue"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </div>

        {/* Drawer Footer with Quick Tip */}
        <div className="p-3 border-t border-slate-200/80 dark:border-slate-800 text-center bg-slate-50/50 dark:bg-slate-900/50">
          <p className="text-[10px] text-[#94A3B8] m-0 font-medium">
            Keyboard shortcut: Press <kbd className="neu-recessed px-1 py-0.5 rounded font-mono text-[9px] text-[#1E293B] dark:text-[#E2E8F0]">Space</kbd> to Play/Pause · <kbd className="neu-recessed px-1 py-0.5 rounded font-mono text-[9px] text-[#1E293B] dark:text-[#E2E8F0]">←/→</kbd> Seek
          </p>
        </div>
      </div>
    </div>
  );
}
