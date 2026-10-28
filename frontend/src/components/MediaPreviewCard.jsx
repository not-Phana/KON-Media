import React, { useState, useEffect } from "react";
import {
  Video,
  Music,
  Download,
  Clock,
  User,
  AlertTriangle,
  X,
  ExternalLink,
  Info,
  Sparkles,
  CheckCircle2,
  Sliders,
  ChevronDown,
  FileVideo,
  FileAudio,
  ShieldAlert,
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
  const [isAdditionalOpen, setIsAdditionalOpen] = useState(false);

  // Active media info is the matched source if available, otherwise original mediaInfo
  const activeInfo = localMatch || mediaInfo;

  // Selected streams for stream pairing
  const [selectedVideoStreamId, setSelectedVideoStreamId] = useState("");
  const [selectedAudioStreamId, setSelectedAudioStreamId] = useState("");

  // Reset local match if mediaInfo prop changes to a new URL
  useEffect(() => {
    setLocalMatch(null);
    setMatchError(null);
  }, [mediaInfo?.webpage_url]);

  // Check if current view is an un-matched Spotify source
  const isSpotifyUnmatched =
    !activeInfo?.is_alternative_match &&
    (activeInfo?.source === "spotify" ||
      activeInfo?.is_unsupported_source ||
      activeInfo?.supported === false);

  // Selected formats for quick options
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

  // Update selection if activeInfo changes
  useEffect(() => {
    if (defaultVideoFormat?.format_id) {
      setSelectedFormatId(defaultVideoFormat.format_id);
    }
    if (defaultAudioFormat?.bitrate) {
      setSelectedAudioBitrate(defaultAudioFormat.bitrate);
    }
    if (activeInfo?.video_streams?.length > 0) {
      setSelectedVideoStreamId(String(activeInfo.video_streams[0].format_id));
    }
    if (activeInfo?.audio_streams?.length > 0) {
      setSelectedAudioStreamId(String(activeInfo.audio_streams[0].format_id));
    }
  }, [activeInfo?.webpage_url, activeInfo?.is_alternative_match]);

  if (!activeInfo) return null;

  // Handle Finding Audio Match for Spotify
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

  // Render Spotify Source / Unsupported DRM View
  if (isSpotifyUnmatched) {
    const handleOpenSpotify = async (e) => {
      e.preventDefault();
      setIsOpeningSpotify(true);
      try {
        await openExternalUrl(activeInfo.open_in_spotify_url || activeInfo.webpage_url);
      } catch (err) {
        window.open(activeInfo.open_in_spotify_url || activeInfo.webpage_url, "_blank");
      } finally {
        setIsOpeningSpotify(false);
      }
    };

    return (
      <div className="neu-card p-6 space-y-5 border border-[#383D46]">
        {/* Title & Dismiss */}
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-2">
              <span className="px-2.5 py-0.5 rounded text-[11px] font-mono bg-[#1E2922] text-[#1DB954] border border-[#1DB954]/30 font-semibold">
                Spotify {activeInfo.content_type?.toUpperCase() || "SOURCE"}
              </span>
              <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[#2C1D20] text-[#EF8585] border border-[#EF8585]/30">
                DRM Protected
              </span>
            </div>
            <h2 className="text-lg font-semibold text-[#F3F4F6] truncate m-0" title={activeInfo.title}>
              {activeInfo.title}
            </h2>
            <p className="flex items-center gap-1.5 text-xs text-[#A5ABB5] mt-1 m-0">
              <User className="w-3.5 h-3.5" />
              <span>{activeInfo.uploader}</span>
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

        {/* Info & DRM Disclosure Box */}
        <div className="p-4 rounded-xl bg-[#131418] border border-[#2D323B] space-y-3">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-lg bg-[#272B32] border border-[#383D46] flex items-center justify-center text-[#8BC5B0] shrink-0 mt-0.5">
              <ShieldAlert className="w-4 h-4 text-[#E8BE72]" />
            </div>
            <div className="flex-1 space-y-1">
              <h3 className="text-xs font-semibold text-[#F3F4F6] m-0">
                DRM-Protected Stream
              </h3>
              <p className="text-xs text-[#A5ABB5] m-0 leading-relaxed">
                {activeInfo.message}
              </p>
              <p className="text-xs text-[#6B7280] m-0 mt-1 leading-relaxed">
                {activeInfo.guidance}
              </p>
            </div>
          </div>

          <div className="pt-2 border-t border-[#252932] flex items-center gap-2 text-[11px] text-[#6B7280]">
            <Info className="w-3.5 h-3.5 shrink-0" />
            <span>
              Zero DRM circumvention. Matcher queries open public sources with full transparency.
            </span>
          </div>
        </div>

        {/* Error notification if matching failed */}
        {matchError && (
          <div className="p-3 rounded-lg bg-[#2D1B1E] border border-[#EF4444]/40 text-[#EF4444] text-xs flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 shrink-0" />
            <span>{matchError}</span>
          </div>
        )}

        {/* Action Controls */}
        <div className="flex flex-wrap items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onDismiss}
            className="neu-button px-4 py-2 text-xs font-medium cursor-pointer"
          >
            Dismiss
          </button>

          <a
            href={activeInfo.open_in_spotify_url || activeInfo.webpage_url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={handleOpenSpotify}
            className="neu-button px-4 py-2 flex items-center gap-2 text-xs font-semibold cursor-pointer no-underline text-[#1DB954] hover:text-[#1ed760]"
          >
            <ExternalLink className="w-4 h-4" />
            <span>{isOpeningSpotify ? "Opening..." : "Open in Spotify"}</span>
          </a>

          {activeInfo.can_match_audio && (
            <button
              type="button"
              onClick={handleMatchAudio}
              disabled={isMatching}
              className="neu-accent px-5 py-2.5 flex items-center gap-2 text-xs font-semibold cursor-pointer disabled:opacity-50"
            >
              {isMatching ? (
                <>
                  <div className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Searching Public Sources...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Find & Download Audio Match</span>
                </>
              )}
            </button>
          )}
        </div>
      </div>
    );
  }

  // Standard or Alternative-Matched Media Preview
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

  // Active streams for pairing
  const activeVideoStream =
    activeInfo?.video_streams?.find(
      (v) => String(v.format_id) === String(selectedVideoStreamId)
    ) || activeInfo?.video_streams?.[0];

  const activeAudioStream =
    activeInfo?.audio_streams?.find(
      (a) => String(a.format_id) === String(selectedAudioStreamId)
    ) || activeInfo?.audio_streams?.[0];

  // Calculate stream pairing status dynamically
  let pairingStatus = {
    valid: false,
    is_direct: false,
    requires_ffmpeg: false,
    recommended_container: "mp4",
    reason: "Select a video stream to evaluate pairing.",
  };

  if (activeVideoStream) {
    if (activeVideoStream.has_audio) {
      pairingStatus = {
        valid: true,
        is_direct: true,
        requires_ffmpeg: false,
        recommended_container: activeVideoStream.ext || "mp4",
        reason: `Video stream (f${activeVideoStream.format_id}) already contains integrated audio (${activeVideoStream.acodec || "audio"}). It can be downloaded directly as a complete playable file without needing extra merging.`,
      };
    } else if (!activeAudioStream) {
      pairingStatus = {
        valid: false,
        is_direct: false,
        requires_ffmpeg: true,
        recommended_container: "mp4",
        reason: `Video stream (f${activeVideoStream.format_id}) is video-only (has no sound). Select a compatible audio stream to pair with it.`,
      };
    } else {
      const vExt = (activeVideoStream.ext || "").toLowerCase();
      const vCodec = (activeVideoStream.vcodec || "").toLowerCase();
      const aExt = (activeAudioStream.ext || "").toLowerCase();
      const aCodec = (activeAudioStream.acodec || "").toLowerCase();

      let recContainer = "mp4";
      let method = "lossless stream copy";
      if (vExt === "webm" && ["webm", "opus", "ogg"].includes(aExt)) {
        recContainer = "webm";
      } else if (
        (vExt === "mp4" || vCodec.includes("avc") || vCodec.includes("h264")) &&
        (["m4a", "aac"].includes(aExt) || aCodec.includes("aac") || aCodec.includes("mp4a"))
      ) {
        recContainer = "mp4";
      } else {
        recContainer = "mkv";
        method = "lossless multi-codec container";
      }

      pairingStatus = {
        valid: true,
        is_direct: false,
        requires_ffmpeg: true,
        recommended_container: recContainer,
        reason: `Compatible stream pairing: Video f${activeVideoStream.format_id} (${vExt.toUpperCase()}) + Audio f${activeAudioStream.format_id} (${aExt.toUpperCase()}) will be downloaded and merged automatically into a single playable ${recContainer.toUpperCase()} file via ${method}.`,
      };
    }
  }

  // Quick download trigger
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

  // Merged stream download trigger
  const handleDownloadMerged = () => {
    if (!pairingStatus.valid || (pairingStatus.requires_ffmpeg && !ffmpegAvailable)) return;

    if (pairingStatus.is_direct) {
      onStartDownload({
        url: activeInfo.webpage_url,
        title: activeInfo.original_spotify_title || activeInfo.title,
        format_id: String(activeVideoStream.format_id),
        media_type: "video",
        ext: activeVideoStream.ext || "mp4",
        thumbnail: activeInfo.thumbnail,
        duration: activeInfo.duration,
      });
    } else {
      onStartDownload({
        url: activeInfo.webpage_url,
        title: activeInfo.original_spotify_title || activeInfo.title,
        format_id: `${activeVideoStream.format_id}+${activeAudioStream.format_id}`,
        media_type: "video",
        merge_streams: true,
        video_format_id: String(activeVideoStream.format_id),
        audio_format_id: String(activeAudioStream.format_id),
        merge_output_format: pairingStatus.recommended_container,
        ext: pairingStatus.recommended_container,
        thumbnail: activeInfo.thumbnail,
        duration: activeInfo.duration,
      });
    }
  };

  // Standalone video-only download trigger
  const handleDownloadVideoOnly = () => {
    if (!activeVideoStream) return;
    onStartDownload({
      url: activeInfo.webpage_url,
      title: activeInfo.original_spotify_title || activeInfo.title,
      format_id: String(activeVideoStream.format_id),
      media_type: "video",
      ext: activeVideoStream.ext || "mp4",
      thumbnail: activeInfo.thumbnail,
      duration: activeInfo.duration,
    });
  };

  // Standalone audio-only download trigger
  const handleDownloadAudioOnly = () => {
    if (!activeAudioStream) return;
    onStartDownload({
      url: activeInfo.webpage_url,
      title: activeInfo.original_spotify_title || activeInfo.title,
      format_id: String(activeAudioStream.format_id),
      media_type: "audio",
      ext: activeAudioStream.ext || "m4a",
      audio_bitrate: "original",
      thumbnail: activeInfo.thumbnail,
      duration: activeInfo.duration,
    });
  };

  return (
    <div className="neu-card p-5 space-y-4">
      {/* Alternative Match Header Banner if matched */}
      {activeInfo.is_alternative_match && (
        <div className="p-3 rounded-xl bg-[#1A2521] border border-[#8BC5B0]/30 flex items-center justify-between gap-3 text-xs text-[#8BC5B0]">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-[#72C69A] shrink-0" />
            <div>
              <span className="font-semibold text-[#F3F4F6]">
                Alternative Match Found
              </span>
              <span className="text-[#A5ABB5] ml-1.5">
                (Matched for Spotify track: <strong className="text-[#8BC5B0]">{activeInfo.original_spotify_title}</strong>)
              </span>
            </div>
          </div>
          <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#202E28] text-[#8BC5B0] border border-[#8BC5B0]/20">
            Public YouTube Source
          </span>
        </div>
      )}

      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1.5">
            <span className="px-2 py-0.5 rounded text-[11px] font-mono bg-[#272B32] text-[#8BC5B0] border border-[#383D46]">
              {activeInfo.extractor || "Media"}
            </span>
            {activeInfo.duration_formatted && (
              <span className="flex items-center gap-1 text-[11px] text-[#A5ABB5] font-mono">
                <Clock className="w-3 h-3" />
                {activeInfo.duration_formatted}
              </span>
            )}
          </div>
          <h2 className="text-base font-semibold text-[#F3F4F6] truncate m-0" title={activeInfo.title}>
            {activeInfo.title}
          </h2>
          <p className="flex items-center gap-1 text-xs text-[#A5ABB5] mt-1 m-0">
            <User className="w-3.5 h-3.5" />
            <span>{activeInfo.uploader}</span>
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
        {activeInfo.thumbnail && (
          <div className="relative w-full md:w-56 h-36 rounded-xl overflow-hidden bg-[#131418] border border-[#2D323B] shrink-0">
            <img
              src={activeInfo.thumbnail}
              alt={activeInfo.title}
              className="w-full h-full object-cover"
              crossOrigin="anonymous"
              referrerPolicy="no-referrer"
            />
            {activeInfo.duration_formatted && (
              <div className="absolute bottom-2 right-2 px-1.5 py-0.5 rounded bg-black/80 text-[10px] font-mono text-white">
                {activeInfo.duration_formatted}
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
              <span>Video (Complete / Merged)</span>
            </button>
            <button
              type="button"
              onClick={() => setMediaType("audio")}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium cursor-pointer transition-colors ${
                mediaType === "audio" ? "neu-pill-active" : "neu-pill-inactive"
              }`}
            >
              <Music className="w-3.5 h-3.5" />
              <span>Audio (MP3 / Direct Streams)</span>
            </button>
          </div>

          {/* Quick Quality Options Grid */}
          <div className="space-y-1.5">
            <label className="text-[11px] font-medium text-[#A5ABB5] uppercase tracking-wider">
              {mediaType === "video" ? "Available Resolutions" : "Audio Bitrate & Quality"}
            </label>

            {mediaType === "video" ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
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
                {activeInfo.audio_formats?.map((fmt) => {
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

          {/* Quick Action Trigger */}
          <div className="pt-1 flex justify-end">
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

          {/* Additional Download Options — Smart Stream Pairing & Merging */}
          {activeInfo.video_streams && activeInfo.video_streams.length > 0 && (
            <div className="pt-3 border-t border-[#252932] space-y-3">
              <button
                type="button"
                onClick={() => setIsAdditionalOpen(!isAdditionalOpen)}
                className="w-full flex items-center justify-between p-3 rounded-xl neu-recessed text-xs font-semibold text-[#A5ABB5] hover:text-[#F3F4F6] cursor-pointer transition-colors"
              >
                <div className="flex items-center gap-2">
                  <Sliders className="w-4 h-4 text-[#8BC5B0]" />
                  <span>Additional Download Options — Smart Stream Pairing & Automatic Merging</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[10px] px-2 py-0.5 rounded bg-[#272B32] text-[#8BC5B0] font-mono border border-[#383D46]">
                    {isAdditionalOpen ? "Hide Options" : "Show Options"}
                  </span>
                  <ChevronDown
                    className={`w-4 h-4 text-[#8BC5B0] transition-transform duration-200 ${
                      isAdditionalOpen ? "rotate-180" : ""
                    }`}
                  />
                </div>
              </button>

              {isAdditionalOpen && (
                <div className="p-4 rounded-xl bg-[#14161B] border border-[#2D323B] space-y-4">
                  <div className="text-xs text-[#A5ABB5] leading-relaxed">
                    Select a separate video stream and audio stream below. KON Media will validate compatibility, download both streams automatically, and merge them into a single playable file with sound.
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* Video Stream Selector */}
                    <div className="space-y-1.5">
                      <label className="flex items-center justify-between text-[11px] font-semibold text-[#8BC5B0] uppercase tracking-wider">
                        <span className="flex items-center gap-1.5">
                          <FileVideo className="w-3.5 h-3.5" />
                          Video Stream
                        </span>
                        <span className="text-[10px] text-[#6B7280] font-mono lowercase">
                          {activeInfo.video_streams.length} available
                        </span>
                      </label>
                      <select
                        value={selectedVideoStreamId}
                        onChange={(e) => setSelectedVideoStreamId(e.target.value)}
                        className="w-full p-2.5 rounded-xl bg-[#1D2026] border border-[#383D46] text-xs text-[#F3F4F6] font-mono focus:border-[#8BC5B0] outline-none cursor-pointer"
                      >
                        {activeInfo.video_streams.map((v) => (
                          <option key={v.format_id} value={v.format_id}>
                            {v.label} (ID: {v.format_id})
                          </option>
                        ))}
                      </select>
                    </div>

                    {/* Audio Stream Selector */}
                    <div className="space-y-1.5">
                      <label className="flex items-center justify-between text-[11px] font-semibold text-[#8BC5B0] uppercase tracking-wider">
                        <span className="flex items-center gap-1.5">
                          <FileAudio className="w-3.5 h-3.5" />
                          Audio Stream
                        </span>
                        <span className="text-[10px] text-[#6B7280] font-mono lowercase">
                          {activeInfo.audio_streams?.length || 0} available
                        </span>
                      </label>
                      <select
                        value={selectedAudioStreamId}
                        onChange={(e) => setSelectedAudioStreamId(e.target.value)}
                        className="w-full p-2.5 rounded-xl bg-[#1D2026] border border-[#383D46] text-xs text-[#F3F4F6] font-mono focus:border-[#8BC5B0] outline-none cursor-pointer disabled:opacity-50"
                        disabled={activeInfo.audio_streams?.length === 0}
                      >
                        {activeInfo.audio_streams && activeInfo.audio_streams.length > 0 ? (
                          activeInfo.audio_streams.map((a) => (
                            <option key={a.format_id} value={a.format_id}>
                              {a.label} (ID: {a.format_id})
                            </option>
                          ))
                        ) : (
                          <option value="">No standalone audio streams</option>
                        )}
                      </select>
                    </div>
                  </div>

                  {/* Dynamic Compatibility Inspection Banner */}
                  <div className="p-3 rounded-xl bg-[#1A1D24] border border-[#383D46] text-xs space-y-1.5 font-mono">
                    <div className="flex items-center justify-between">
                      <span className="text-[#A5ABB5] text-[11px] uppercase tracking-wider font-semibold">
                        Pairing Compatibility
                      </span>
                      <span
                        className={`px-2 py-0.5 rounded text-[10px] font-semibold ${
                          pairingStatus.valid
                            ? pairingStatus.is_direct
                              ? "bg-[#1E2922] text-[#8BC5B0] border border-[#8BC5B0]/30"
                              : "bg-[#1A2521] text-[#72C69A] border border-[#72C69A]/30"
                            : "bg-[#2D1B1E] text-[#EF8585] border border-[#EF8585]/30"
                        }`}
                      >
                        {pairingStatus.valid
                          ? pairingStatus.is_direct
                            ? "Direct Stream"
                            : `Merge -> ${pairingStatus.recommended_container.toUpperCase()}`
                          : "Needs Audio Stream"}
                      </span>
                    </div>
                    <p className="text-[11px] text-[#F3F4F6]/90 m-0 leading-relaxed font-sans">
                      {pairingStatus.reason}
                    </p>
                  </div>

                  {/* Missing FFmpeg Warning for Merging */}
                  {pairingStatus.requires_ffmpeg && !ffmpegAvailable && (
                    <div className="p-3 rounded-lg bg-[#2D281E] border border-[#E8BE72]/40 text-[#E8BE72] text-xs flex items-start gap-2">
                      <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5" />
                      <div className="flex-1">
                        <p className="font-semibold m-0">FFmpeg Required for Merging</p>
                        <p className="m-0 mt-0.5 text-[11px] text-[#F3F4F6]/80">
                          Combining separate video and audio streams requires FFmpeg. You can configure FFmpeg in Settings, or use the standalone download buttons below to download individual streams.
                        </p>
                      </div>
                    </div>
                  )}

                  {/* Action Bar for Stream Pairing */}
                  <div className="flex flex-wrap items-center justify-between gap-2 pt-2 border-t border-[#252932]">
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={handleDownloadVideoOnly}
                        disabled={!activeVideoStream}
                        className="neu-button px-3 py-1.5 flex items-center gap-1.5 text-xs text-[#A5ABB5] hover:text-[#F3F4F6] cursor-pointer disabled:opacity-50"
                        title="Download video stream standalone"
                      >
                        <FileVideo className="w-3.5 h-3.5 text-[#8BC5B0]" />
                        <span>Download Video Only</span>
                      </button>
                      <button
                        type="button"
                        onClick={handleDownloadAudioOnly}
                        disabled={!activeAudioStream}
                        className="neu-button px-3 py-1.5 flex items-center gap-1.5 text-xs text-[#A5ABB5] hover:text-[#F3F4F6] cursor-pointer disabled:opacity-50"
                        title="Download audio stream standalone"
                      >
                        <FileAudio className="w-3.5 h-3.5 text-[#8BC5B0]" />
                        <span>Download Audio Only</span>
                      </button>
                    </div>

                    <button
                      type="button"
                      onClick={handleDownloadMerged}
                      disabled={!pairingStatus.valid || (pairingStatus.requires_ffmpeg && !ffmpegAvailable)}
                      className="neu-accent px-4 py-2 flex items-center gap-2 text-xs font-semibold cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <Download className="w-4 h-4" />
                      <span>Download Selected + Merge</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
