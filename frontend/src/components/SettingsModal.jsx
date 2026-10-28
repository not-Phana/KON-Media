import React, { useState, useEffect } from "react";
import { X, Save, Folder, FolderOpen, Layers, Check, Film, CheckCircle2, AlertTriangle, Loader2, HelpCircle } from "lucide-react";
import { validateFFmpeg } from "../api";

export default function SettingsModal({ isOpen, onClose, currentSettings, onSaveSettings, onOpenFile }) {
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4 overflow-y-auto">
      <div className="neu-card w-full max-w-lg p-6 space-y-5 border border-[#383D46] my-8">
        <div className="flex items-center justify-between border-b border-[#2D323B] pb-3">
          <div className="flex items-center gap-2">
            <Layers className="w-5 h-5 text-[#8BC5B0]" />
            <h2 className="text-base font-semibold text-[#F3F4F6] m-0">Settings & Configuration</h2>
          </div>
          <button
            onClick={onClose}
            className="text-[#6B7280] hover:text-[#F3F4F6] p-1 cursor-pointer"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-5">
          {/* Downloads Directory */}
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#A5ABB5] block">
              Downloads Directory (Local Storage)
            </label>
            <div className="neu-recessed flex items-center px-3 py-2 gap-2">
              <Folder className="w-4 h-4 text-[#8BC5B0] shrink-0" />
              <input
                type="text"
                value={downloadsDir}
                onChange={(e) => setDownloadsDir(e.target.value)}
                className="w-full bg-transparent border-none outline-none text-xs text-[#F3F4F6] font-mono"
                required
              />
              <button
                type="button"
                onClick={handleOpenFolder}
                disabled={isOpeningFolder}
                className="neu-button px-2.5 py-1 text-xs text-[#8BC5B0] hover:text-white flex items-center gap-1.5 shrink-0 cursor-pointer disabled:opacity-50"
                title="Open downloads folder in Windows File Explorer"
              >
                <FolderOpen className="w-3.5 h-3.5" />
                <span>{isOpeningFolder ? "Opening..." : "Open"}</span>
              </button>
            </div>
            <p className="text-[11px] text-[#6B7280]">
              All downloads will save to this folder on your machine.
            </p>
          </div>

          {/* FFmpeg Configuration Card */}
          <div className="p-4 rounded-xl bg-[#1A1C22] border border-[#2D323B] space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Film className="w-4 h-4 text-[#8BC5B0]" />
                <span className="text-xs font-semibold text-[#F3F4F6]">
                  FFmpeg Media Engine Integration
                </span>
              </div>
              <button
                type="button"
                onClick={() => setShowSetupGuide(!showSetupGuide)}
                className="text-[11px] text-[#8BC5B0] hover:underline flex items-center gap-1 cursor-pointer"
              >
                <HelpCircle className="w-3.5 h-3.5" />
                <span>{showSetupGuide ? "Hide Setup Guide" : "Setup Guide ($0)"}</span>
              </button>
            </div>

            <p className="text-[11px] text-[#A5ABB5] leading-relaxed">
              Required for merging 1080p+ video with audio streams and converting audio to MP3. Auto-detected from system PATH if blank, or enter a custom path below.
            </p>

            <div className="space-y-2">
              <div className="flex gap-2">
                <div className="neu-recessed flex-1 flex items-center px-3 py-2">
                  <input
                    type="text"
                    value={ffmpegPath}
                    onChange={(e) => {
                      setFfmpegPath(e.target.value);
                      setValidationResult(null);
                    }}
                    placeholder="Auto-detect from system PATH, or enter path..."
                    className="w-full bg-transparent border-none outline-none text-xs text-[#F3F4F6] font-mono placeholder-[#6B7280]"
                  />
                </div>
                <button
                  type="button"
                  onClick={handleTestFFmpeg}
                  disabled={isValidating}
                  className="neu-raised px-3 py-2 text-xs text-[#F3F4F6] hover:text-[#8BC5B0] flex items-center gap-1.5 cursor-pointer shrink-0 disabled:opacity-50"
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
                  className="text-[10px] text-[#6B7280] hover:text-[#A5ABB5] cursor-pointer"
                >
                  Reset to Auto-Detect (System PATH)
                </button>
              )}
            </div>

            {/* Validation Result Box */}
            {validationResult && (
              <div
                className={`p-2.5 rounded-lg text-xs font-mono flex items-start gap-2 border ${
                  validationResult.available
                    ? "bg-[#1F2E28] border-[#72C69A]/40 text-[#72C69A]"
                    : "bg-[#2C1D20] border-[#EF8585]/40 text-[#EF8585]"
                }`}
              >
                {validationResult.available ? (
                  <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
                ) : (
                  <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                )}
                <div className="flex-1 min-w-0">
                  <p className="font-semibold m-0">
                    {validationResult.available ? "FFmpeg Verified & Ready" : "Validation Failed"}
                  </p>
                  {validationResult.version && (
                    <p className="text-[11px] text-[#A5ABB5] truncate m-0 mt-0.5">
                      {validationResult.version}
                    </p>
                  )}
                  {validationResult.path && (
                    <p className="text-[10px] text-[#6B7280] truncate m-0 mt-0.5">
                      Source: {validationResult.path} ({validationResult.source})
                    </p>
                  )}
                  {validationResult.error && (
                    <p className="text-[11px] text-[#EF8585] m-0 mt-0.5">
                      {validationResult.error}
                    </p>
                  )}
                </div>
              </div>
            )}

            {/* Setup Guide Dropdown */}
            {showSetupGuide && (
              <div className="p-3 rounded-lg bg-[#131418] border border-[#2D323B] text-[11px] text-[#A5ABB5] space-y-2">
                <p className="font-semibold text-[#8BC5B0] m-0">Two Zero-Cost Ways to Install FFmpeg on Windows 11:</p>
                <div className="space-y-1.5 pl-2 border-l border-[#2D323B]">
                  <p className="m-0">
                    <strong className="text-[#F3F4F6]">Option A (Winget Package):</strong> Open PowerShell and run:
                    <br />
                    <code className="text-[#8BC5B0] bg-[#1A1C22] px-1.5 py-0.5 rounded">winget install Gyan.FFmpeg</code>
                    <br />
                    Then restart KON Media to auto-detect.
                  </p>
                  <p className="m-0 pt-1">
                    <strong className="text-[#F3F4F6]">Option B (Portable on Drive E:):</strong>
                    <br />
                    1. Download the free release build from <span className="text-[#8BC5B0]">gyan.dev/ffmpeg/builds</span>.
                    <br />
                    2. Extract to: <code className="text-[#8BC5B0]">E:\Code\make thing\tools\ffmpeg\</code>.
                    <br />
                    3. Enter path above: <code className="text-[#8BC5B0]">E:\Code\make thing\tools\ffmpeg\bin\ffmpeg.exe</code> and click Validate!
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Concurrency and Media Type */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[#A5ABB5] block">
                Max Concurrent Downloads
              </label>
              <select
                value={maxConcurrent}
                onChange={(e) => setMaxConcurrent(e.target.value)}
                className="neu-recessed w-full px-3 py-2 text-xs text-[#F3F4F6] outline-none border border-[#2D323B] rounded-lg"
              >
                <option value={1} className="bg-[#202329]">1 Download (Conserves CPU)</option>
                <option value={2} className="bg-[#202329]">2 Downloads (Default)</option>
                <option value={3} className="bg-[#202329]">3 Downloads</option>
                <option value={4} className="bg-[#202329]">4 Downloads</option>
              </select>
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-medium text-[#A5ABB5] block">
                Default Format Type
              </label>
              <div className="flex items-center gap-4 pt-2">
                <label className="flex items-center gap-2 text-xs text-[#F3F4F6] cursor-pointer">
                  <input
                    type="radio"
                    name="mediaType"
                    value="video"
                    checked={defaultMediaType === "video"}
                    onChange={() => setDefaultMediaType("video")}
                    className="accent-[#8BC5B0]"
                  />
                  <span>Video (MP4)</span>
                </label>
                <label className="flex items-center gap-2 text-xs text-[#F3F4F6] cursor-pointer">
                  <input
                    type="radio"
                    name="mediaType"
                    value="audio"
                    checked={defaultMediaType === "audio"}
                    onChange={() => setDefaultMediaType("audio")}
                    className="accent-[#8BC5B0]"
                  />
                  <span>Audio (MP3)</span>
                </label>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="pt-3 flex justify-end gap-2 border-t border-[#2D323B]">
            <button
              type="button"
              onClick={onClose}
              className="neu-raised px-4 py-2 text-xs text-[#A5ABB5] cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="neu-accent px-4 py-2 flex items-center gap-1.5 text-xs font-semibold cursor-pointer"
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
