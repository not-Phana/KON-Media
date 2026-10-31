import React from "react";
import {
  Search,
  Heart,
  Clock,
  Download,
  Settings,
  FolderOpen,
  HardDrive,
  Moon,
  Sun,
  Brain,
  Cpu,
  Layers,
  Sparkles,
  ShieldCheck,
} from "lucide-react";
import KonLogo from "./KonLogo";
import { KonFlashIcon, KonPrecisionIcon } from "./KonIcons";

export default function LeftSidebar({
  activeView = "search",
  onViewChange,
  favoritesCount = 0,
  recentCount = 0,
  activeDownloadsCount = 0,
  engineMode = "rei",
  onEngineModeChange,
  onOpenModelModal,
  onOpenLearningDashboard,
  onOpenSettings,
  onOpenFile,
  health,
  theme,
  onToggleTheme,
}) {
  const isFlash = engineMode === "flash";

  return (
    <aside
      className="hidden lg:flex flex-col justify-between w-64 xl:w-72 shrink-0 space-y-4 select-none sticky top-5 self-start max-h-[calc(100vh-2.5rem)] overflow-y-auto pr-1"
      aria-label="Navigation & Control Sidebar"
    >
      <div className="space-y-4">
        {/* Branding & Quick Preferences */}
        <div className="neu-card p-4 space-y-3 border border-slate-200/60 dark:border-slate-800">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <KonLogo size={38} />
              <div>
                <h1 className="text-base font-black tracking-tight text-[#1E293B] dark:text-[#F8FAFC] m-0 leading-tight">
                  KON <span className="text-[#0084FF]">Media</span>
                </h1>
                <p className="text-[10px] text-[#64748B] dark:text-[#94A3B8] font-medium m-0">
                  Desktop Search &amp; Player
                </p>
              </div>
            </div>

            <div className="flex items-center gap-1.5">
              {/* Theme Toggle */}
              <button
                type="button"
                onClick={onToggleTheme}
                className="neu-raised p-2 rounded-xl text-xs cursor-pointer neu-btn-elastic text-[#334155] dark:text-[#CBD5E1] hover:text-[#0084FF]"
                title={theme === "dark" ? "Switch to Light Mode" : "Switch to Dark Mode"}
              >
                {theme === "dark" ? (
                  <Moon className="w-3.5 h-3.5 text-[#38BDF8]" />
                ) : (
                  <Sun className="w-3.5 h-3.5 text-[#F59E0B]" />
                )}
              </button>

              {/* Settings */}
              <button
                type="button"
                onClick={onOpenSettings}
                className="neu-raised p-2 rounded-xl text-xs cursor-pointer neu-btn-elastic text-[#64748B] hover:text-[#0084FF]"
                title="Settings & Configuration"
              >
                <Settings className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Navigation Section */}
        <nav className="neu-card p-3 space-y-1.5 border border-slate-200/60 dark:border-slate-800" aria-label="Main Views">
          <span className="px-3 py-1 text-[10px] font-black uppercase tracking-wider text-[#64748B] dark:text-[#94A3B8] block">
            Workspace
          </span>

          {/* Search & Discover */}
          <button
            type="button"
            onClick={() => onViewChange("search")}
            className={`w-full px-3.5 py-2.5 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center justify-between transition-all ${
              activeView === "search"
                ? "neu-recessed text-[#0084FF] border border-[#0084FF]/30 bg-[#0084FF]/10"
                : "neu-raised text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B] dark:hover:text-[#F8FAFC]"
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Search className="w-4 h-4 shrink-0" />
              <span>Search &amp; Discover</span>
            </div>
          </button>

          {/* Favorites */}
          <button
            type="button"
            onClick={() => onViewChange("favorites")}
            className={`w-full px-3.5 py-2.5 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center justify-between transition-all ${
              activeView === "favorites"
                ? "neu-recessed text-[#EF4444] border border-[#EF4444]/30 bg-[#EF4444]/10"
                : "neu-raised text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B] dark:hover:text-[#F8FAFC]"
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Heart className={`w-4 h-4 shrink-0 ${activeView === "favorites" ? "fill-current" : ""}`} />
              <span>Favorites</span>
            </div>
            {favoritesCount > 0 && (
              <span
                className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold ${
                  activeView === "favorites" ? "bg-[#EF4444]/20 text-[#EF4444]" : "neu-recessed text-[#64748B]"
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
            className={`w-full px-3.5 py-2.5 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center justify-between transition-all ${
              activeView === "recent"
                ? "neu-recessed text-[#8B5CF6] border border-[#8B5CF6]/30 bg-[#8B5CF6]/10"
                : "neu-raised text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B] dark:hover:text-[#F8FAFC]"
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Clock className="w-4 h-4 shrink-0" />
              <span>Recently Played</span>
            </div>
            {recentCount > 0 && (
              <span
                className={`px-1.5 py-0.2 rounded text-[10px] font-mono font-bold ${
                  activeView === "recent" ? "bg-[#8B5CF6]/20 text-[#8B5CF6]" : "neu-recessed text-[#64748B]"
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
            className={`w-full px-3.5 py-2.5 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center justify-between transition-all ${
              activeView === "downloads"
                ? "neu-recessed text-[#10B981] border border-[#10B981]/30 bg-[#10B981]/10"
                : "neu-raised text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B] dark:hover:text-[#F8FAFC]"
            }`}
          >
            <div className="flex items-center gap-2.5">
              <Download className="w-4 h-4 shrink-0" />
              <span>Downloads</span>
            </div>
            {activeDownloadsCount > 0 && (
              <span className="px-1.5 py-0.2 rounded text-[10px] font-mono font-bold bg-[#10B981]/20 text-[#10B981] animate-pulse">
                {activeDownloadsCount} active
              </span>
            )}
          </button>
        </nav>

        {/* Engine Mode Control Hub */}
        <div className="neu-card p-3.5 space-y-2.5 border border-slate-200/60 dark:border-slate-800">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#64748B] dark:text-[#94A3B8] flex items-center gap-1">
              <Cpu className="w-3 h-3 text-[#0084FF]" />
              Search Engine
            </span>
            <button
              type="button"
              onClick={onOpenModelModal}
              className="text-[10px] text-[#0084FF] hover:underline font-bold cursor-pointer"
              title="Inspect model weights and architecture"
            >
              Info
            </button>
          </div>

          <div className="grid grid-cols-2 gap-2">
            {/* Rei Precision */}
            <button
              type="button"
              onClick={() => onEngineModeChange && onEngineModeChange("rei")}
              className={`p-2.5 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex flex-col items-center gap-1.5 text-center transition-all ${
                !isFlash
                  ? "neu-recessed text-[#0084FF] border border-[#0084FF]/35 bg-[#0084FF]/10 shadow-xs"
                  : "neu-raised text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B]"
              }`}
              title="KON Search 1.2 Rei — Precision mode"
            >
              <KonPrecisionIcon className="w-4 h-4 text-[#0084FF]" />
              <span className="leading-tight">Rei Precision</span>
            </button>

            {/* Rei Flash Speed */}
            <button
              type="button"
              onClick={() => onEngineModeChange && onEngineModeChange("flash")}
              className={`p-2.5 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex flex-col items-center gap-1.5 text-center transition-all ${
                isFlash
                  ? "neu-recessed text-[#F59E0B] border border-[#F59E0B]/35 bg-[#F59E0B]/10 shadow-xs"
                  : "neu-raised text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B]"
              }`}
              title="KON Search 1.2 Rei Flash — Speed mode"
            >
              <KonFlashIcon className="w-4 h-4 text-[#F59E0B]" />
              <span className="leading-tight">Rei Flash</span>
            </button>
          </div>

          <p className="text-[10px] text-[#64748B] dark:text-[#94A3B8] m-0 font-medium leading-relaxed">
            {isFlash
              ? "Speed mode active: Sub-8ms latency and lightweight filtering."
              : "Precision mode active: Deeper musical semantics & title cleanups."}
          </p>
        </div>

        {/* Autonomous Continuous Learning Hub Widget */}
        <div className="neu-card p-3.5 space-y-2.5 border border-[#6366F1]/20 dark:border-[#6366F1]/30">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-black uppercase tracking-wider text-[#6366F1] flex items-center gap-1.5">
              <Brain className="w-3.5 h-3.5 text-[#6366F1]" />
              Continuous Learning
            </span>
            <span className="w-2 h-2 rounded-full bg-[#10B981] animate-pulse"></span>
          </div>

          <p className="text-[11px] text-[#475569] dark:text-[#CBD5E1] m-0 leading-relaxed font-medium">
            Self-improving ranking via background signals and evaluation gatekeepers.
          </p>

          <button
            type="button"
            onClick={onOpenLearningDashboard}
            className="w-full neu-raised px-3 py-2 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center justify-center gap-2 text-[#6366F1] hover:text-[#4F46E5] border border-[#6366F1]/20 transition-colors"
            title="Open Autonomous Continuous Learning Center"
          >
            <Sparkles className="w-3.5 h-3.5 text-[#6366F1]" />
            <span>Open Learning Center</span>
          </button>
        </div>
      </div>

      {/* Storage & Downloads Folder Quick Action */}
      <div className="neu-card p-3.5 space-y-2 border border-slate-200/60 dark:border-slate-800">
        <div className="flex items-center justify-between text-xs text-[#64748B] dark:text-[#94A3B8] font-medium">
          <span className="flex items-center gap-1.5">
            <HardDrive className="w-3.5 h-3.5 text-[#0084FF]" />
            <span>Storage</span>
          </span>
          {health?.disk_free_gb && (
            <span className="font-mono font-bold text-[#1E293B] dark:text-[#F8FAFC]">
              {health.disk_free_gb} GB Free
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => onOpenFile && onOpenFile()}
          className="w-full neu-raised px-3 py-2 rounded-xl text-xs font-bold cursor-pointer neu-btn-tactile flex items-center justify-center gap-2 text-[#334155] dark:text-[#CBD5E1] hover:text-[#0084FF] transition-colors"
          title="Open Downloads Folder in Windows Explorer"
        >
          <FolderOpen className="w-3.5 h-3.5 text-[#0084FF]" />
          <span>Open Folder</span>
        </button>
      </div>
    </aside>
  );
}
