import React, { useState, useEffect } from "react";
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
  Search,
  Sparkles,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  Layers,
  Check,
  Film,
  Volume2,
} from "lucide-react";
import { openExternalUrl, matchSpotifyTrack } from "../api";

export default function MediaPreviewCard({
  mediaInfo,
  onStartDownload,
  onDismiss,
  onUpdateMediaInfo,
}) {
  const [localMatch, setLocalMatch] = useState(null);
  const [isMatching, setIsMatching] = useState(false);
  const [matchError, setMatchError] = useState(null);
  const [mediaType, setMediaType] = useState("video");
  const [isOpeningSpotify, setIsOpeningSpotify] = useState(false);

  const activeInfo = localMatch || mediaInfo;

  useEffect(() => {
    setLocalMatch(null);
    setMatchError(null);
  }, [mediaInfo?.webpage_url]);

  const isSpotifyUnmatched =
    !activeInfo?.is_alternative_match &&
    (activeInfo?.source === "spotify" ||
      activeInfo?.is_unsupported_source ||
      activeInfo?.supported === false);

  const defaultVideoFormat =
    activeInfo?.video_formats?.find((f) => !f.requires_ffmpeg) ||
    activeInfo?.video_formats?.[0];

  const defaultAudioFormat =
    activeInfo?.audio_formats?.find((f) => !f.requires_ffmpeg) ||
    activeInfo?.audio_formats?.[0];

  const [selectedFormatId, setSelectedFormatId] = useState(
    defaultVideoFormat?.format_id || "best"
  );
  const [selectedAudioBitrate, setSelectedAudioBitrate] = useState(
    defaultAudioFormat?.bitrate || "320k"
  );

  useEffect(() => {
    if (defaultVideoFormat?.format_id) {
      setSelectedFormatId(defaultVideoFormat.format_id);
    }
    if (defaultAudioFormat?.bitrate) {
      setSelectedAudioBitrate(defaultAudioFormat.bitrate);
    }
  }, [activeInfo?.webpage_url, activeInfo?.is_alternative_match]);

  if (!activeInfo) return null;

  const handleMatchAudio = async () => {
    setIsMatching(true);
    setMatchError(null);
    try {
      const match = await matchSpotifyTrack(
        activeInfo.webpage_url,
        activeInfo.match_search_query || activeInfo.title
      );
      setLocalMatch(match);
      if (onUpdateMediaInfo) {
        onUpdateMediaInfo(match);
      }
    } catch (err) {
      setMatchError(err.message || "Failed to find matching public source.");
    } finally {
      setIsMatching(false);
    }
  };

  if (isSpotifyUnmatched) {
    const handleOpenSpotify = async (e) => {
      e.preventDefault();
      setIsOpeningSpotify(true);
      try {
        const url = activeInfo.open_in_spotify_url || activeInfo.webpage_url;
        window.open(url, "_blank", "noopener,noreferrer");
        await openExternalUrl(url).catch(() => {});
      } finally {
        setTimeout(() => setIsOpeningSpotify(false), 1000);
      }
    };

    return (
      <div className="neu-card p-6 space-y-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="neu-recessed px-3 py-1 rounded-full text-xs font-semibold text-[#10B981] flex items-center gap-1.5">
                <Music className="w-3.5 h-3.5" />
                Spotify Source
              </span>
              <span className="neu-recessed px-2.5 py-1 rounded-full text-xs font-semibold text-[#F59E0B]">
                DRM Protected
              </span>
            </div>
            <h2 className="text-lg font-bold text-[#1E293B] truncate m-0">
              {activeInfo.title || "Spotify Music"}
            </h2>
            <p className="text-xs text-[#64748B] mt-1 m-0 truncate">
              {activeInfo.webpage_url}
            </p>
          </div>

          <button
            onClick={onDismiss}
            className="neu-raised p-2 text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl"
            title="Dismiss preview"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Media Presentation: Artwork + Details */}
        <div className="flex flex-col sm:flex-row gap-4 items-center sm:items-start p-4 rounded-2xl neu-recessed">
          {activeInfo.thumbnail ? (
            <img
              src={activeInfo.thumbnail}
              alt={activeInfo.title}
              className="w-24 h-24 rounded-xl object-cover shrink-0"
              crossOrigin="anonymous"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-24 h-24 rounded-xl neu-recessed flex items-center justify-center text-[#10B981] shrink-0">
              <Music className="w-8 h-8 opacity-60" />
            </div>
          )}
          <div className="flex-1 text-center sm:text-left space-y-1">
            <h3 className="text-sm font-bold text-[#1E293B] m-0">
              {activeInfo.title}
            </h3>
            <p className="text-xs text-[#64748B] m-0">
              Source: <span className="text-[#1E293B] font-semibold">{activeInfo.uploader || "Spotify"}</span>
            </p>
            <p className="text-[11px] text-[#94A3B8] m-0 pt-1">
              Metadata verified via official Spotify oEmbed API
            </p>
          </div>
        </div>

        {/* Guidance Box */}
        <div className="p-4 rounded-2xl neu-raised space-y-3">
          <div className="flex items-start gap-3">
            <ShieldAlert className="w-5 h-5 text-[#F59E0B] shrink-0 mt-0.5" />
            <div className="space-y-1 text-xs">
              <p className="font-bold text-[#1E293B] m-0">
                Direct Stream Protected by Copyright DRM
              </p>
              <p className="text-[#64748B] leading-relaxed m-0">
                Spotify streams are encrypted with Digital Rights Management and cannot be exported directly.
                KON Media provides an authorized public source matcher to locate matching legal media (e.g. YouTube),
                or you can listen directly in Spotify.
              </p>
            </div>
          </div>

          <div className="pt-2 border-t border-slate-200/60 flex items-center gap-2 text-[11px] text-[#64748B]">
            <Info className="w-3.5 h-3.5 shrink-0 text-[#0084FF]" />
            <span>
              Zero DRM circumvention. Matcher queries open public sources with full transparency.
            </span>
          </div>
        </div>

        {/* Error notification if matching failed */}
        {matchError && (
          <div className="p-3.5 rounded-xl bg-[#FEE2E2]/60 border border-[#FCA5A5] text-[#DC2626] text-xs flex items-center gap-2 font-medium">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{matchError}</span>
          </div>
        )}

        {/* Action Controls */}
        <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onDismiss}
            className="neu-raised px-4 py-2 text-xs font-semibold text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl"
          >
            Dismiss
          </button>

          <a
            href={activeInfo.open_in_spotify_url || activeInfo.webpage_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={handleOpenSpotify}
            className="neu-raised px-4 py-2 flex items-center gap-2 text-xs font-semibold cursor-pointer no-underline text-[#10B981] hover:text-[#059669] rounded-xl"
          >
            <ExternalLink className="w-4 h-4" />
            <span>{isOpeningSpotify ? "Opening..." : "Open in Spotify"}</span>
          </a>

          {activeInfo.can_match_audio && (
            <button
              type="button"
              onClick={handleMatchAudio}
              disabled={isMatching}
              className="neu-accent px-5 py-2.5 flex items-center gap-2 text-xs font-semibold cursor-pointer disabled:opacity-50 rounded-xl"
            >
              {isMatching ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Searching Public Sources...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Find &amp; Download Audio Match</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    );
  }

  // Standard Media Preview
  const isVideo = mediaType === "video";
  const selectedFormat = isVideo
    ? activeInfo.video_formats?.find((f) => f.format_id === selectedFormatId)
    : null;

  const selectedAudioFormat = !isVideo
    ? activeInfo.audio_formats?.find((f) => f.bitrate === selectedAudioBitrate)
    : null;

  const ffmpegAvailable = Boolean(activeInfo.ffmpeg_available);
  const isBlockedByMissingFfmpeg =
    !ffmpegAvailable &&
    (isVideo ? selectedFormat?.requires_ffmpeg : selectedAudioFormat?.requires_ffmpeg);

  const [showAdditional, setShowAdditional] = useState(false);
  const availableVideoStreams = activeInfo.available_video_streams || [];
  const availableAudioStreams = activeInfo.available_audio_streams || [];
  const hasAdditionalStreams =
    availableVideoStreams.length > 0 || availableAudioStreams.length > 0;

  const [selectedCustomVideoId, setSelectedCustomVideoId] = useState(
    availableVideoStreams[0]?.format_id || ""
  );
  const [selectedCustomAudioId, setSelectedCustomAudioId] = useState(
    availableAudioStreams[0]?.format_id || ""
  );

  useEffect(() => {
    if (activeInfo?.available_video_streams?.length > 0) {
      setSelectedCustomVideoId(activeInfo.available_video_streams[0].format_id);
    }
    if (activeInfo?.available_audio_streams?.length > 0) {
      setSelectedCustomAudioId(activeInfo.available_audio_streams[0].format_id);
    }
  }, [activeInfo?.webpage_url, activeInfo?.is_alternative_match]);

  const selectedCustomVideo = availableVideoStreams.find(
    (s) => s.format_id === selectedCustomVideoId
  );
  const selectedCustomAudio = availableAudioStreams.find(
    (s) => s.format_id === selectedCustomAudioId
  );

  const getPairStatus = () => {
    if (!selectedCustomVideo && !selectedCustomAudio) {
      return { compatible: false, message: "Select a video and audio stream to pair." };
    }
    if (selectedCustomVideo && !selectedCustomAudio) {
      if (selectedCustomVideo.stream_kind === "combined") {
        return {
          compatible: true,
          canSolo: true,
          requiresMerge: false,
          targetContainer: (selectedCustomVideo.ext || "mp4").toLowerCase(),
          message: "Selected video stream includes audio and can be downloaded standalone.",
        };
      }
      return {
        compatible: false,
        message: "Selected video has no audio. Select an audio stream to pair and merge.",
      };
    }
    if (selectedCustomAudio && !selectedCustomVideo) {
      return {
        compatible: true,
        canSolo: true,
        requiresMerge: false,
        targetContainer: (selectedCustomAudio.ext || "m4a").toLowerCase(),
        message: "Audio stream selected for standalone direct audio download.",
      };
    }

    const vExt = (selectedCustomVideo.ext || "").toLowerCase();
    const aExt = (selectedCustomAudio.ext || "").toLowerCase();
    const vc = (selectedCustomVideo.vcodec || "").toLowerCase();
    const ac = (selectedCustomAudio.acodec || "").toLowerCase();

    const isWebm = (vExt === "webm" || vc.includes("vp9") || vc.includes("vp8") || vc.includes("av01")) &&
      (aExt === "webm" || aExt === "opus" || ac.includes("opus") || ac.includes("vorbis"));

    const isMp4 = (vExt === "mp4" || vc.includes("avc") || vc.includes("h264") || vc.includes("h265") || vc.includes("hevc")) &&
      (aExt === "m4a" || aExt === "mp4" || ac.includes("aac") || ac.includes("mp4a"));

    const targetExt = isWebm ? "webm" : "mp4";
    return {
      compatible: true,
      canSolo: false,
      requiresMerge: true,
      targetContainer: targetExt,
      message: `Streams validated. Will merge into high-quality ${targetExt.toUpperCase()} with FFmpeg.`,
    };
  };

  const pairStatus = getPairStatus();

  const handleDownloadSelectedMerge = () => {
    if (!pairStatus.compatible || !ffmpegAvailable) return;
    onStartDownload({
      url: activeInfo.webpage_url,
      title: activeInfo.original_spotify_title || activeInfo.title,
      format_id: `${selectedCustomVideo.format_id}+${selectedCustomAudio.format_id}`,
      media_type: "video",
      video_format_id: selectedCustomVideo.format_id,
      audio_format_id: selectedCustomAudio.format_id,
      ext: pairStatus.targetContainer || "mp4",
      merge_output_format: pairStatus.targetContainer || "mp4",
      is_merge_operation: true,
      thumbnail: activeInfo.thumbnail,
      duration: activeInfo.duration,
    });
  };

  const handleDownloadVideoSolo = (stream) => {
    const s = stream || selectedCustomVideo;
    if (!s) return;
    onStartDownload({
      url: activeInfo.webpage_url,
      title: activeInfo.original_spotify_title || activeInfo.title,
      format_id: s.format_id,
      media_type: "video",
      ext: s.ext || "mp4",
      thumbnail: activeInfo.thumbnail,
      duration: activeInfo.duration,
    });
  };

  const handleDownloadAudioSolo = (stream) => {
    const s = stream || selectedCustomAudio;
    if (!s) return;
    onStartDownload({
      url: activeInfo.webpage_url,
      title: activeInfo.original_spotify_title || activeInfo.title,
      format_id: s.format_id,
      media_type: "audio",
      ext: s.ext || "m4a",
      audio_bitrate: "original",
      thumbnail: activeInfo.thumbnail,
      duration: activeInfo.duration,
    });
  };

  const handleDownload = () => {
    if (isBlockedByMissingFfmpeg) return;

    onStartDownload({
      url: activeInfo.webpage_url,
      title: activeInfo.original_spotify_title || activeInfo.title,
      format_id: isVideo
        ? selectedFormatId
        : selectedAudioFormat?.format_id || "bestaudio/best",
      media_type: mediaType,
      ext: isVideo ? "mp4" : selectedAudioFormat?.ext || "mp3",
      audio_bitrate: selectedAudioBitrate,
      thumbnail: activeInfo.thumbnail,
      duration: activeInfo.duration,
    });
  };

  return (
    <div className="neu-card p-6 space-y-5">
      {/* Alternative Match Header Banner if matched */}
      {activeInfo.is_alternative_match && (
        <div className="p-3.5 rounded-2xl neu-raised flex items-center justify-between gap-3 text-xs text-[#0084FF]">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-[#10B981] shrink-0" />
            <div>
              <span className="font-bold text-[#1E293B]">
                Alternative Match Found
              </span>
              <span className="text-[#64748B] ml-1.5 font-medium">
                (Matched for Spotify track: <strong className="text-[#0084FF]">{activeInfo.original_spotify_title}</strong>)
              </span>
            </div>
          </div>
          <span className="neu-recessed px-3 py-1 rounded-full text-xs font-semibold text-[#0084FF]">
            Public YouTube Source
          </span>
        </div>
      )}

      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="neu-recessed px-3 py-0.5 rounded-full text-xs font-semibold text-[#0084FF]">
              {activeInfo.extractor || "Media"}
            </span>
            {activeInfo.duration_formatted && (
              <span className="flex items-center gap-1 text-xs text-[#64748B] font-medium">
                <Clock className="w-3.5 h-3.5" />
                {activeInfo.duration_formatted}
              </span>
            )}
          </div>
          <h2 className="text-lg font-bold text-[#1E293B] truncate m-0" title={activeInfo.title}>
            {activeInfo.title}
          </h2>
          <p className="flex items-center gap-1.5 text-xs text-[#64748B] mt-1 m-0 font-medium">
            <User className="w-3.5 h-3.5 text-[#94A3B8]" />
            <span>{activeInfo.uploader}</span>
          </p>
        </div>

        <button
          onClick={onDismiss}
          className="neu-raised p-2 text-[#64748B] hover:text-[#1E293B] cursor-pointer rounded-xl"
          title="Dismiss preview"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <div className="flex flex-col md:flex-row gap-5">
        {/* Thumbnail Container */}
        {activeInfo.thumbnail && (
          <div className="relative w-full md:w-56 h-36 rounded-2xl overflow-hidden neu-recessed p-1 shrink-0">
            <img
              src={activeInfo.thumbnail}
              alt={activeInfo.title}
              className="w-full h-full object-cover rounded-xl"
              crossOrigin="anonymous"
              referrerPolicy="no-referrer"
            />
            {activeInfo.duration_formatted && (
              <div className="absolute bottom-2.5 right-2.5 px-2 py-0.5 rounded-md bg-black/75 text-[10px] font-mono text-white">
                {activeInfo.duration_formatted}
              </div>
            )}
          </div>
        )}

        {/* Format Selector Column */}
        <div className="flex-1 space-y-4">
          {/* Media Type Toggle: Video vs Audio */}
          <div className="neu-recessed p-1.5 flex items-center gap-1.5 rounded-2xl w-fit">
            <button
              type="button"
              onClick={() => setMediaType("video")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-colors ${
                mediaType === "video" ? "neu-raised text-[#0084FF]" : "text-[#64748B] hover:text-[#1E293B]"
              }`}
            >
              <Video className="w-3.5 h-3.5" />
              <span>Video (MP4)</span>
            </button>
            <button
              type="button"
              onClick={() => setMediaType("audio")}
              className={`flex items-center gap-2 px-4 py-2 rounded-xl text-xs font-semibold cursor-pointer transition-colors ${
                mediaType === "audio" ? "neu-raised text-[#0084FF]" : "text-[#64748B] hover:text-[#1E293B]"
              }`}
            >
              <Music className="w-3.5 h-3.5" />
              <span>Audio (MP3)</span>
            </button>
          </div>

          {/* Quality Options Grid */}
          <div className="space-y-2">
            <label className="text-xs font-semibold text-[#64748B] uppercase tracking-wider">
              {mediaType === "video" ? "Available Resolutions" : "Audio Bitrate & Quality"}
            </label>

            {mediaType === "video" ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {activeInfo.video_formats && activeInfo.video_formats.length > 0 ? (
                  activeInfo.video_formats.map((fmt) => {
                    const isSelected = selectedFormatId === fmt.format_id;
                    const sizeMb = fmt.filesize ? `${Math.round(fmt.filesize / 1024 / 1024)} MB` : null;
                    const needsFFmpeg = fmt.requires_ffmpeg && !ffmpegAvailable;

                    return (
                      <button
                        key={fmt.format_id}
                        type="button"
                        onClick={() => setSelectedFormatId(fmt.format_id)}
                        className={`flex flex-col items-start p-3 rounded-2xl text-left cursor-pointer transition-all ${
                          isSelected
                            ? "neu-pressed text-[#0084FF] border border-[#0084FF]/30"
                            : "neu-raised text-[#334155] hover:text-[#0084FF]"
                        }`}
                      >
                        <div className="flex items-center justify-between w-full">
                          <span className="text-xs font-bold">{fmt.label}</span>
                          {needsFFmpeg && (
                            <span className="text-[9px] px-1.5 py-0.5 rounded neu-recessed text-[#F59E0B] font-mono">
                              FFmpeg
                            </span>
                          )}
                        </div>
                        {sizeMb && <span className="text-[11px] text-[#64748B] font-mono mt-1">~{sizeMb}</span>}
                      </button>
                    );
                  })
                ) : (
                  <div className="col-span-full text-xs text-[#64748B] p-3 neu-recessed rounded-xl font-medium">
                    Direct video streams not found; best available will be merged.
                  </div>
                )}
              </div>
            ) : (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
                {activeInfo.audio_formats?.map((fmt) => {
                  const isSelected = selectedAudioBitrate === fmt.bitrate;
                  const needsFFmpeg = fmt.requires_ffmpeg && !ffmpegAvailable;

                  return (
                    <button
                      key={fmt.bitrate + fmt.label}
                      type="button"
                      onClick={() => setSelectedAudioBitrate(fmt.bitrate)}
                      className={`flex flex-col items-start p-3 rounded-2xl text-left cursor-pointer transition-all ${
                        isSelected
                          ? "neu-pressed text-[#0084FF] border border-[#0084FF]/30"
                          : "neu-raised text-[#334155] hover:text-[#0084FF]"
                      }`}
                    >
                      <div className="flex items-center justify-between w-full">
                        <span className="text-xs font-bold truncate">{fmt.label}</span>
                        {needsFFmpeg && (
                          <span className="text-[9px] px-1.5 py-0.5 rounded neu-recessed text-[#F59E0B] font-mono shrink-0 ml-1">
                            FFmpeg
                          </span>
                        )}
                      </div>
                      <span className="text-[11px] text-[#64748B] font-mono mt-1">
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
            <div className="p-3.5 rounded-2xl bg-[#FEF3C7]/60 border border-[#FCD34D] text-[#D97706] text-xs flex items-start gap-2.5 font-medium">
              <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-[#D97706]" />
              <div className="flex-1">
                <p className="font-bold m-0">FFmpeg Required for this format</p>
                <p className="m-0 mt-0.5 text-[11px] text-[#92400E]">
                  {isVideo
                    ? "This resolution requires merging separate video and audio streams. Configure FFmpeg in Settings to unlock it, or choose a (Direct) format above."
                    : "Audio extraction and conversion to MP3 requires FFmpeg. Configure FFmpeg in Settings, or select an (Original / Direct) audio format if available."}
                </p>
              </div>
            </div>
          )}

          {/* Additional Download Options & Custom Stream Pairing */}
          {hasAdditionalStreams && (
            <div className="pt-3 border-t border-slate-200/60 space-y-3">
              <button
                type="button"
                onClick={() => setShowAdditional(!showAdditional)}
                className="w-full flex items-center justify-between p-3.5 rounded-2xl neu-raised text-left transition-colors cursor-pointer"
              >
                <div className="flex items-center gap-2.5">
                  <Layers className="w-4 h-4 text-[#0084FF]" />
                  <span className="text-xs font-bold text-[#1E293B]">
                    Additional Options &amp; Custom Stream Pairing
                  </span>
                  <span className="neu-recessed px-2.5 py-0.5 rounded-full text-xs font-semibold text-[#0084FF]">
                    {availableVideoStreams.length + availableAudioStreams.length} streams
                  </span>
                </div>
                {showAdditional ? (
                  <ChevronUp className="w-4 h-4 text-[#64748B]" />
                ) : (
                  <ChevronDown className="w-4 h-4 text-[#64748B]" />
                )}
              </button>

              {showAdditional && (
                <div className="p-5 rounded-2xl neu-recessed space-y-4">
                  <p className="text-xs text-[#64748B] m-0 leading-relaxed font-medium">
                    Select a video stream and an audio stream to automatically download and merge them into a single playable file with FFmpeg, or download any stream standalone.
                  </p>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Video Streams Column */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-[#0084FF] flex items-center gap-1.5 uppercase tracking-wider">
                          <Film className="w-3.5 h-3.5" />
                          1. Video Stream ({availableVideoStreams.length})
                        </span>
                        {selectedCustomVideo && (
                          <span className="neu-raised px-2 py-0.5 rounded-md text-[11px] text-[#64748B] font-mono">
                            {selectedCustomVideo.resolution} · {selectedCustomVideo.ext.toUpperCase()}
                          </span>
                        )}
                      </div>

                      <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                        {availableVideoStreams.map((vs) => {
                          const isSel = selectedCustomVideoId === vs.format_id;
                          return (
                            <div
                              key={vs.format_id}
                              onClick={() => setSelectedCustomVideoId(vs.format_id)}
                              className={`p-3 rounded-2xl text-xs cursor-pointer transition-colors flex items-center justify-between gap-2.5 ${
                                isSel
                                  ? "neu-pressed text-[#0084FF] border border-[#0084FF]/30"
                                  : "neu-raised text-[#334155] hover:text-[#0084FF]"
                              }`}
                            >
                              <div className="flex items-center gap-2.5 min-w-0">
                                <div
                                  className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${
                                    isSel
                                      ? "border-[#0084FF] bg-[#0084FF]"
                                      : "border-[#94A3B8]"
                                  }`}
                                >
                                  {isSel && <Check className="w-2.5 h-2.5 text-white" />}
                                </div>
                                <div className="min-w-0">
                                  <div className="font-bold truncate">
                                    {vs.resolution || `${vs.height}p`} ({vs.vcodec_clean || vs.ext.toUpperCase()})
                                  </div>
                                  <div className="text-[11px] text-[#64748B] font-mono">
                                    {vs.ext.toUpperCase()} · {vs.bitrate_kbps ? `${vs.bitrate_kbps} kbps` : ""}
                                    {vs.stream_kind === "combined" ? " · Audio+Video" : " · Video only"}
                                  </div>
                                </div>
                              </div>

                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDownloadVideoSolo(vs);
                                }}
                                className="neu-raised px-2.5 py-1 rounded-xl text-xs font-semibold text-[#0084FF] hover:text-[#0074E0] cursor-pointer shrink-0"
                                title="Download just this video stream standalone (no audio)"
                              >
                                Solo
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    </div>

                    {/* Audio Streams Column */}
                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-[#0084FF] flex items-center gap-1.5 uppercase tracking-wider">
                          <Volume2 className="w-3.5 h-3.5" />
                          2. Audio Stream ({availableAudioStreams.length})
                        </span>
                        {selectedCustomAudio && (
                          <span className="neu-raised px-2 py-0.5 rounded-md text-[11px] text-[#64748B] font-mono">
                            {selectedCustomAudio.acodec_clean || selectedCustomAudio.ext.toUpperCase()}
                          </span>
                        )}
                      </div>

                      <div className="space-y-2 max-h-56 overflow-y-auto pr-1">
                        {availableAudioStreams.map((as) => {
                          const isSel = selectedCustomAudioId === as.format_id;
                          return (
                            <div
                              key={as.format_id}
                              onClick={() => setSelectedCustomAudioId(as.format_id)}
                              className={`p-3 rounded-2xl text-xs cursor-pointer transition-colors flex items-center justify-between gap-2.5 ${
                                isSel
                                  ? "neu-pressed text-[#0084FF] border border-[#0084FF]/30"
                                  : "neu-raised text-[#334155] hover:text-[#0084FF]"
                              }`}
                            >
                              <div className="flex items-center gap-2.5 min-w-0">
                                <div
                                  className={`w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${
                                    isSel
                                      ? "border-[#0084FF] bg-[#0084FF]"
                                      : "border-[#94A3B8]"
                                  }`}
                                >
                                  {isSel && <Check className="w-2.5 h-2.5 text-white" />}
                                </div>
                                <div className="min-w-0">
                                  <div className="font-bold truncate">
                                    {as.acodec_clean || as.ext.toUpperCase()} ({as.bitrate_kbps ? `${as.bitrate_kbps} kbps` : as.ext.toUpperCase()})
                                  </div>
                                  <div className="text-[11px] text-[#64748B] font-mono">
                                    {as.ext.toUpperCase()} · Audio only
                                  </div>
                                </div>
                              </div>

                              <button
                                type="button"
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleDownloadAudioSolo(as);
                                }}
                                className="neu-raised px-2.5 py-1 rounded-xl text-xs font-semibold text-[#0084FF] hover:text-[#0074E0] cursor-pointer shrink-0"
                                title="Download just this audio stream standalone"
                              >
                                Solo
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  </div>

                  {/* Compatibility Card */}
                  <div
                    className={`p-3.5 rounded-2xl text-xs space-y-1.5 ${
                      pairStatus.compatible
                        ? "neu-raised text-[#1E293B] border border-[#0084FF]/25"
                        : "bg-[#FEF3C7]/60 border border-[#FCD34D] text-[#D97706]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2 font-bold">
                      <div className="flex items-center gap-2">
                        {pairStatus.compatible ? (
                          <CheckCircle2 className="w-4 h-4 text-[#10B981] shrink-0" />
                        ) : (
                          <AlertTriangle className="w-4 h-4 text-[#D97706] shrink-0" />
                        )}
                        <span>
                          {pairStatus.compatible
                            ? "Stream Pair Validated"
                            : "Pair Selection Incomplete"}
                        </span>
                      </div>
                      {pairStatus.compatible && (
                        <span className="neu-recessed px-2.5 py-0.5 rounded-full text-[#0084FF] font-mono uppercase text-xs">
                          Target: {pairStatus.targetContainer?.toUpperCase() || "MP4"}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-[#64748B] m-0 font-medium">
                      {pairStatus.message}
                    </p>
                  </div>

                  {/* Merged Action Trigger */}
                  <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
                    <span className="text-xs text-[#94A3B8] font-medium">
                      {!ffmpegAvailable && "FFmpeg is required to merge separate streams."}
                    </span>

                    <button
                      type="button"
                      onClick={handleDownloadSelectedMerge}
                      disabled={!pairStatus.compatible || !ffmpegAvailable}
                      className="neu-accent px-5 py-2.5 flex items-center gap-2 text-xs font-semibold cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed rounded-xl"
                    >
                      <Sparkles className="w-4 h-4" />
                      <span>Download Selected + Merge ({pairStatus.targetContainer?.toUpperCase() || "MP4"})</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Action Trigger */}
          <div className="pt-2 flex justify-end">
            <button
              type="button"
              onClick={handleDownload}
              disabled={isBlockedByMissingFfmpeg}
              className="neu-accent px-6 py-3 flex items-center gap-2 text-xs font-semibold cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed rounded-xl"
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
