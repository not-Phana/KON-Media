import React, { useState, useEffect } from "react";
import {
  X,
  Save,
  Folder,
  FolderOpen,
  Check,
  Film,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  HelpCircle,
  Moon,
  Sun,
  Monitor,
  Globe,
  Sparkles,
  Sliders,
  HardDrive,
  Image as ImageIcon,
  Upload,
  Trash2,
  Link2,
} from "lucide-react";
import { validateFFmpeg, getCustomBackendUrl, setCustomBackendUrl } from "../api";

const WALLPAPER_PRESETS = [
  {
    id: "obsidian-ember",
    name: "Obsidian Ember",
    value: "radial-gradient(ellipse at bottom left, #451a03 0%, #18181b 50%, #09090b 100%)",
    style: "radial-gradient(ellipse at bottom left, #451a03 0%, #18181b 50%, #09090b 100%)",
  },
  {
    id: "cosmic-void",
    name: "Cosmic Void",
    value: "radial-gradient(ellipse at top right, #1e1b4b 0%, #0f172a 50%, #030712 100%)",
    style: "radial-gradient(ellipse at top right, #1e1b4b 0%, #0f172a 50%, #030712 100%)",
  },
  {
    id: "cyber-synth",
    name: "Cyber Synth",
    value: "radial-gradient(ellipse at top left, #0e7490 0%, #0f172a 50%, #020617 100%)",
    style: "radial-gradient(ellipse at top left, #0e7490 0%, #0f172a 50%, #020617 100%)",
  },
  {
    id: "anime-twilight",
    name: "Anime Twilight",
    value: "radial-gradient(ellipse at center, #311042 0%, #110d21 55%, #05040a 100%)",
    style: "radial-gradient(ellipse at center, #311042 0%, #110d21 55%, #05040a 100%)",
  },
];

