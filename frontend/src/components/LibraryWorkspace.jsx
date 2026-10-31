import React, { useState } from "react";
import {
  Heart,
  Clock,
  Play,
  Pause,
  Download,
  Trash2,
  FolderOpen,
  Music,
  Shuffle,
  Sparkles,
  ExternalLink,
} from "lucide-react";

function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return "";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

export default function LibraryWorkspace({
  activeTab = "favorites", // "favorites" | "recent"
  onTabChange,
  favorites = [],
  recentlyPlayed = [],
  currentTrack = null,
  isPlaying = false,
  onPlayTrack,
  onToggleFavorite,
  onClearRecentlyPlayed,
  onDirectDownload,
  onOpenFile,
  history = [],
  onNavigateToSearch,
}) {
  const isFavorites = activeTab === "favorites";
  const items = isFavorites ? favorites : recentlyPlayed;

  const handlePlayAll = (shuffle = false) => {
    if (!items.length) return;
    if (shuffle) {
      const shuffled = [...items].sort(() => Math.random() - 0.5);
      onPlayTrack(shuffled[0], shuffled);
    } else {
      onPlayTrack(items[0], items);
    }
  };

  return (
    <div className="neu-card p-6 space-y-5 animate-fade-in">
      {/* Shelf Header & Navigation Tabs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-2 border-b border-slate-200/80 dark:border-slate-800">
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => onTabChange && onTabChange("favorites")}
            className={`px-4 py-2 rounded-xl text-xs font-bold cursor-pointer transition-all flex items-center gap-2 ${
              isFavorites
                ? "neu-recessed text-[#EF4444] border border-[#EF4444]/30 bg-[#EF4444]/10 shadow-xs"
                : "neu-raised text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F1F5F9]"
            }`}
          >
            <Heart className={`w-4 h-4 ${isFavorites ? "fill-current" : ""}`} />
            <span>Favorites</span>
            <span className="neu-recessed px-1.5 py-0.2 rounded text-[10px] font-mono">
              {favorites.length}
            </span>
          </button>

          <button
            type="button"
            onClick={() => onTabChange && onTabChange("recent")}
            className={`px-4 py-2 rounded-xl text-xs font-bold cursor-pointer transition-all flex items-center gap-2 ${
              !isFavorites
                ? "neu-recessed text-[#0084FF] border border-[#0084FF]/30 bg-[#0084FF]/10 shadow-xs"
                : "neu-raised text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F1F5F9]"
            }`}
          >
            <Clock className="w-4 h-4" />
            <span>Recently Played</span>
            <span className="neu-recessed px-1.5 py-0.2 rounded text-[10px] font-mono">
              {recentlyPlayed.length}
            </span>
          </button>
        </div>

        {items.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => handlePlayAll(false)}
              className="neu-accent px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer flex items-center gap-1.5 text-white shadow-sm"
              title="Play all tracks in list"
            >
              <Play className="w-3.5 h-3.5 fill-current" />
              <span>Play All</span>
            </button>

            <button
              type="button"
              onClick={() => handlePlayAll(true)}
              className="neu-raised p-2 rounded-xl text-xs font-bold text-[#64748B] hover:text-[#0084FF] cursor-pointer"
              title="Shuffle all tracks in list"
            >
              <Shuffle className="w-3.5 h-3.5" />
            </button>

            {!isFavorites && recentlyPlayed.length > 0 && (
              <button
                type="button"
                onClick={onClearRecentlyPlayed}
                className="neu-raised px-2.5 py-1.5 rounded-xl text-xs text-[#EF4444] hover:bg-red-500/10 cursor-pointer flex items-center gap-1"
                title="Clear recently played history"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span className="text-[11px] font-semibold">Clear</span>
              </button>
            )}
          </div>
        )}
      </div>

      {/* Items List or Empty State */}
      {items.length === 0 ? (
        <div className="neu-recessed p-10 rounded-2xl text-center space-y-3">
          {isFavorites ? (
            <>
              <Heart className="w-10 h-10 text-[#EF4444]/40 mx-auto" />
              <h4 className="text-sm font-bold text-[#1E293B] dark:text-[#E2E8F0] m-0">
                No favorite songs saved yet
              </h4>
              <p className="text-xs text-[#64748B] dark:text-[#94A3B8] m-0 max-w-sm mx-auto">
                Click the heart icon on any song in search results or the bottom player to save it to your private offline favorites shelf.
              </p>
            </>
          ) : (
            <>
              <Clock className="w-10 h-10 text-[#0084FF]/40 mx-auto" />
              <h4 className="text-sm font-bold text-[#1E293B] dark:text-[#E2E8F0] m-0">
                No recently played tracks
              </h4>
              <p className="text-xs text-[#64748B] dark:text-[#94A3B8] m-0 max-w-sm mx-auto">
                Songs you preview or listen to will appear here automatically so you can replay them anytime.
              </p>
            </>
          )}

          {onNavigateToSearch && (
            <button
              type="button"
              onClick={onNavigateToSearch}
              className="neu-raised px-4 py-2 rounded-xl text-xs font-bold text-[#0084FF] hover:text-white hover:bg-[#0084FF] transition-all cursor-pointer inline-flex items-center gap-1.5 mt-2"
            >
              <Music className="w-3.5 h-3.5" />
              <span>Search Music Now</span>
            </button>
          )}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {items.map((track, idx) => {
            const isThisPlaying =
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
                className={`p-3.5 rounded-2xl transition-all flex items-center justify-between gap-3 group ${
                  isThisPlaying
                    ? "neu-recessed border border-[#0084FF]/40 bg-[#0084FF]/5 shadow-[0_0_12px_rgba(0,132,255,0.15)]"
                    : "neu-raised hover:border-slate-300 dark:hover:border-slate-700"
                }`}
              >
                {/* Left: Thumbnail & Song Info */}
                <div
                  className="flex items-center gap-3 min-w-0 flex-1 cursor-pointer"
                  onClick={() => onPlayTrack && onPlayTrack(track, items)}
                >
                  <div className="w-12 h-12 rounded-xl neu-recessed overflow-hidden shrink-0 relative flex items-center justify-center">
                    {track.thumbnail ? (
                      <img
                        src={track.thumbnail}
                        alt={track.title}
                        className="w-full h-full object-cover"
                        referrerPolicy="no-referrer"
                      />
                    ) : (
                      <Music className="w-5 h-5 text-[#0084FF]" />
                    )}

                    <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 flex items-center justify-center transition-opacity">
                      {isThisPlaying && isPlaying ? (
                        <Pause className="w-4 h-4 fill-white text-white" />
                      ) : (
                        <Play className="w-4 h-4 fill-white text-white ml-0.5" />
                      )}
                    </div>

                    {isThisPlaying && isPlaying && (
                      <div className="absolute inset-0 bg-black/40 flex items-center justify-center gap-0.5 pointer-events-none">
                        <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:0ms] h-3.5"></span>
                        <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:150ms] h-5"></span>
                        <span className="w-1 bg-[#0084FF] rounded-full animate-bounce [animation-delay:300ms] h-3"></span>
                      </div>
                    )}
                  </div>

                  <div className="min-w-0 flex-1">
                    <h4
                      className={`text-xs sm:text-sm font-bold truncate m-0 ${
                        isThisPlaying ? "text-[#0084FF]" : "text-[#1E293B] dark:text-[#E2E8F0]"
                      }`}
                      title={track.title}
                    >
                      {track.title}
                    </h4>
                    <p
                      className="text-[11px] text-[#64748B] dark:text-[#94A3B8] truncate m-0 mt-0.5 font-medium"
                      title={track.artist || track.uploader}
                    >
                      {track.artist || track.uploader || "Unknown Artist"}
                    </p>

                    <div className="flex items-center gap-2 mt-1 text-[10px] text-[#94A3B8] font-mono">
                      {track.duration ? <span>{formatDuration(track.duration)}</span> : null}
                      {track.platform && (
                        <span className="uppercase font-sans font-bold text-[9px] px-1.5 py-0.2 rounded neu-recessed">
                          {track.platform}
                        </span>
                      )}
                      {isDownloaded && (
                        <span className="text-[#10B981] font-sans font-bold text-[9px] px-1.5 py-0.2 rounded neu-recessed flex items-center gap-0.5">
                          Saved
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Right: Actions */}
                <div className="flex items-center gap-1.5 shrink-0">
                  {/* Play / Preview Button */}
                  <button
                    type="button"
                    onClick={() => onPlayTrack && onPlayTrack(track, items)}
                    className={`p-2 rounded-xl cursor-pointer transition-all ${
                      isThisPlaying
                        ? "neu-recessed text-[#0084FF]"
                        : "neu-raised text-[#64748B] hover:text-[#0084FF]"
                    }`}
                    title={isThisPlaying && isPlaying ? "Pause" : "Play track"}
                  >
                    {isThisPlaying && isPlaying ? (
                      <Pause className="w-4 h-4 fill-current" />
                    ) : (
                      <Play className="w-4 h-4 fill-current ml-0.5" />
                    )}
                  </button>

                  {/* Favorite Toggle Button */}
                  {onToggleFavorite && (
                    <button
                      type="button"
                      onClick={() => onToggleFavorite(track)}
                      className={`p-2 rounded-xl cursor-pointer transition-all ${
                        isFavorites
                          ? "neu-recessed text-[#EF4444]"
                          : "neu-raised text-[#94A3B8] hover:text-[#EF4444]"
                      }`}
                      title={isFavorites ? "Remove from favorites" : "Add to favorites"}
                    >
                      <Heart className={`w-4 h-4 ${isFavorites ? "fill-current" : ""}`} />
                    </button>
                  )}

                  {/* Direct Download Button */}
                  {onDirectDownload && (
                    <button
                      type="button"
                      onClick={() => onDirectDownload(track, "audio")}
                      className="neu-raised p-2 rounded-xl text-[#64748B] hover:text-[#0084FF] cursor-pointer transition-colors"
                      title="Download song as MP3"
                    >
                      <Download className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
