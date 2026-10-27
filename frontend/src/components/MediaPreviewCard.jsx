import React, { useState } from "react";
import {
  Video,
  Music,
  Download,
  Clock,
  User,
  AlertTriangle,
  X,
  ShieldAlert,
  ExternalLink,
  Info,
} from "lucide-react";
import { openExternalUrl } from "../api";

export default function MediaPreviewCard({ mediaInfo, onStartDownload, onDismiss }) {
  const [mediaType, setMediaType] = useState("video");
  const [isOpeningSpotify, setIsOpeningSpotify] = useState(false);

  // If this is a Spotify URL or unsupported DRM source, render the dedicated Spotify view
  const isSpotify =
    mediaInfo?.source === "spotify" ||
    mediaInfo?.is_unsupported_source ||
    mediaInfo?.supported === false;

  // Selected formats
  const defaultVideoFormat =
    mediaInfo?.video_formats?.find((f) => !f.requires_ffmpeg) ||
    mediaInfo?.video_formats?.[0];

  const defaultAudioFormat =
    mediaInfo?.audio_formats?.find((f) => !f.requires_ffmpeg) ||
    mediaInfo?.audio_formats?.[0];

  const [selectedFormatId, setSelectedFormatId] = useState(
    defaultVideoFormat?.format_id || "best"
  );
  const [selectedAudioBitrate, setSelectedAudioBitrate] = useState(
    defaultAudioFormat?.bitrate || "320k"
  );

  if (!mediaInfo) return null;

  // Render Spotify Source / Unsupported DRM View
  if (isSpotify) {
    const handleOpenSpotify = async (e) => {
      e.preventDefault();
      setIsOpeningSpotify(true);
      try {
        const url = mediaInfo.open_in_spotify_url || mediaInfo.webpage_url;
        window.open(url, "_blank", "noopener,noreferrer");
        await openExternalUrl(url).catch(() => {});
      } finally {
        setTimeout(() => setIsOpeningSpotify(false), 1000);
      }
    };

    return (
      <div className="neu-card p-6 space-y-5 border border-[#383D46]">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-[#1DB954]/15 text-[#1DB954] border border-[#1DB954]/30 flex items-center gap-1.5">
                <Music className="w-3 h-3" />
                Spotify Source
              </span>
              <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[#272B32] text-[#E8BE72] border border-[#383D46]">
                DRM-Protected Stream
              </span>
            </div>
            <h2 className="text-lg font-semibold text-[#F3F4F6] truncate m-0">
              {mediaInfo.title || "Spotify Music"}
            </h2>
            <p className="text-xs text-[#A5ABB5] mt-1 m-0 truncate">
              {mediaInfo.webpage_url}
            </p>
          </div>

          <button
            onClick={onDismiss}
            className="text-[#6B7280] hover:text-[#F3F4F6] p-1.5 rounded-lg hover:bg-[#272B32] transition-colors cursor-pointer"
            title="Dismiss preview"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Guidance and Explanation Box */}
        <div className="p-4 rounded-xl bg-[#17191E] border border-[#2D323B] space-y-3">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-[#E8BE72] shrink-0 mt-0.5" />
            <div className="space-y-1.5 text-xs">
              <p className="font-semibold text-[#F3F4F6] m-0">
                Audio Stream Cannot Be Exported
              </p>
              <p className="text-[#A5ABB5] leading-relaxed m-0">
                {mediaInfo.message ||
                  "Spotify music streams are protected by Digital Rights Management (DRM) and cannot be exported as MP3 files."}
              </p>
              <p className="text-[#A5ABB5] leading-relaxed m-0">
                {mediaInfo.guidance ||
                  "To download music for offline listening, please use the official Spotify desktop or mobile application. Spotify's supported offline-download functionality operates exclusively inside Spotify."}
              </p>
            </div>
          </div>

          <div className="pt-2 border-t border-[#252932] flex items-center gap-2 text-[11px] text-[#6B7280]">
            <Info className="w-3.5 h-3.5 shrink-0" />
            <span>
              This is a copyright protection enforced by Spotify, not an FFmpeg or configuration issue.
            </span>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onDismiss}
            className="neu-button px-4 py-2 text-xs font-medium cursor-pointer"
          >
            Dismiss
          </button>

          <a
            href={mediaInfo.open_in_spotify_url || mediaInfo.webpage_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={handleOpenSpotify}
            className="neu-accent px-5 py-2.5 flex items-center gap-2 text-xs font-semibold cursor-pointer no-underline text-white hover:brightness-110"
          >
            <ExternalLink className="w-4 h-4" />
            <span>{isOpeningSpotify ? "Opening..." : "Open in Spotify"}</span>
          </a>
        </div>
      </div>
    );
  }

  // Standard Media Preview
  const isVideo = mediaType === "video";
  const selectedFormat = isVideo
    ? mediaInfo.video_formats?.find((f) => f.format_id === selectedFormatId)
    : null;

  const selectedAudioFormat = !isVideo
    ? mediaInfo.audio_formats?.find((f) => f.bitrate === selectedAudioBitrate)
    : null;

  const ffmpegAvailable = Boolean(mediaInfo.ffmpeg_available);
  const isBlockedByMissingFfmpeg =
    !ffmpegAvailable &&
    (isVideo ? selectedFormat?.requires_ffmpeg : selectedAudioFormat?.requires_ffmpeg);

  const handleDownload = () => {
    if (isBlockedByMissingFfmpeg) return;

    onStartDownload({
      url: mediaInfo.webpage_url,
      title: mediaInfo.title,
      format_id: isVideo
        ? selectedFormatId
        : selectedAudioFormat?.format_id || "bestaudio/best",
      media_type: mediaType,
      ext: isVideo ? "mp4" : selectedAudioFormat?.ext || "mp3",
      audio_bitrate: selectedAudioBitrate,
      thumbnail: mediaInfo.thumbnail,
      duration: mediaInfo.duration,
    });
  };

  return (
    <div className="neu-card p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[#272B32] text-[#8BC5B0] border border-[#383D46]">
              {mediaInfo.extractor || "Media"}
            </span>
            {mediaInfo.duration_formatted && (
              <span className="flex items-center gap-1 text-[11px] text-[#A5ABB5] font-mono">
                <Clock className="w-3 h-3" />
                {mediaInfo.duration_formatted}
              </span>
            )}
          </div>
          <h2 className="text-base font-semibold text-[#F3F4F6] truncate m-0" title={mediaInfo.title}>
            {mediaInfo.title}
          </h2>
          <p className="flex items-center gap-1 text-xs text-[#A5ABB5] mt-1 m-0">
            <User className="w-3.5 h-3.5" />
            <span>{mediaInfo.uploader}</span>
          </p>
        </div>

        <button
          onClick={onDismiss}
          className="text-[#6B7280] hover:text-[#F3F4F6] p-1 cursor-pointer"
          title="Dismiss preview"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-5">
        {/* Thumbnail Container */}
        {mediaInfo.thumbnail && (
          <div className="relative w-full md:w-56 h-36 rounded-xl overflow-hidden bg-[#131418] border border-[#2D323B] shrink-0">
            <img
              src={mediaInfo.thumbnail}
              alt={mediaInfo.title}
              className="w-full h-full object-cover"
              crossOrigin="anonymous"
              referrerPolicy="no-referrer"
            />
            {mediaInfo.duration_formatted && (
              <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 text-[10px] font-mono text-white">
                {mediaInfo.duration_formatted}
              </div>
            )}
          </div>
        )}

        {/* Format Selector Column */}
        <div className="flex-1 space-y-4">
          {/* Media Type Toggle: Video vs Audio */}
          <div className="flex items-center gap-2 p-1 rounded-xl bg-[#131418] border border-[#2D323B] w-fit">
            <button
              type="button"
              onClick={() => setMediaType("video")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
                mediaType === "video" ? "neu-pill-active" : "neu-pill-inactive"
              }`}
            >
              <Video className="w-3.5 h-3.5" />
              <span>Video (MP4)</span>
            </button>
            <button
              type="button"
              onClick={() => setMediaType("audio")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
                mediaType === "audio" ? "neu-pill-active" : "neu-pill-inactive"
              }`}
            >
              <Music className="w-3.5 h-3.5" />
              <span>Audio (MP3 / Direct)</span>
            </button>
          </div>

          {/* Quality Options Grid */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-[#A5ABB5] uppercase tracking-wider">
              {mediaType === "video" ? "Available Resolutions" : "Audio Bitrate & Quality"}
            </label>

            {mediaType === "video" ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {mediaInfo.video_formats && mediaInfo.video_formats.length > 0 ? (
                  mediaInfo.video_formats.map((fmt) => {
                    const isSelected = selectedFormatId === fmt.format_id;
                    const sizeMb = fmt.filesize ? `${Math.round(fmt.filesize / 1024 / 1024)} MB` : null;
                    const needsFFmpeg = fmt.requires_ffmpeg && !ffmpegAvailable;

                    return (
                      <button
                        key={fmt.format_id}
                        type="button"
                        onClick={() => setSelectedFormatId(fmt.format_id)}
                        className={`flex flex-col items-start p-2.5 rounded-xl border text-left cursor-pointer transition-all ${
                          isSelected
                            ? "bg-[#272B32] border-[#8BC5B0] text-[#F3F4F6] shadow-sm"
                            : "bg-[#1A1C22] border-[#2D323B] text-[#A5ABB5] hover:border-[#383D46]"
                        }`}
                      >
                        <div className="flex items-center justify-between w-full">
                          <span className="text-xs font-semibold">{fmt.label}</span>
                          {needsFFmpeg && (
                            <span className="text-[9px] px-1 py-0.2 rounded bg-[#2D281E] text-[#E8BE72] font-mono">
                              FFmpeg Req.
                            </span>
                          )}
                        </div>
                        {sizeMb && <span className="text-[10px] text-[#6B7280] font-mono mt-0.5">~{sizeMb}</span>}
                      </button>
                    );
                  })
                ) : (
                  <div className="col-span-full text-xs text-[#A5ABB5] p-2 bg-[#1A1C22] rounded-lg">
                    Direct video streams not found; best available will be merged.
                  </div>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                {mediaInfo.audio_formats?.map((fmt) => {
                  const isSelected = selectedAudioBitrate === fmt.bitrate;
                  const needsFFmpeg = fmt.requires_ffmpeg && !ffmpegAvailable;

                  return (
                    <button
                      key={fmt.bitrate + fmt.label}
                      type="button"
                      onClick={() => setSelectedAudioBitrate(fmt.bitrate)}
                      className={`flex flex-col items-start p-2.5 rounded-xl border text-left cursor-pointer transition-all ${
                        isSelected
                          ? "bg-[#272B32] border-[#8BC5B0] text-[#F3F4F6] shadow-sm"
                          : "bg-[#1A1C22] border-[#2D323B] text-[#A5ABB5] hover:border-[#383D46]"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className="text-xs font-semibold truncate">{fmt.label}</span>
                        {needsFFmpeg && (
                          <span className="text-[9px] px-1 py-0.2 rounded bg-[#2D281E] text-[#E8BE72] font-mono shrink-0 ml-1">
                            FFmpeg Req.
                          </span>
                        )}
                      </div>
                      <span className="text-[10px] text-[#6B7280] font-mono mt-0.5">
                        {fmt.bitrate === "original" ? "Direct Stream" : fmt.bitrate}
                      </span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Missing FFmpeg Warning Banner */}
          {isBlockedByMissingFfmpeg && (
            <div className="p-3 rounded-lg bg-[#2D281E] border border-[#E8BE72]/40 text-[#E8BE72] text-xs flex items-start gap-2">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold m-0">FFmpeg Required for this format</p>
                <p className="m-0 mt-0.5 text-[11px] text-[#F3F4F6]/80">
                  {isVideo
                    ? "This resolution requires merging separate video and audio streams. Configure FFmpeg in Settings to unlock it, or choose a (Direct) format above."
                    : "Audio extraction and conversion to MP3 requires FFmpeg. Configure FFmpeg in Settings, or select an (Original / Direct) audio format if available."}
                </p>
              </div>
            </div>
          )}

          {/* Action Trigger */}
          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={handleDownload}
              disabled={isBlockedByMissingFfmpeg}
              className="neu-accent px-5 py-2.5 flex items-center gap-2 text-xs font-semibold cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <Download className="w-4 h-4" />
              <span>{isBlockedByMissingFfmpeg ? "FFmpeg Required" : "Start Download"}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