export default function SettingsModal({
  isOpen,
  onClose,
  currentSettings,
  onSaveSettings,
  onOpenFile,
  theme,
  onSelectTheme,
  glassMode,
  onToggleGlassMode,
  customWallpaper,
  onSelectWallpaper,
}) {
  const [activeTab, setActiveTab] = useState("general"); // "general" | "storage" | "advanced"
  const [downloadsDir, setDownloadsDir] = useState("");
  const [maxConcurrent, setMaxConcurrent] = useState(2);
  const [defaultMediaType, setDefaultMediaType] = useState("video");
  const [ffmpegPath, setFfmpegPath] = useState("");
  const [glassModeEnabled, setGlassModeEnabled] = useState(false);
  const [wallpaper, setWallpaper] = useState(customWallpaper || "");
  const [urlInput, setUrlInput] = useState("");
  const [backendUrl, setBackendUrlState] = useState(() => getCustomBackendUrl());
  const [isSaved, setIsSaved] = useState(false);
  const [isOpeningFolder, setIsOpeningFolder] = useState(false);

  // FFmpeg validation state
  const [isValidating, setIsValidating] = useState(false);
  const [validationResult, setValidationResult] = useState(null);
  const [showSetupGuide, setShowSetupGuide] = useState(false);

  useEffect(() => {
    if (currentSettings) {
      setDownloadsDir(currentSettings.downloads_dir || "");
      setMaxConcurrent(currentSettings.max_concurrent_downloads || 2);
      setDefaultMediaType(currentSettings.default_media_type || "video");
      setFfmpegPath(currentSettings.ffmpeg_path || "");
      setGlassModeEnabled(Boolean(currentSettings.glass_mode ?? glassMode));
      setWallpaper(currentSettings.custom_wallpaper ?? customWallpaper ?? "");
      setValidationResult(null);
    }
  }, [currentSettings, isOpen, glassMode, customWallpaper]);

  if (!isOpen) return null;

  const handleToggleGlass = (enabled) => {
    setGlassModeEnabled(enabled);
    if (onToggleGlassMode) {
      onToggleGlassMode(enabled);
    }
  };

  const handleApplyWallpaper = (wp) => {
    setWallpaper(wp);
    if (onSelectWallpaper) {
      onSelectWallpaper(wp);
    }
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (loadEvent) => {
      const dataUrl = loadEvent.target.result;
      const img = new window.Image();
      img.onload = () => {
        const MAX_WIDTH = 1920;
        const MAX_HEIGHT = 1080;
        let width = img.width;
        let height = img.height;
        if (width > MAX_WIDTH || height > MAX_HEIGHT) {
          if (width / height > MAX_WIDTH / MAX_HEIGHT) {
            height = Math.round((height * MAX_WIDTH) / width);
            width = MAX_WIDTH;
          } else {
            width = Math.round((width * MAX_HEIGHT) / height);
            height = MAX_HEIGHT;
          }
        }
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, width, height);
        const optimized = canvas.toDataURL("image/jpeg", 0.88);
        handleApplyWallpaper(optimized);
      };
      img.onerror = () => {
        handleApplyWallpaper(dataUrl);
      };
      img.src = dataUrl;
    };
    reader.readAsDataURL(file);
    e.target.value = "";
  };

  const handleOpenFolder = async () => {
    if (!onOpenFile) return;
    setIsOpeningFolder(true);
    try {
      await onOpenFile(downloadsDir);
    } finally {
      setTimeout(() => setIsOpeningFolder(false), 1200);
    }
  };

  const handleTestFFmpeg = async () => {
    setIsValidating(true);
    setValidationResult(null);
    try {
      const res = await validateFFmpeg(ffmpegPath);
      setValidationResult(res);
    } catch (err) {
      setValidationResult({
        available: false,
        error: err.message || "Failed to validate path",
      });
    } finally {
      setIsValidating(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    setCustomBackendUrl(backendUrl);
    onSaveSettings({
      downloads_dir: downloadsDir,
      max_concurrent_downloads: Number(maxConcurrent),
      default_media_type: defaultMediaType,
      ffmpeg_path: ffmpegPath.trim(),
      glass_mode: glassModeEnabled,
      custom_wallpaper: wallpaper,
    });
    setIsSaved(true);
    setTimeout(() => {
      setIsSaved(false);
      onClose();
    }, 800);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/60 neu-popup-backdrop p-4 overflow-y-auto">
      <div className="neu-card neu-popup-spring neu-popup-aura w-full max-w-lg max-h-[88vh] flex flex-col border border-[#0084FF]/25 shadow-2xl overflow-hidden rounded-2xl">
        {/* Header (Always Visible) */}
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-slate-200/60 dark:border-slate-800 shrink-0">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-[#0084FF] shadow-[0_0_8px_rgba(0,132,255,0.6)]" />
            <h2 className="text-sm font-bold text-[#1E293B] dark:text-[#F8FAFC] m-0">Settings</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="neu-raised p-1.5 text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F8FAFC] cursor-pointer rounded-lg neu-btn-elastic"
            title="Close Settings (Esc)"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab Switcher Pills */}
        <div className="flex items-center gap-1.5 px-5 pt-3 pb-1 shrink-0 bg-slate-100/50 dark:bg-slate-900/30 border-b border-slate-200/40 dark:border-slate-800/40">
          <button
            type="button"
            onClick={() => setActiveTab("general")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 neu-btn-tactile ${
              activeTab === "general"
                ? "neu-accent shadow-sm"
                : "text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B] dark:hover:text-[#F8FAFC]"
            }`}
          >
            <Sparkles className="w-3.5 h-3.5" />
            <span>Appearance</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("storage")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 neu-btn-tactile ${
              activeTab === "storage"
                ? "neu-accent shadow-sm"
                : "text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B] dark:hover:text-[#F8FAFC]"
            }`}
          >
            <HardDrive className="w-3.5 h-3.5" />
            <span>Storage &amp; Downloads</span>
          </button>

          <button
            type="button"
            onClick={() => setActiveTab("advanced")}
            className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-all cursor-pointer flex items-center gap-1.5 neu-btn-tactile ${
              activeTab === "advanced"
                ? "neu-accent shadow-sm"
                : "text-[#64748B] dark:text-[#94A3B8] hover:text-[#1E293B] dark:hover:text-[#F8FAFC]"
            }`}
          >
            <Sliders className="w-3.5 h-3.5" />
            <span>Engine &amp; Cloud</span>
          </button>
        </div>

        {/* Scrollable Form Body (Strictly constrained height) */}
        <form onSubmit={handleSubmit} className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <div className="flex-1 overflow-y-auto p-5 space-y-4 neu-custom-scrollbar">
            {/* TAB 1: APPEARANCE */}
            {activeTab === "general" && (
              <div className="space-y-4 animate-in fade-in duration-150">
                {/* Theme Selector */}
                <div className="space-y-2">
                  <label className="text-xs font-bold text-[#1E293B] dark:text-[#F8FAFC] block">
                    Theme &amp; Visual Style
                  </label>
                  <div className="grid grid-cols-3 gap-2">
                    <button
                      type="button"
                      onClick={() => onSelectTheme && onSelectTheme("dark")}
                      className={`p-2.5 rounded-xl flex items-center justify-center gap-2 cursor-pointer text-xs font-semibold transition-all ${
                        theme === "dark"
                          ? "neu-accent"
                          : "neu-raised text-[#334155] dark:text-[#E2E8F0] hover:text-[#0084FF]"
                      }`}
                    >
                      <Moon className="w-3.5 h-3.5 text-[#38BDF8]" />
                      <span>Cool Dark</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => onSelectTheme && onSelectTheme("light")}
                      className={`p-2.5 rounded-xl flex items-center justify-center gap-2 cursor-pointer text-xs font-semibold transition-all ${
                        theme === "light"
                          ? "neu-accent"
                          : "neu-raised text-[#334155] dark:text-[#E2E8F0] hover:text-[#0084FF]"
                      }`}
                    >
                      <Sun className="w-3.5 h-3.5 text-[#F59E0B]" />
                      <span>Soft Light</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => onSelectTheme && onSelectTheme("system")}
                      className={`p-2.5 rounded-xl flex items-center justify-center gap-2 cursor-pointer text-xs font-semibold transition-all ${
                        theme === "system"
                          ? "neu-accent"
                          : "neu-raised text-[#334155] dark:text-[#E2E8F0] hover:text-[#0084FF]"
                      }`}
                    >
                      <Monitor className="w-3.5 h-3.5 text-[#64748B]" />
                      <span>System Auto</span>
                    </button>
                  </div>
                </div>

                {/* Glass Mode Card */}
                <div className="p-3.5 rounded-xl neu-raised border border-slate-200/60 dark:border-slate-800 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Sparkles className={`w-4 h-4 ${glassModeEnabled ? "text-[#F59E0B]" : "text-[#64748B]"}`} />
                      <div>
                        <span className="text-xs font-bold text-[#1E293B] dark:text-[#F8FAFC] block">
                          Glass Mode
                        </span>
                        <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8]">
                          Frosted charcoal surfaces &amp; warm gold highlights
                        </span>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleToggleGlass(!glassModeEnabled)}
                      className={`relative w-11 h-6 rounded-full transition-colors duration-250 cursor-pointer focus:outline-none p-0.5 shrink-0 ${
                        glassModeEnabled
                          ? "bg-[#D97706] shadow-[0_0_10px_rgba(217,119,6,0.4)]"
                          : "neu-recessed bg-slate-300 dark:bg-slate-800"
                      }`}
                      role="switch"
                      aria-checked={glassModeEnabled}
                      title={glassModeEnabled ? "Turn Glass Mode OFF" : "Turn Glass Mode ON"}
                    >
                      <div
                        className={`w-5 h-5 rounded-full bg-white shadow-sm transform transition-transform duration-200 ${
                          glassModeEnabled ? "translate-x-5" : "translate-x-0"
                        }`}
                      />
                    </button>
                  </div>
                </div>

                {/* Custom Wallpaper Section */}
                <div className="p-3.5 rounded-xl neu-raised border border-slate-200/60 dark:border-slate-800 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <ImageIcon className={`w-4 h-4 ${wallpaper ? "text-[#F59E0B]" : "text-[#64748B]"}`} />
                      <div>
                        <span className="text-xs font-bold text-[#1E293B] dark:text-[#F8FAFC] block">
                          Custom Wallpaper
                        </span>
                        <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8]">
                          Background visible through frosted glass cards (5px corner radius)
                        </span>
                      </div>
                    </div>
                    {wallpaper ? (
                      <button
                        type="button"
                        onClick={() => handleApplyWallpaper("")}
                        className="px-2 py-1 rounded text-[11px] font-semibold text-rose-400 hover:text-rose-300 bg-rose-500/10 hover:bg-rose-500/20 transition-colors flex items-center gap-1 cursor-pointer"
                        title="Remove custom wallpaper and return to default ambient reflection"
                      >
                        <Trash2 className="w-3 h-3" />
                        <span>Remove</span>
                      </button>
                    ) : (
                      <span className="text-[10px] text-[#64748B] dark:text-[#94A3B8] font-medium">
                        Default Ambient
                      </span>
                    )}
                  </div>

                  {/* Active Preview Thumbnail if set */}
                  {wallpaper && (
                    <div className="relative h-20 rounded-lg overflow-hidden border border-white/20 shadow-inner group">
                      <div
                        className="w-full h-full bg-cover bg-center"
                        style={
                          wallpaper.startsWith("data:") ||
                          wallpaper.startsWith("http") ||
                          wallpaper.startsWith("/") ||
                          wallpaper.startsWith("file:")
                            ? { backgroundImage: `url(${wallpaper})` }
                            : { background: wallpaper }
                        }
                      />
                      <div className="absolute inset-0 bg-black/30 backdrop-blur-[2px] flex items-center justify-center p-2">
                        <div className="glass-card px-3 py-1 text-[11px] font-bold text-white shadow-lg flex items-center gap-1.5">
                          <Check className="w-3 h-3 text-[#10B981]" />
                          <span>Active Wallpaper (5px Corner Radius)</span>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* File Upload & URL Inputs */}
                  <div className="space-y-2">
                    <label className="neu-recessed hover:bg-slate-200/50 dark:hover:bg-slate-800/50 px-3 py-2 rounded-lg text-xs font-semibold flex items-center justify-center gap-1.5 cursor-pointer text-[#1E293B] dark:text-[#F8FAFC] transition-colors border border-slate-200/60 dark:border-slate-800">
                      <Upload className="w-3.5 h-3.5 text-[#0084FF]" />
                      <span>Upload Wallpaper / Artwork</span>
                      <input
                        type="file"
                        accept="image/*"
                        className="hidden"
                        onChange={handleFileUpload}
                      />
                    </label>

                    <div className="flex items-center gap-1.5">
                      <div className="relative flex-1">
                        <Link2 className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
                        <input
                          type="url"
                          value={urlInput}
                          onChange={(e) => setUrlInput(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              e.preventDefault();
                              if (urlInput.trim()) {
                                handleApplyWallpaper(urlInput.trim());
                                setUrlInput("");
                              }
                            }
                          }}
                          placeholder="Or paste wallpaper image URL..."
                          className="w-full text-xs pl-8 pr-2.5 py-1.5 neu-recessed rounded-lg border border-slate-200/60 dark:border-slate-800 text-[#1E293B] dark:text-[#F8FAFC] focus:outline-none"
                        />
                      </div>
                      <button
                        type="button"
                        onClick={() => {
                          if (urlInput.trim()) {
                            handleApplyWallpaper(urlInput.trim());
                            setUrlInput("");
                          }
                        }}
                        disabled={!urlInput.trim()}
                        className="px-3 py-1.5 neu-accent rounded-lg text-xs font-bold disabled:opacity-40 cursor-pointer transition-opacity"
                      >
                        Apply
                      </button>
                    </div>
                  </div>

                  {/* Curated Dark Atmosphere Presets */}
                  <div className="space-y-1.5 pt-1">
                    <span className="text-[10px] font-bold text-[#64748B] dark:text-[#94A3B8] uppercase tracking-wider block">
                      Atmosphere Presets
                    </span>
                    <div className="grid grid-cols-4 gap-1.5">
                      {WALLPAPER_PRESETS.map((preset) => (
                        <button
                          key={preset.id}
                          type="button"
                          onClick={() => handleApplyWallpaper(preset.value)}
                          className={`h-11 rounded-md overflow-hidden relative border transition-all cursor-pointer group ${
                            wallpaper === preset.value
                              ? "border-[#F59E0B] shadow-[0_0_8px_rgba(245,158,11,0.5)] ring-1 ring-[#F59E0B]"
                              : "border-slate-700/60 hover:border-slate-400"
                          }`}
                          style={{
                            background: preset.style,
                          }}
                          title={preset.name}
                        >
                          <span className="absolute inset-x-0 bottom-0 py-0.5 bg-black/60 backdrop-blur-[2px] text-[9px] font-bold text-white text-center truncate px-1">
                            {preset.name}
                          </span>
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Default Format Type */}
                <div className="space-y-1.5 pt-1 border-t border-slate-200/40 dark:border-slate-800/40">
                  <label className="text-xs font-bold text-[#1E293B] dark:text-[#F8FAFC] block">
                    Default 1-Click Download Format
                  </label>
                  <div className="grid grid-cols-2 gap-2">
                    <label
                      className={`neu-recessed p-2.5 rounded-xl flex items-center gap-2 text-xs font-semibold cursor-pointer border ${
                        defaultMediaType === "video"
                          ? "border-[#0084FF]/40 text-[#0084FF] bg-[#0084FF]/5"
                          : "border-transparent text-[#64748B] dark:text-[#94A3B8]"
                      }`}
                    >
                      <input
                        type="radio"
                        name="mediaType"
                        value="video"
                        checked={defaultMediaType === "video"}
                        onChange={() => setDefaultMediaType("video")}
                        className="accent-[#0084FF]"
                      />
                      <span>Video (MP4)</span>
                    </label>

                    <label
                      className={`neu-recessed p-2.5 rounded-xl flex items-center gap-2 text-xs font-semibold cursor-pointer border ${
                        defaultMediaType === "audio"
                          ? "border-[#0084FF]/40 text-[#0084FF] bg-[#0084FF]/5"
                          : "border-transparent text-[#64748B] dark:text-[#94A3B8]"
                      }`}
                    >
                      <input
                        type="radio"
                        name="mediaType"
                        value="audio"
                        checked={defaultMediaType === "audio"}
                        onChange={() => setDefaultMediaType("audio")}
                        className="accent-[#0084FF]"
                      />
                      <span>Audio (MP3)</span>
                    </label>
                  </div>
                </div>
              </div>
            )}

            {/* TAB 2: STORAGE & DOWNLOADS */}
            {activeTab === "storage" && (
              <div className="space-y-4 animate-in fade-in duration-150">
                {/* Downloads Directory */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1E293B] dark:text-[#F8FAFC] block">
                    Downloads Directory
                  </label>
                  <div className="neu-recessed flex items-center px-3 py-2 gap-2 rounded-xl">
                    <Folder className="w-4 h-4 text-[#0084FF] shrink-0" />
                    <input
                      type="text"
                      value={downloadsDir}
                      onChange={(e) => setDownloadsDir(e.target.value)}
                      className="w-full bg-transparent border-none outline-none text-xs text-[#1E293B] dark:text-[#F8FAFC] font-mono truncate"
                      required
                    />
                    <button
                      type="button"
                      onClick={handleOpenFolder}
                      disabled={isOpeningFolder}
                      className="neu-raised px-2.5 py-1 text-xs font-bold text-[#0084FF] hover:text-[#0074E0] flex items-center gap-1 shrink-0 cursor-pointer disabled:opacity-50 rounded-lg neu-btn-tactile"
                      title="Open in Windows File Explorer"
                    >
                      <FolderOpen className="w-3.5 h-3.5" />
                      <span>{isOpeningFolder ? "Opening..." : "Open"}</span>
                    </button>
                  </div>
                </div>

                {/* Max Concurrent Downloads */}
                <div className="space-y-1.5">
                  <label className="text-xs font-bold text-[#1E293B] dark:text-[#F8FAFC] block">
                    Max Concurrent Downloads
                  </label>
                  <select
                    value={maxConcurrent}
                    onChange={(e) => setMaxConcurrent(e.target.value)}
                    className="neu-recessed w-full px-3 py-2 text-xs text-[#1E293B] dark:text-[#F8FAFC] outline-none rounded-xl font-medium"
                  >
                    <option value={1}>1 Download (Light CPU)</option>
                    <option value={2}>2 Downloads (Recommended)</option>
                    <option value={3}>3 Downloads</option>
                    <option value={4}>4 Downloads (Fast Internet)</option>
                  </select>
                </div>
              </div>
            )}

            {/* TAB 3: ENGINE & CLOUD */}
            {activeTab === "advanced" && (
              <div className="space-y-3.5 animate-in fade-in duration-150">
                {/* FFmpeg Integration */}
                <div className="p-3.5 rounded-xl neu-raised space-y-2 border border-slate-200/60 dark:border-slate-800">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-1.5">
                      <Film className="w-3.5 h-3.5 text-[#0084FF]" />
                      <span className="text-xs font-bold text-[#1E293B] dark:text-[#F8FAFC]">
                        FFmpeg Media Engine
                      </span>
                    </div>
                    <button
                      type="button"
                      onClick={() => setShowSetupGuide(!showSetupGuide)}
                      className="text-[10px] font-bold text-[#0084FF] hover:underline flex items-center gap-1 cursor-pointer"
                    >
                      <HelpCircle className="w-3 h-3" />
                      <span>{showSetupGuide ? "Hide Guide" : "Install Guide"}</span>
                    </button>
                  </div>

                  <div className="flex gap-2">
                    <div className="neu-recessed flex-1 flex items-center px-3 py-2 rounded-xl">
                      <input
                        type="text"
                        value={ffmpegPath}
                        onChange={(e) => {
                          setFfmpegPath(e.target.value);
                          setValidationResult(null);
                        }}
                        placeholder="Auto-detect from system PATH..."
                        className="w-full bg-transparent border-none outline-none text-xs text-[#1E293B] dark:text-[#F8FAFC] font-mono placeholder-[#94A3B8]"
                      />
                    </div>
                    <button
                      type="button"
                      onClick={handleTestFFmpeg}
                      disabled={isValidating}
                      className="neu-raised px-3 py-2 text-xs font-bold text-[#334155] dark:text-[#E2E8F0] hover:text-[#0084FF] flex items-center gap-1.5 cursor-pointer shrink-0 disabled:opacity-50 rounded-xl neu-btn-tactile"
                    >
                      {isValidating ? (
                        <Loader2 className="w-3 h-3 animate-spin" />
                      ) : (
                        <span>Validate</span>
                      )}
                    </button>
                  </div>

                  {ffmpegPath && (
                    <button
                      type="button"
                      onClick={() => {
                        setFfmpegPath("");
                        setValidationResult(null);
                      }}
                      className="text-[10px] text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F8FAFC] cursor-pointer font-medium"
                    >
                      Reset to Auto-Detect
                    </button>
                  )}

                  {validationResult && (
                    <div
                      className={`p-2.5 rounded-xl text-xs font-mono flex items-start gap-2 ${
                        validationResult.available
                          ? "neu-recessed text-[#10B981] border border-[#10B981]/30"
                          : "bg-[#FEE2E2]/60 border border-[#FCA5A5] text-[#DC2626]"
                      }`}
                    >
                      {validationResult.available ? (
                        <CheckCircle2 className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      ) : (
                        <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1 min-w-0">
                        <p className="font-bold m-0 text-xs">
                          {validationResult.available ? "FFmpeg Ready" : "Validation Failed"}
                        </p>
                        {validationResult.version && (
                          <p className="text-[10px] text-[#64748B] truncate m-0">
                            {validationResult.version}
                          </p>
                        )}
                      </div>
                    </div>
                  )}

                  {showSetupGuide && (
                    <div className="p-2.5 rounded-xl neu-recessed text-[11px] text-[#64748B] dark:text-[#94A3B8] space-y-1 font-medium">
                      <p className="font-bold text-[#0084FF] m-0">Install on Windows 11:</p>
                      <code className="text-[#0084FF] bg-black/20 px-1 py-0.5 rounded font-mono text-[10px] block">
                        winget install Gyan.FFmpeg
                      </code>
                    </div>
                  )}
                </div>

                {/* Cloud Backend Server URL */}
                <div className="space-y-1.5 pt-1 border-t border-slate-200/40 dark:border-slate-800/40">
                  <div className="flex items-center gap-1.5">
                    <Globe className="w-3.5 h-3.5 text-[#0084FF]" />
                    <label className="text-xs font-bold text-[#1E293B] dark:text-[#F8FAFC]">
                      Cloud Backend URL (Optional)
                    </label>
                  </div>
                  <div className="neu-recessed flex items-center px-3 py-2 rounded-xl">
                    <input
                      type="text"
                      value={backendUrl}
                      onChange={(e) => setBackendUrlState(e.target.value)}
                      placeholder="Leave blank for local 127.0.0.1:8899"
                      className="w-full bg-transparent border-none outline-none text-xs text-[#1E293B] dark:text-[#E2E8F0] font-mono placeholder-[#94A3B8]"
                    />
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Sticky Actions Footer (Never Cut Off!) */}
          <div className="px-5 py-3 flex justify-end gap-2.5 border-t border-slate-200/60 dark:border-slate-800 bg-slate-100/40 dark:bg-slate-900/40 shrink-0">
            <button
              type="button"
              onClick={onClose}
              className="neu-raised px-4 py-2 text-xs font-bold text-[#64748B] hover:text-[#1E293B] dark:hover:text-[#F8FAFC] cursor-pointer rounded-xl neu-btn-tactile"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="neu-accent px-5 py-2 flex items-center gap-1.5 text-xs font-bold cursor-pointer rounded-xl neu-btn-elastic shadow-md"
            >
              {isSaved ? (
                <>
                  <Check className="w-3.5 h-3.5" />
                  <span>Saved!</span>
                </>
              ) : (
                <>
                  <Save className="w-3.5 h-3.5" />
                  <span>Save Settings</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
