import React from "react";
import { HardDrive, Settings, CheckCircle2, AlertTriangle, FolderOpen } from "lucide-react";
import KonLogo from "./KonLogo";

export default function Header({ health, onOpenSettings, onOpenFile }) {
  return (
    <header className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 py-6 border-b border-[#2D323B]">
      <div>
        <div className="flex items-center gap-3">
          <KonLogo size={42} />
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[#F3F4F6] m-0">
              KON <span className="text-[#8BC5B0]">Media</span>
            </h1>
            <p className="text-xs text-[#A5ABB5] m-0">
              Personal Desktop Media Workspace · Local-First
            </p>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        {/* yt-dlp Status Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#202329] border border-[#2D323B] text-[#A5ABB5]">
          <CheckCircle2 className="w-3.5 h-3.5 text-[#72C69A]" />
          <span>yt-dlp: <strong className="text-[#F3F4F6]">{health?.engine?.ytdlp_version ? `v${health.engine.ytdlp_version.split('.')[0]}` : "Active"}</strong></span>
        </div>

        {/* FFmpeg Status Badge */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#202329] border border-[#2D323B] text-[#A5ABB5]">
          {health?.engine?.ffmpeg_available ? (
            <>
              <CheckCircle2 className="w-3.5 h-3.5 text-[#72C69A]" />
              <span>FFmpeg: <strong className="text-[#F3F4F6]">{health.engine.ffmpeg_source === 'custom' ? 'Configured' : 'Ready'}</strong></span>
            </>
          ) : (
            <>
              <AlertTriangle className="w-3.5 h-3.5 text-[#E8BE72]" />
              <span title={health?.engine?.ffmpeg_error || "Install FFmpeg or configure custom path in Settings"}>
                FFmpeg: <strong className="text-[#E8BE72]">Not Found</strong>
              </span>
            </>
          )}
        </div>

        {/* Free Space Badge */}
        {health?.disk_free_gb && (
          <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#202329] border border-[#2D323B] text-[#A5ABB5]">
            <HardDrive className="w-3.5 h-3.5 text-[#8BC5B0]" />
            <span>Disk Free: <strong className="text-[#F3F4F6]">{health.disk_free_gb} GB</strong></span>
          </div>
        )}

        {/* Open Downloads Folder */}
        <button
          onClick={() => onOpenFile && onOpenFile()}
          className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#F3F4F6] cursor-pointer hover:text-[#8BC5B0]"
          title="Open Downloads Folder in Windows File Explorer"
        >
          <FolderOpen className="w-3.5 h-3.5 text-[#8BC5B0]" />
          <span>Folder</span>
        </button>

        {/* Settings Button */}
        <button
          onClick={onOpenSettings}
          className="neu-raised flex items-center gap-1.5 px-3 py-1.5 text-xs text-[#F3F4F6] cursor-pointer hover:text-[#8BC5B0]"
          title="Open Settings"
        >
          <Settings className="w-3.5 h-3.5" />
          <span>Settings</span>
        </button>
      </div>
    </header>
  );
}
