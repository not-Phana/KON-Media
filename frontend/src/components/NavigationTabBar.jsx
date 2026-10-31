import React from "react";
import { Search, Heart, Clock, Download, HardDrive } from "lucide-react";
import { KonFlashIcon, KonPrecisionIcon } from "./KonIcons";

export default function NavigationTabBar({
  activeView = "search", // "search" | "favorites" | "recent" | "downloads"
  onViewChange,
  favoritesCount = 0,
  recentCount = 0,
  activeDownloadsCount = 0,
  engineMode = "rei",
  onOpenModelModal,
}) {
  const isFlash = engineMode === "flash";

  return (
    <nav
      className="flex flex-wrap items-center justify-between gap-3 p-1.5 rounded-2xl neu-card shadow-sm"
      aria-label="Main Navigation"
    >
      {/* Navigation Pills */}
      <div className="flex flex-wrap items-center gap-1.5">
        {/* Search & Discover */}
        <button
          type="button"
          onClick={() => onViewChange("search")}
          className={`px-4 py-2 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center gap-2 ${
            activeView === "search"
              ? "neu-recessed text-[#0084FF] border border-[#0084FF]/30 bg-[#0084FF]/10 shadow-xs"
              : "neu-raised text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F1F5F9]"
          }`}
        >
          <Search className="w-4 h-4" />
          <span>Search &amp; Discover</span>
        </button>

        {/* Favorites */}
        <button
          type="button"
          onClick={() => onViewChange("favorites")}
          className={`px-4 py-2 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center gap-2 ${
            activeView === "favorites"
              ? "neu-recessed text-[#EF4444] border border-[#EF4444]/30 bg-[#EF4444]/10 shadow-xs"
              : "neu-raised text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F1F5F9]"
          }`}
        >
          <Heart className={`w-4 h-4 ${activeView === "favorites" ? "fill-current" : ""}`} />
          <span>Favorites</span>
          {favoritesCount > 0 && (
            <span
              className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold ${
                activeView === "favorites"
                  ? "bg-[#EF4444]/20 text-[#EF4444]"
                  : "neu-recessed text-[#64748B]"
              }`}
            >
              {favoritesCount}
            </span>
          )}
        </button>

        {/* Recently Played */}
        <button
          type="button"
          onClick={() => onViewChange("recent")}
          className={`px-4 py-2 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center gap-2 ${
            activeView === "recent"
              ? "neu-recessed text-[#8B5CF6] border border-[#8B5CF6]/30 bg-[#8B5CF6]/10 shadow-xs"
              : "neu-raised text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F1F5F9]"
          }`}
        >
          <Clock className="w-4 h-4" />
          <span>Recently Played</span>
          {recentCount > 0 && (
            <span
              className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold ${
                activeView === "recent"
                  ? "bg-[#8B5CF6]/20 text-[#8B5CF6]"
                  : "neu-recessed text-[#64748B]"
              }`}
            >
              {recentCount}
            </span>
          )}
        </button>

        {/* Downloads */}
        <button
          type="button"
          onClick={() => onViewChange("downloads")}
          className={`px-4 py-2 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center gap-2 ${
            activeView === "downloads"
              ? "neu-recessed text-[#10B981] border border-[#10B981]/30 bg-[#10B981]/10 shadow-xs"
              : "neu-raised text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F1F5F9]"
          }`}
        >
          <Download className="w-4 h-4" />
          <span>Downloads</span>
          {activeDownloadsCount > 0 && (
            <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-[#10B981]/20 text-[#10B981] animate-pulse">
              {activeDownloadsCount} active
            </span>
          )}
        </button>
      </div>

      {/* Active Engine Spotlight Pill */}
      <div className="hidden md:flex items-center gap-2 pr-1">
        <button
          type="button"
          onClick={onOpenModelModal}
          className={`neu-recessed px-3 py-1.5 rounded-xl text-xs font-bold cursor-pointer flex items-center gap-1.5 transition-colors ${
            isFlash ? "text-[#F59E0B] hover:text-[#D97706]" : "text-[#0084FF] hover:text-[#0074E0]"
          }`}
          title={
            isFlash
              ? "Active Search Engine: KON Search 1.2 Rei Flash (Speed mode)"
              : "Active Search Engine: KON Search 1.2 Rei (Precision mode)"
          }
        >
          {isFlash ? (
            <KonFlashIcon className="w-3.5 h-3.5" />
          ) : (
            <KonPrecisionIcon className="w-3.5 h-3.5" />
          )}
          <span>{isFlash ? "Rei Flash · Speed" : "Rei · Precision"}</span>
        </button>
      </div>
    </nav>
  );
}
