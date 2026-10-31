import React from "react";
import { HardDrive, Settings, FolderOpen, Cpu, Moon, Sun, Brain } from "lucide-react";
import KonLogo from "./KonLogo";

export default function Header({
  health,
  onOpenSettings,
  onOpenFile,
  onOpenModelModal,
  onOpenLearningDashboard,
  theme,
  onToggleTheme,
}) {
  return (
    <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 py-4">
      <div className="flex items-center gap-3.5">
        <KonLogo size={46} />
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-[#1E293B] m-0">
            KON <span className="text-[#0084FF]">Media</span>
          </h1>
          <p className="text-xs text-[#64748B] font-medium m-0 mt-0.5">
            Private Desktop Media Downloader &amp; Library
          </p>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2.5 text-xs">
        {/* Cool Dark Mode Toggle */}
        <button
          type="button"
          onClick={onToggleTheme}
          className="neu-raised flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-[#334155] cursor-pointer hover:text-[#0084FF] transition-all"
          title={theme === "dark" ? "Dark Mode Active — Click to switch to Light" : "Light Mode Active — Click to switch to Cool Dark Mode"}
        >
          {theme === "dark" ? (
            <>
              <Moon className="w-3.5 h-3.5 text-[#38BDF8]" />
              <span className="text-[#38BDF8] font-bold">Dark</span>
            </>
          ) : (
            <>
              <Sun className="w-3.5 h-3.5 text-[#F59E0B]" />
              <span>Light</span>
            </>
          )}
        </button>

        {/* KON Search 1.2 Rei Model Spotlight Badge */}
        <button
          type="button"
          onClick={onOpenModelModal}
          className="neu-raised flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-[#1E293B] hover:text-[#0084FF] cursor-pointer transition-colors"
          title="Our Search Model: KON Search 1.2 Rei (Click for model architecture & live weights)"
        >
          <Cpu className="w-3.5 h-3.5 text-[#0084FF]" />
          <span>KON Search 1.2 Rei</span>
          <span className="neu-recessed px-1.5 py-0.5 rounded text-[10px] font-mono font-bold text-[#0084FF]">
            v1.2
          </span>
        </button>

        {/* Autonomous Continuous Learning Center */}
        {onOpenLearningDashboard && (
          <button
            type="button"
            onClick={onOpenLearningDashboard}
            className="neu-raised flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-[#6366F1] hover:text-[#4F46E5] cursor-pointer transition-colors"
            title="Open Autonomous Continuous Learning Center (Model Evolution & Telemetry)"
          >
            <Brain className="w-3.5 h-3.5 text-[#6366F1]" />
            <span className="hidden md:inline">Learning Center</span>
          </button>
        )}

        {/* System Ready Badge */}
        <div className="neu-raised flex items-center gap-2 px-3.5 py-2 text-[#475569] font-medium">
          <span className="w-2 h-2 rounded-full bg-[#10B981] shadow-xs"></span>
          <span>Engine Active</span>
        </div>

        {/* Disk Free Space */}
        {health?.disk_free_gb && (
          <div className="neu-raised flex items-center gap-1.5 px-3.5 py-2 text-[#475569] font-medium">
            <HardDrive className="w-3.5 h-3.5 text-[#0084FF]" />
            <span>{health.disk_free_gb} GB Free</span>
          </div>
        )}

        {/* Open Downloads Folder */}
        <button
          onClick={() => onOpenFile && onOpenFile()}
          className="neu-raised flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-[#334155] cursor-pointer hover:text-[#0084FF] transition-colors"
          title="Open Downloads Folder in File Explorer"
        >
          <FolderOpen className="w-3.5 h-3.5 text-[#0084FF]" />
          <span>Folder</span>
        </button>

        {/* Settings Button */}
        <button
          onClick={onOpenSettings}
          className="neu-raised flex items-center gap-2 px-3.5 py-2 text-xs font-semibold text-[#334155] cursor-pointer hover:text-[#0084FF] transition-colors"
          title="Open Application Settings"
        >
          <Settings className="w-3.5 h-3.5 text-[#64748B]" />
          <span>Settings</span>
        </button>
      </div>
    </header>
  );
}
