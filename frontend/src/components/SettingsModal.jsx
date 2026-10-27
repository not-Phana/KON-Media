import React, { useState, useEffect } from "react";
import { X, Save, Folder, Layers, Check } from "lucide-react";

export default function SettingsModal({ isOpen, onClose, currentSettings, onSaveSettings }) {
  const [downloadsDir, setDownloadsDir] = useState("");
  const [maxConcurrent, setMaxConcurrent] = useState(2);
  const [defaultMediaType, setDefaultMediaType] = useState("video");
  const [isSaved, setIsSaved] = useState(false);

  useEffect(() => {
    if (currentSettings) {
      setDownloadsDir(currentSettings.downloads_dir || "");
      setMaxConcurrent(currentSettings.max_concurrent_downloads || 2);
      setDefaultMediaType(currentSettings.default_media_type || "video");
    }
  }, [currentSettings, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = (e) => {
    e.preventDefault();
    onSaveSettings({
      downloads_dir: downloadsDir,
      max_concurrent_downloads: Number(maxConcurrent),
      default_media_type: defaultMediaType,
    });
    setIsSaved(true);
    setTimeout(() => {
      setIsSaved(false);
      onClose();
    }, 800);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-xs p-4">
      <div className="neu-card w-full max-w-lg p-6 space-y-5 border border-[#383D46]">
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

        <form onSubmit={handleSubmit} className="space-y-4">
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
            </div>
            <p className="text-[11px] text-[#6B7280]">
              Must reside on a local drive with adequate free space (default: E:\Code\make thing\downloads).
            </p>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#A5ABB5] block">
              Max Concurrent Downloads
            </label>
            <select
              value={maxConcurrent}
              onChange={(e) => setMaxConcurrent(e.target.value)}
              className="neu-recessed w-full px-3 py-2 text-xs text-[#F3F4F6] outline-none border border-[#2D323B] rounded-lg"
            >
              <option value={1} className="bg-[#202329]">1 Download (Conserves CPU/Bandwidth)</option>
              <option value={2} className="bg-[#202329]">2 Concurrent Downloads (Recommended)</option>
              <option value={3} className="bg-[#202329]">3 Concurrent Downloads</option>
              <option value={4} className="bg-[#202329]">4 Concurrent Downloads</option>
            </select>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-[#A5ABB5] block">
              Default Format Type
            </label>
            <div className="flex gap-3">
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
                <span>Audio Only (MP3)</span>
              </label>
            </div>
          </div>

          <div className="p-3 rounded-lg bg-[#1A1C22] border border-[#2D323B] text-[11px] text-[#A5ABB5] space-y-1">
            <p className="font-semibold text-[#8BC5B0] m-0">Zero Recurring Cost & Privacy</p>
            <p className="m-0">
              All tasks run 100% locally on your machine. No accounts, subscriptions, analytics, or external cloud storage.
            </p>
          </div>

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
