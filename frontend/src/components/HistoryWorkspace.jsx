import React, { useState } from "react";
import {
  Film,
  FolderOpen,
  Trash2,
  Video,
  Music,
  Download,
  Play,
  Pause,
  Shuffle,
} from "lucide-react";
import { getDownloadUrl } from "../api";

export default function HistoryWorkspace({
  history = [],
  onOpenFile,
  onDeleteItem,
  onClearAll,
  onPlayVideo,
  onPlayTrack,
  currentTrack = null,
  isPlaying = false,
  onTogglePlay,
}) {
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

  const isAudioPlayable = (item) => {
    if (!item) return false;
    if (item.media_type === "audio" || item.has_audio) return true;
    const ext = (item.ext || "").toLowerCase();
    if (["mp3", "m4a", "wav", "flac", "opus", "webm", "ogg", "aac", "mp4"].includes(ext)) return true;
    if (item.filename && /\.(mp3|m4a|wav|flac|opus|webm|ogg|aac|mp4)$/i.test(item.filename)) return true;
    return false;
  };

  const isItemActive = (item) => {
    if (!currentTrack || !item) return false;
    if (currentTrack.id && item.id && currentTrack.id === item.id) return true;
    if (currentTrack.filename && item.filename && currentTrack.filename === item.filename) return true;
    if (currentTrack.file_path && item.file_path && currentTrack.file_path === item.file_path) return true;
    if (currentTrack.url && item.url && currentTrack.url === item.url) return true;
    return false;
  };

  const playableItems = history.filter(isAudioPlayable);

  const handlePlayAll = (shuffle = false) => {
    if (!playableItems.length || !onPlayTrack) return;
    if (shuffle) {
      const shuffled = [...playableItems].sort(() => Math.random() - 0.5);
      onPlayTrack(shuffled[0], shuffled);
    } else {
      onPlayTrack(playableItems[0], playableItems);
    }
  };

  return (
    <section className="neu-card p-6 space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-1">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-[#0084FF]"></div>
          <h2 className="text-base font-bold text-[#1E293B] dark:text-[#F8FAFC] m-0">
            Download History
          </h2>
          <span className="neu-recessed px-2.5 py-0.5 rounded-full text-xs font-semibold text-[#64748B]">
            {history.length}
          </span>
          {playableItems.length > 0 && (
            <span className="neu-recessed px-2.5 py-0.5 rounded-full text-xs font-semibold text-[#0084FF]">
              {playableItems.length} songs
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {playableItems.length > 0 && onPlayTrack && (
            <div className="flex items-center gap-1.5 mr-1">
              <button
                type="button"
                onClick={() => handlePlayAll(false)}
                className="neu-accent neu-btn-tactile px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer flex items-center gap-1.5 text-white shadow-sm"
                title="Play all downloaded songs"
              >
                <Play className="w-3.5 h-3.5 fill-current" />
                <span>Play All</span>
              </button>

              <button
                type="button"
                onClick={() => handlePlayAll(true)}
                className="neu-raised neu-btn-tactile p-2 rounded-xl text-xs font-bold text-[#64748B] hover:text-[#0084FF] cursor-pointer"
                title="Shuffle all downloaded songs"
              >
                <Shuffle className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {history.length > 0 && (
            <div>
              {showConfirmClear ? (
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold text-[#EF4444]">Clear history?</span>
                  <button
                    type="button"
                    onClick={() => {
                      onClearAll();
                      setShowConfirmClear(false);
                    }}
                    className="px-2.5 py-1 rounded-xl bg-[#FEE2E2] text-[#EF4444] text-xs font-bold cursor-pointer"
                  >
                    Yes, Clear
                  </button>
                  <button
                    type="button"
                    onClick={() => setShowConfirmClear(false)}
                    className="neu-raised px-2.5 py-1 text-[#64748B] text-xs font-medium cursor-pointer"
                  >
                    Cancel
                  </button>
                </div>
              ) : (
                <button
                  type="button"
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
      </div>

      {history.length === 0 ? (
        <div className="neu-recessed p-8 text-center text-[#94A3B8] text-sm font-medium rounded-2xl">
          No downloaded files recorded yet. Completed media downloads will appear here.
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((item) => {
            const isPlayingThis = isItemActive(item);
            const isThisPlaying = isPlayingThis && isPlaying;
            const canPlayAudio = isAudioPlayable(item);
            const isVideo =
              item.media_type === "video" ||
              item.has_video ||
              (item.filename && /\.(mp4|webm|mkv|mov)$/i.test(item.filename));

            return (
              <div
                key={item.id || item.filename}
                className={`neu-raised p-4 rounded-2xl flex flex-col sm:flex-row sm:items-center justify-between gap-3 group transition-all ${
                  isThisPlaying
                    ? "neu-recessed border border-[#0084FF]/40 bg-[#0084FF]/5 shadow-[0_0_12px_rgba(0,132,255,0.15)]"
                    : "hover:border-slate-300 dark:hover:border-slate-700"
                }`}
              >
                {/* Left: Thumbnail & Info */}
                <div
                  className="flex items-start sm:items-center gap-3.5 flex-1 min-w-0 cursor-pointer"
                  onClick={() => {
                    if (isPlayingThis && onTogglePlay) {
                      onTogglePlay();
                    } else if (canPlayAudio && onPlayTrack) {
                      onPlayTrack(item, playableItems.length ? playableItems : history);
                    } else if (isVideo && onPlayVideo) {
                      onPlayVideo({
                        url: item.url || item.webpage_url,
                        title: item.title,
                        uploader: item.uploader || item.artist,
                        thumbnail: item.thumbnail,
                        file_path: item.file_path,
                        is_local: true,
                        resolution: "Local File",
                      });
                    }
                  }}
                >
                  <div className="w-12 h-12 rounded-xl neu-recessed p-0.5 flex items-center justify-center shrink-0 overflow-hidden relative">
                    {item.thumbnail ? (
                      <img
                        src={item.thumbnail}
                        alt={item.title || item.filename}
                        className="w-full h-full object-cover rounded-lg transition-transform duration-300 group-hover:scale-106"
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

                    {/* Quick-play hover overlay */}
                    {canPlayAudio && (
                      <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity rounded-lg">
                        {isThisPlaying ? (
                          <Pause className="w-4 h-4 fill-white text-white" />
                        ) : (
                          <Play className="w-4 h-4 fill-white text-white ml-0.5" />
                        )}
                      </div>
                    )}

                    {/* Animated dancing soundwave equalizer when playing */}
                    {isThisPlaying && (
                      <div className="absolute inset-0 bg-black/40 flex items-center justify-center gap-0.75 pointer-events-none rounded-lg">
                        <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:0ms] h-3.5"></span>
                        <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:150ms] h-5"></span>
                        <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:300ms] h-3"></span>
                      </div>
                    )}
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <h3
                        className={`text-sm font-bold truncate m-0 leading-tight ${
                          isThisPlaying ? "text-[#0084FF]" : "text-[#1E293B] dark:text-[#F8FAFC]"
                        }`}
                        title={item.title || item.filename}
                      >
                        {item.title || item.filename}
                      </h3>
                      {isThisPlaying && (
                        <span className="neu-recessed px-2 py-0.5 rounded-full text-[10px] font-bold text-[#0084FF] border border-[#0084FF]/40 inline-flex items-center gap-1 shrink-0">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#0084FF] animate-ping" />
                          <span>Playing</span>
                        </span>
                      )}
                    </div>

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
                      <span className="neu-recessed px-2 py-0.5 rounded-md text-[10px] font-semibold text-[#10B981]">
                        Downloaded
                      </span>
                    </div>
                  </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                  {/* Play / Pause button for audio or any sound media */}
                  {canPlayAudio && onPlayTrack && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        if (isPlayingThis && onTogglePlay) {
                          onTogglePlay();
                        } else {
                          onPlayTrack(item, playableItems.length ? playableItems : history);
                        }
                      }}
                      className={`neu-btn-tactile flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold cursor-pointer rounded-xl transition-all ${
                        isThisPlaying
                          ? "neu-recessed text-[#0084FF] border border-[#0084FF]/40 bg-[#0084FF]/10 shadow-xs"
                          : "neu-raised text-[#0084FF] hover:bg-[#0084FF]/10 hover:border-[#0084FF]/40"
                      }`}
                      title={isThisPlaying ? "Pause song" : "Play song in player"}
                    >
                      {isThisPlaying ? (
                        <>
                          <Pause className="w-3.5 h-3.5 fill-current" />
                          <span>Pause</span>
                        </>
                      ) : (
                        <>
                          <Play className="w-3.5 h-3.5 fill-current ml-0.5" />
                          <span>Play</span>
                        </>
                      )}
                    </button>
                  )}

                  {/* Watch button for video */}
                  {onPlayVideo && isVideo && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onPlayVideo({
                          url: item.url || item.webpage_url,
                          title: item.title,
                          uploader: item.uploader || item.artist,
                          thumbnail: item.thumbnail,
                          file_path: item.file_path,
                          is_local: true,
                          resolution: "Local File",
                        });
                      }}
                      className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#EF4444] hover:bg-[#EF4444]/10 hover:border-[#EF4444]/40 cursor-pointer rounded-xl transition-all"
                      title="Watch downloaded video"
                    >
                      <Film className="w-3.5 h-3.5" />
                      <span>Watch</span>
                    </button>
                  )}

                  {/* Save to browser */}
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

                  {/* Open in File Explorer */}
                  {item.file_path && onOpenFile && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleOpenFolder(item.file_path, item.id);
                      }}
                      disabled={openingItemId === item.id}
                      className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-[#334155] hover:text-[#0084FF] cursor-pointer disabled:opacity-50 rounded-xl"
                      title="Show in Windows File Explorer"
                    >
                      <FolderOpen className="w-3.5 h-3.5 text-[#0084FF]" />
                      <span>{openingItemId === item.id ? "Opening..." : "Folder"}</span>
                    </button>
                  )}

                  {/* Delete from history */}
                  {onDeleteItem && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onDeleteItem(item.id);
                      }}
                      className="neu-raised p-2 text-[#94A3B8] hover:text-[#EF4444] cursor-pointer rounded-xl"
                      title="Delete record from history"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
