import React, { useState, useEffect } from "react";
import {
  X,
  Save,
  Folder,
  FolderOpen,
  Layers,
  Check,
  Film,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  HelpCircle,
  Moon,
  Sun,
  Monitor,
} from "lucide-react";
import { validateFFmpeg } from "../api";

export default function SettingsModal({
  isOpen,
  onClose,
  currentSettings,
  onSaveSettings,
  onOpenFile,
  theme,
  onSelectTheme,
}) {
  const [downloadsDir, setDownloadsDir] = useState("");
  const [maxConcurrent, setMaxConcurrent] = useState(2);
  const [defaultMediaType, setDefaultMediaType] = useState("video");
  const [ffmpegPath, setFfmpegPath] = useState("");
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
      setValidationResult(null);
    }
  }, [currentSettings, isOpen]);

  if (!isOpen) return null;

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
    onSaveSettings({
      downloads_dir: downloadsDir,
      max_concurrent_downloads: Number(maxConcurrent),
      default_media_type: defaultMediaType,
      ffmpeg_path: ffmpegPath.trim(),
    });
    setIsSaved(true);
    setTimeout(() => {
      setIsSaved(false);
      onClose();
    }, 800);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/30 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="neu-card w-full max-w-lg p-6 space-y-5 my-8">
        <div className="flex items-center justify-between pb-2 border-b border-slate-200/60">
          <div className="flex items-center gap-2.5">
            <div className="w-2.5 h-2.5 rounded-full bg-[#0084FF]"></div>
            <h2 className="text-base font-bold text-[#1E293B] m-0">Settings &amp; Configuration</h2>
          </div>
          <button
            onClick={onClose}
            className="neu-raised p-2 text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Theme & Visual Style */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-[#1E293B] block">
              Theme &amp; Visual Style
            </label>
            <div className="grid grid-cols-3 gap-2.5">
              <button
                type="button"
                onClick={() => onSelectTheme && onSelectTheme("dark")}
                className={`p-3 rounded-xl flex flex-col items-center gap-1.5 cursor-pointer text-xs font-semibold transition-all ${
                  theme === "dark"
                    ? "neu-accent"
                    : "neu-raised text-[#334155] hover:text-[#0084FF]"
                }`}
              >
                <Moon className="w-4 h-4 text-[#38BDF8]" />
                <span>Cool Dark</span>
              </button>

              <button
                type="button"
                onClick={() => onSelectTheme && onSelectTheme("light")}
                className={`p-3 rounded-xl flex flex-col items-center gap-1.5 cursor-pointer text-xs font-semibold transition-all ${
                  theme === "light"
                    ? "neu-accent"
                    : "neu-raised text-[#334155] hover:text-[#0084FF]"
                }`}
              >
                <Sun className="w-4 h-4 text-[#F59E0B]" />
                <span>Soft Light</span>
              </button>

              <button
                type="button"
                onClick={() => onSelectTheme && onSelectTheme("system")}
                className={`p-3 rounded-xl flex flex-col items-center gap-1.5 cursor-pointer text-xs font-semibold transition-all ${
                  theme === "system"
                    ? "neu-accent"
                    : "neu-raised text-[#334155] hover:text-[#0084FF]"
                }`}
              >
                <Monitor className="w-4 h-4 text-[#64748B]" />
                <span>System Auto</span>
              </button>
            </div>
            <p className="text-[11px] text-[#64748B] font-medium m-0">
              Cool Dark features deep obsidian surfaces, cyber luminescence, and tactile neumorphic shadows.
            </p>
          </div>

          {/* Downloads Directory */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-[#1E293B] block">
              Downloads Directory (Local Storage)
            </label>
            <div className="neu-recessed flex items-center px-3.5 py-2.5 gap-2.5 rounded-xl">
              <Folder className="w-4 h-4 text-[#0084FF] shrink-0" />
              <input
                type="text"
                value={downloadsDir}
                onChange={(e) => setDownloadsDir(e.target.value)}
                className="w-full bg-transparent border-none outline-none text-xs text-[#1E293B] font-mono"
                required
              />
              <button
                type="button"
                onClick={handleOpenFolder}
                disabled={isOpeningFolder}
                className="neu-raised px-3 py-1 text-xs font-semibold text-[#0084FF] hover:text-[#0074E0] flex items-center gap-1.5 shrink-0 cursor-pointer disabled:opacity-50 rounded-lg"
                title="Open downloads folder in Windows File Explorer"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                <span>{isOpeningFolder ? "Opening..." : "Open"}</span>
              </button>
            </div>
            <p className="text-[11px] text-[#64748B] font-medium m-0">
              All downloads will save to this folder on your machine.
            </p>
          </div>

          {/* FFmpeg Configuration Card */}
          <div className="p-4 rounded-2xl neu-raised space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Film className="w-4 h-4 text-[#0084FF]" />
                <span className="text-xs font-bold text-[#1E293B]">
                  FFmpeg Media Engine Integration
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowSetupGuide(!showSetupGuide)}
                className="text-[11px] font-semibold text-[#0084FF] hover:underline flex items-center gap-1 cursor-pointer"
              >
                <HelpCircle className="w-3.5 h-3.5" />
                <span>{showSetupGuide ? "Hide Setup Guide" : "Setup Guide"}</span>
              </button>
            </div>

            <p className="text-xs text-[#64748B] leading-relaxed font-medium m-0">
              Required for merging 1080p+ video with audio streams and converting audio to MP3. Auto-detected from system PATH if blank, or enter a custom path below.
            </p>

            <div className="space-y-2">
              <div className="flex gap-2">
                <div className="neu-recessed flex-1 flex items-center px-3.5 py-2.5 rounded-xl">
                  <input
                    type="text"
                    value={ffmpegPath}
                    onChange={(e) => {
                      setFfmpegPath(e.target.value);
                      setValidationResult(null);
                    }}
                    placeholder="Auto-detect from system PATH, or enter path..."
                    className="w-full bg-transparent border-none outline-none text-xs text-[#1E293B] font-mono placeholder-[#94A3B8]"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleTestFFmpeg}
                  disabled={isValidating}
                  className="neu-raised px-4 py-2.5 text-xs font-semibold text-[#334155] hover:text-[#0084FF] flex items-center gap-1.5 cursor-pointer shrink-0 disabled:opacity-50 rounded-xl"
                  title="Test if FFmpeg executable runs at this path"
                >
                  {isValidating ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
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
                  className="text-[11px] text-[#64748B] hover:text-[#1E293B] cursor-pointer font-medium"
                >
                  Reset to Auto-Detect (System PATH)
                </button>
              )}
            </div>

            {/* Validation Result Box */}
            {validationResult && (
              <div
                className={`p-3 rounded-xl text-xs font-mono flex items-start gap-2.5 ${
                  validationResult.available
                    ? "neu-recessed text-[#10B981] border border-[#10B981]/30"
                    : "bg-[#FEE2E2]/60 border border-[#FCA5A5] text-[#DC2626]"
                }`}
              >
                {validationResult.available ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="font-bold m-0">
                    {validationResult.available ? "FFmpeg Verified & Ready" : "Validation Failed"}
                  </p>
                  {validationResult.version && (
                    <p className="text-[11px] text-[#64748B] truncate m-0 mt-0.5">
                      {validationResult.version}
                    </p>
                  )}
                  {validationResult.path && (
                    <p className="text-[10px] text-[#94A3B8] truncate m-0 mt-0.5">
                      Source: {validationResult.path} ({validationResult.source})
                    </p>
                  )}
                  {validationResult.error && (
                    <p className="text-[11px] text-[#DC2626] m-0 mt-0.5">
                      {validationResult.error}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Setup Guide Dropdown */}
            {showSetupGuide && (
              <div className="p-3.5 rounded-xl neu-recessed text-xs text-[#64748B] space-y-2 font-medium">
                <p className="font-bold text-[#0084FF] m-0">Install FFmpeg on Windows 11:</p>
                <div className="space-y-2 pl-2 border-l border-slate-300">
                  <p className="m-0">
                    <strong className="text-[#1E293B]">Option A (Winget Package):</strong> Open PowerShell and run:
                    <br />
                    <code className="text-[#0084FF] bg-white/70 px-1.5 py-0.5 rounded font-mono">winget install Gyan.FFmpeg</code>
                  </p>
                  <p className="m-0">
                    <strong className="text-[#1E293B]">Option B (Portable on Drive E:):</strong>
                    <br />
                    Extract to: <code className="text-[#0084FF] bg-white/70 px-1.5 py-0.5 rounded font-mono">E:\Code\make thing\tools\ffmpeg\bin\ffmpeg.exe</code> and click Validate!
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Concurrency and Media Type */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-semibold text-[#1E293B] block">
                Max Concurrent Downloads
              </label>
              <select
                value={maxConcurrent}
                onChange={(e) => setMaxConcurrent(e.target.value)}
                className="neu-recessed w-full px-3.5 py-2.5 text-xs text-[#1E293B] outline-none rounded-xl font-medium"
              >
                <option value={1}>1 Download (Conserves CPU)</option>
                <option value={2}>2 Downloads (Default)</option>
                <option value={3}>3 Downloads</option>
                <option value={4}>4 Downloads</option>
              </select>
            </div>

            <div className="space-y-2">
              <label className="text-xs font-semibold text-[#1E293B] block">
                Default Format Type
              </label>
              <div className="flex items-center gap-4 pt-2">
                <label className="flex items-center gap-2 text-xs text-[#1E293B] font-medium cursor-pointer">
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
                <label className="flex items-center gap-2 text-xs text-[#1E293B] font-medium cursor-pointer">
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

          {/* Actions */}
          <div className="pt-3 flex justify-end gap-3 border-t border-slate-200/60">
            <button
              type="button"
              onClick={onClose}
              className="neu-raised px-4 py-2 text-xs font-semibold text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="neu-accent px-5 py-2.5 flex items-center gap-2 text-xs font-semibold cursor-pointer rounded-xl"
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
