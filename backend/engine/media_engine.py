"""Media Engine for KON Media.

Directly leverages the upstream yt_dlp Python library to extract media metadata,
evaluate available resolutions and bitrates, report real-time progress, and execute
downloads with cancellation support.
"""

import logging
import os
import shutil
import subprocess
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
import yt_dlp
from backend.engine.ffmpeg_manager import validate_ffmpeg_path
from backend.security.url_guard import detect_spotify_source, socket_guard_scope
try:
    from yt_dlp.version import __version__ as ytdlp_version
except ImportError:
    ytdlp_version = getattr(yt_dlp, "__version__", "unknown")

log = logging.getLogger("kon_media_engine")


class MediaEngineError(Exception):
    """Raised when media extraction or download encounters an error."""
    pass


class DownloadCancelledError(Exception):
    """Raised when a download is cancelled by user request."""
    pass


def get_engine_health(custom_ffmpeg_path: Optional[str] = None) -> Dict[str, Any]:
    """Inspect and return the health status of yt-dlp and FFmpeg."""
    ffmpeg_status = validate_ffmpeg_path(custom_ffmpeg_path)
    return {
        "ytdlp_available": True,
        "ytdlp_version": ytdlp_version,
        "ffmpeg_available": ffmpeg_status["available"],
        "ffmpeg_path": ffmpeg_status["path"],
        "ffmpeg_version": ffmpeg_status["version"],
        "ffmpeg_source": ffmpeg_status["source"],
        "ffmpeg_error": ffmpeg_status["error"],
    }


def format_duration(seconds: Optional[int | float]) -> str:
    """Format duration in seconds into human-readable HH:MM:SS or MM:SS."""
    if not seconds or seconds < 0:
        return "Unknown"
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    rem_seconds = s % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{rem_seconds:02d}"
    return f"{minutes:02d}:{rem_seconds:02d}"


def clean_codec_name(codec_str: Optional[str]) -> Optional[str]:
    """Return a human-readable clean codec representation from raw codec identifier."""
    if not codec_str or codec_str == "none":
        return None
    c = str(codec_str).lower().strip()
    if c.startswith("avc1") or c.startswith("h264"):
        return "H.264 (AVC)"
    if c.startswith("vp09") or c.startswith("vp9"):
        return "VP9"
    if c.startswith("av01"):
        return "AV1"
    if c.startswith("hvc1") or c.startswith("hevc") or c.startswith("h265"):
        return "H.265 (HEVC)"
    if c.startswith("mp4a") or c.startswith("aac"):
        return "AAC"
    if "opus" in c:
        return "Opus"
    if "vorbis" in c:
        return "Vorbis"
    if "mp3" in c:
        return "MP3"
    if "flac" in c:
        return "FLAC"
    return codec_str.split(".")[0].upper()


def determine_stream_kind(vcodec: Optional[str], acodec: Optional[str]) -> str:
    """Classify stream as 'video_only', 'audio_only', or 'combined'."""
    has_v = vcodec not in (None, "none")
    has_a = acodec not in (None, "none")
    if has_v and has_a:
        return "combined"
    if has_v:
        return "video_only"
    if has_a:
        return "audio_only"
    return "unknown"


def validate_stream_pair(
    video_stream: Optional[Dict[str, Any]],
    audio_stream: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Validate whether two chosen streams can be merged into a playable media file.

    Returns compatibility status, container recommendation, lossless capability,
    and a clear explanation of container/codec requirements.
    """
    if not video_stream and not audio_stream:
        return {
            "compatible": False,
            "requires_merge": False,
            "error": "Please select a video stream and an audio stream to pair.",
        }

    # Only video stream provided
    if video_stream and not audio_stream:
        v_kind = video_stream.get("stream_kind") or determine_stream_kind(
            video_stream.get("vcodec"), video_stream.get("acodec")
        )
        if v_kind == "combined":
            return {
                "compatible": True,
                "requires_merge": False,
                "is_combined_direct": True,
                "target_container": (video_stream.get("ext") or "mp4").lower(),
                "format_selector": str(video_stream.get("format_id")),
                "message": "This video stream already contains audio and can be downloaded directly without merging.",
            }
        elif v_kind == "video_only":
            return {
                "compatible": False,
                "requires_merge": True,
                "error": "The selected video stream has no audio. Please select an audio stream below to pair and merge.",
            }
        else:
            return {
                "compatible": False,
                "requires_merge": False,
                "error": "The format chosen under Video is an audio-only stream. Please select a valid video stream.",
            }

    # Only audio stream provided
    if audio_stream and not video_stream:
        a_kind = audio_stream.get("stream_kind") or determine_stream_kind(
            audio_stream.get("vcodec"), audio_stream.get("acodec")
        )
        if a_kind in ("audio_only", "combined"):
            return {
                "compatible": True,
                "requires_merge": False,
                "is_audio_solo": True,
                "target_container": (audio_stream.get("ext") or "m4a").lower(),
                "format_selector": str(audio_stream.get("format_id")),
                "message": "Audio stream selected for standalone direct audio download.",
            }
        else:
            return {
                "compatible": False,
                "requires_merge": False,
                "error": "The format chosen under Audio is not an audio stream.",
            }

    # Both video and audio streams provided:
    v_kind = video_stream.get("stream_kind") or determine_stream_kind(
        video_stream.get("vcodec"), video_stream.get("acodec")
    )
    a_kind = audio_stream.get("stream_kind") or determine_stream_kind(
        audio_stream.get("vcodec"), audio_stream.get("acodec")
    )

    if v_kind == "audio_only":
        return {
            "compatible": False,
            "requires_merge": False,
            "error": "The format chosen as Video is audio-only. Please choose a video stream.",
        }

    if a_kind == "video_only":
        return {
            "compatible": False,
            "requires_merge": False,
            "error": "The format chosen as Audio is video-only. Pairing two video streams is not an audio-merging solution.",
        }

    v_ext = (video_stream.get("ext") or "").lower()
    a_ext = (audio_stream.get("ext") or "").lower()
    vc = str(video_stream.get("vcodec") or "").lower()
    ac = str(audio_stream.get("acodec") or "").lower()

    # Determine container and lossless remuxing capability
    # MP4 container: supports H.264 (avc1), H.265 (hevc/hvc1), AV1 (av01) + AAC (mp4a), MP3
    is_mp4_video = v_ext == "mp4" or any(vc.startswith(p) for p in ("avc", "h264", "av01", "hvc1", "hevc", "h265"))
    is_mp4_audio = a_ext in ("m4a", "mp4") or any(ac.startswith(p) for p in ("mp4a", "aac", "mp3"))

    # WebM container: supports VP8, VP9, AV1 + Opus, Vorbis
    is_webm_video = v_ext == "webm" or any(vc.startswith(p) for p in ("vp8", "vp9", "vp09"))
    is_webm_audio = a_ext in ("webm", "opus", "ogg") or any(ac.startswith(p) for p in ("opus", "vorbis"))

    if is_mp4_video and is_mp4_audio:
        target_container = "mp4"
        lossless = True
        desc = "Compatible MP4 container: lossless stream copy without re-encoding."
    elif is_webm_video and is_webm_audio:
        target_container = "webm"
        lossless = True
        desc = "Compatible WebM container: lossless stream copy without re-encoding."
    elif is_mp4_video and is_webm_audio:
        # AVC1/MP4 video + Opus audio: can merge to MP4 with audio remuxed to AAC, preserving video losslessly
        target_container = "mp4"
        lossless = False
        desc = "Cross-container pair: video will be preserved losslessly; audio will be packaged into MP4."
    elif is_webm_video and is_mp4_audio:
        # VP9 video + AAC audio: can merge to MP4/MKV
        target_container = "mp4"
        lossless = False
        desc = "Cross-container pair: streams will be merged into standard MP4."
    else:
        target_container = "mp4"
        lossless = False
        desc = "Streams will be merged into a standard playable container using FFmpeg."

    format_selector = f"{video_stream.get('format_id')}+{audio_stream.get('format_id')}"
    return {
        "compatible": True,
        "requires_merge": True,
        "target_container": target_container,
        "lossless": lossless,
        "format_selector": format_selector,
        "message": desc,
    }


def fetch_spotify_oembed(spotify_url: str) -> Dict[str, Any]:
    """Fetch public track metadata and cover art from Spotify's official oEmbed API without credentials."""
    import httpx
    try:
        with socket_guard_scope():
            with httpx.Client(timeout=6.0, follow_redirects=True) as client:
                res = client.get("https://open.spotify.com/oembed", params={"url": spotify_url})
                if res.status_code == 200:
                    data = res.json()
                    return {
                        "title": data.get("title"),
                        "thumbnail": data.get("thumbnail_url"),
                        "provider_name": data.get("provider_name", "Spotify"),
                        "author_name": data.get("author_name"),
                    }
    except Exception as e:
        log.warning("Failed to fetch Spotify oEmbed metadata: %s", e)
    return {}


def extract_media_info(
    url: str,
    abort_event: Optional[threading.Event] = None,
    ffmpeg_location: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze a media URL without downloading, extracting supported formats and metadata."""
    ffmpeg_status = validate_ffmpeg_path(ffmpeg_location)

    # 1. Recognize Spotify sources upfront before attempting extraction
    spotify_match = detect_spotify_source(url)
    if spotify_match:
        oembed = fetch_spotify_oembed(spotify_match["canonical_url"])
        title = oembed.get("title") or spotify_match["title"]
        thumbnail = oembed.get("thumbnail")
        uploader = oembed.get("author_name") or oembed.get("provider_name") or "Spotify"
        content_type = spotify_match["content_type"]

        return {
            "title": title,
            "uploader": uploader,
            "duration": None,
            "duration_formatted": "N/A",
            "thumbnail": thumbnail,
            "extractor": "Spotify",
            "webpage_url": spotify_match["canonical_url"],
            "video_formats": [],
            "audio_formats": [],
            "ffmpeg_available": ffmpeg_status["available"],
            "supported": False,
            "is_unsupported_source": True,
            "source": "spotify",
            "content_type": content_type,
            "open_in_spotify_url": spotify_match["canonical_url"],
            "can_match_audio": content_type in ("track", "content"),
            "match_search_query": title if content_type == "track" else None,
            "message": (
                "Spotify music streams are protected by Digital Rights Management (DRM) "
                "and cannot be exported as MP3 or offline audio files."
            ),
            "guidance": (
                "To download music for offline playback, please use the official Spotify "
                "desktop or mobile application. Spotify's supported offline-download functionality "
                "operates exclusively inside Spotify."
            ),
        }

    ydl_opts: Dict[str, Any] = {
        "skip_download": True,
        "extract_flat": False,
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
    }

    if shutil.which("node"):
        ydl_opts["js_runtimes"] = {"node": {}}

    if ffmpeg_status["available"]:
        ydl_opts["ffmpeg_location"] = ffmpeg_status["path"]

    if abort_event and abort_event.is_set():
        raise DownloadCancelledError("Download was cancelled by user.")

    try:
        with socket_guard_scope():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                if not info:
                    raise MediaEngineError("Source returned no media information.")

            # Process available formats
            raw_formats = info.get("formats", [])
            video_options = []
            seen_resolutions = set()

            # Filter valid video formats by resolution height
            for f in sorted(raw_formats, key=lambda x: (x.get("height") or 0, x.get("tbr") or 0), reverse=True):
                height = f.get("height")
                vcodec = f.get("vcodec")
                acodec = f.get("acodec")

                if not height or vcodec in (None, "none"):
                    continue

                label_base = f"{height}p"
                if label_base in seen_resolutions:
                    continue
                seen_resolutions.add(label_base)

                format_id = f.get("format_id")
                has_audio = acodec not in (None, "none")
                # If audio is not included in this video stream, requires ffmpeg to merge with bestaudio
                if not has_audio:
                    format_selector = f"{format_id}+bestaudio/best"
                    requires_ffmpeg = True
                    label = f"{height}p MP4"
                else:
                    format_selector = str(format_id)
                    requires_ffmpeg = False
                    label = f"{height}p MP4 (Direct)"

                filesize = f.get("filesize") or f.get("filesize_approx")

                video_options.append({
                    "format_id": format_selector,
                    "label": label,
                    "height": height,
                    "ext": "mp4",
                    "filesize": filesize,
                    "type": "video",
                    "requires_ffmpeg": requires_ffmpeg,
                })

            # If no parsed resolutions (e.g. direct media URL), provide original quality fallback
            if not video_options:
                ext = (info.get("ext") or "mp4").lower()
                filesize = info.get("filesize") or info.get("filesize_approx")
                video_options.append({
                    "format_id": "best",
                    "label": f"Original Quality ({ext.upper()})",
                    "height": None,
                    "ext": ext,
                    "filesize": filesize,
                    "type": "video",
                    "requires_ffmpeg": False,
                })

            # Define standard audio quality options (genuine MP3 conversions require FFmpeg)
            audio_options = [
                {
                    "format_id": "bestaudio/best",
                    "label": "MP3 High (320 kbps)",
                    "bitrate": "320k",
                    "ext": "mp3",
                    "type": "audio",
                    "requires_ffmpeg": True,
                },
                {
                    "format_id": "bestaudio/best",
                    "label": "MP3 Standard (192 kbps)",
                    "bitrate": "192k",
                    "ext": "mp3",
                    "type": "audio",
                    "requires_ffmpeg": True,
                },
                {
                    "format_id": "bestaudio/best",
                    "label": "MP3 Compact (128 kbps)",
                    "bitrate": "128k",
                    "ext": "mp3",
                    "type": "audio",
                    "requires_ffmpeg": True,
                },
            ]

            # Extract distinct native audio streams
            native_audio_streams = [
                f for f in raw_formats
                if f.get("vcodec") in (None, "none") and f.get("acodec") not in (None, "none")
            ]

            # If the source has standalone or direct audio streams, offer direct audio download without FFmpeg
            ext = (info.get("ext") or "mp4").lower()
            has_standalone_audio = (
                info.get("vcodec") in (None, "none")
                and ext in ("mp3", "wav", "m4a", "flac", "ogg", "opus", "aac")
            ) or bool(native_audio_streams)

            if has_standalone_audio:
                # Find best M4A / AAC audio stream if available (universal MP4 container compatibility)
                m4a_stream = next((s for s in native_audio_streams if (s.get("ext") or "").lower() == "m4a"), None)
                # Find best WebM / Opus audio stream if available
                webm_stream = next((s for s in native_audio_streams if (s.get("ext") or "").lower() == "webm"), None)
                # Fallback to top audio stream or container ext
                primary_stream = m4a_stream or webm_stream or (native_audio_streams[0] if native_audio_streams else None)

                direct_ext = (
                    (primary_stream.get("ext") or "").lower()
                    if primary_stream
                    else (ext if ext in ("mp3", "wav", "m4a", "flac", "ogg", "opus", "aac") else "m4a")
                )
                direct_fid = str(primary_stream.get("format_id")) if primary_stream else "bestaudio/best"
                clean_acodec = clean_codec_name(primary_stream.get("acodec")) if primary_stream else direct_ext.upper()

                audio_options.insert(0, {
                    "format_id": direct_fid,
                    "label": f"Original Audio ({direct_ext.upper()}) (Direct)",
                    "bitrate": "original",
                    "ext": direct_ext,
                    "type": "audio",
                    "codec": clean_acodec,
                    "requires_ffmpeg": False,
                })

            # Process all individual streams for Additional Download Options and Smart Stream Pairing
            available_streams = []
            for f in raw_formats:
                fid = f.get("format_id")
                f_ext = (f.get("ext") or "").lower()
                if not fid or f_ext in ("mhtml", "none", "") or str(fid).startswith("sb"):
                    continue

                vc = f.get("vcodec")
                ac = f.get("acodec")
                kind = determine_stream_kind(vc, ac)
                if kind == "unknown":
                    continue

                h = f.get("height")
                w = f.get("width")
                fps = f.get("fps")
                vc_clean = clean_codec_name(vc)
                ac_clean = clean_codec_name(ac)
                tbr = round(f.get("tbr") or f.get("vbr") or f.get("abr") or 0)
                filesize = f.get("filesize") or f.get("filesize_approx")

                if kind == "video_only":
                    res_label = f"{h}p" if h else "Video"
                    desc = f"{res_label} ({vc_clean or f_ext.upper()} · {f_ext.upper()}, Video only)"
                elif kind == "audio_only":
                    res_label = f"{tbr} kbps" if tbr else "Audio"
                    desc = f"{res_label} ({ac_clean or f_ext.upper()} · {f_ext.upper()}, Audio only)"
                else:
                    res_label = f"{h}p" if h else "Combined"
                    desc = f"{res_label} ({vc_clean}+{ac_clean} · {f_ext.upper()}, Audio+Video)"

                available_streams.append({
                    "format_id": str(fid),
                    "ext": f_ext,
                    "stream_kind": kind,
                    "resolution": f.get("resolution") or (f"{h}p" if h else ("Audio only" if kind == "audio_only" else "Unknown")),
                    "height": h,
                    "width": w,
                    "fps": fps,
                    "vcodec": vc,
                    "vcodec_clean": vc_clean,
                    "acodec": ac,
                    "acodec_clean": ac_clean,
                    "bitrate_kbps": tbr,
                    "filesize": filesize,
                    "format_note": f.get("format_note"),
                    "label": desc,
                    "requires_ffmpeg": kind == "video_only",
                })

            available_video_streams = sorted(
                [s for s in available_streams if s["stream_kind"] in ("video_only", "combined")],
                key=lambda x: (x.get("height") or 0, x.get("bitrate_kbps") or 0),
                reverse=True,
            )
            available_audio_streams = sorted(
                [s for s in available_streams if s["stream_kind"] in ("audio_only", "combined")],
                key=lambda x: (x.get("bitrate_kbps") or 0),
                reverse=True,
            )

            return {
                "title": info.get("title", "Untitled Media"),
                "uploader": info.get("uploader") or info.get("channel") or "Unknown Creator",
                "duration": info.get("duration"),
                "duration_formatted": format_duration(info.get("duration")),
                "thumbnail": info.get("thumbnail"),
                "extractor": info.get("extractor_key") or info.get("extractor") or "Generic",
                "webpage_url": info.get("webpage_url", url),
                "video_formats": video_options,
                "audio_formats": audio_options,
                "available_streams": available_streams,
                "available_video_streams": available_video_streams,
                "available_audio_streams": available_audio_streams,
                "ffmpeg_available": ffmpeg_status["available"],
            }

    except yt_dlp.utils.DownloadError as e:
        clean_err = str(e).strip()
        if "ERROR:" in clean_err:
            clean_err = clean_err.split("ERROR:", 1)[1].strip()
        raise MediaEngineError(f"Media extraction failed: {clean_err}")
    except Exception as e:
        raise MediaEngineError(f"Unexpected extraction error: {e}")


def find_spotify_match(
    query: str,
    original_url: Optional[str] = None,
    original_title: Optional[str] = None,
    original_thumbnail: Optional[str] = None,
    ffmpeg_location: Optional[str] = None,
) -> Dict[str, Any]:
    """Find an authorized public source match (e.g. YouTube) for a Spotify track.

    Uses the multi-signal SearchEngine to find the most accurate public release,
    avoiding low-quality covers, parodies, or mislabeled media.
    """
    clean_query = (query or "").strip()
    if not clean_query:
        raise MediaEngineError("Search query cannot be empty.")

    try:
        from backend.search.engine import SearchEngine
        engine = SearchEngine()
        candidates = engine.search(
            query=clean_query,
            limit=5,
            expected_title=original_title,
            ffmpeg_path=ffmpeg_location,
        )

        if not candidates:
            # Fallback to direct query if multi-provider aggregator returned no candidates
            ffmpeg_status = validate_ffmpeg_path(ffmpeg_location)
            ydl_opts: Dict[str, Any] = {
                "skip_download": True,
                "extract_flat": False,
                "quiet": True,
                "no_warnings": True,
                "no_color": True,
            }
            if shutil.which("node"):
                ydl_opts["js_runtimes"] = {"node": {}}
            if ffmpeg_status["available"]:
                ydl_opts["ffmpeg_location"] = ffmpeg_status["path"]

            with socket_guard_scope():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    res = ydl.extract_info(f"ytsearch1:{clean_query}", download=False)
                    if not res or not res.get("entries"):
                        raise MediaEngineError(f"No matching public media found for: '{clean_query}'")
                    entry = res["entries"][0]
                    matched_url = entry.get("webpage_url") or entry.get("url")
                    top_cand = {"url": matched_url, "score": 1.0, "confidence": "high", "explanation": ["Direct search fallback"]}
        else:
            top_cand = candidates[0]
            matched_url = top_cand.get("url")

        if not matched_url:
            raise MediaEngineError("Search match did not return a valid URL.")

        matched_info = extract_media_info(matched_url, ffmpeg_location=ffmpeg_location)
        matched_info["is_alternative_match"] = True
        matched_info["original_spotify_title"] = original_title or clean_query
        matched_info["original_spotify_url"] = original_url
        matched_info["match_score"] = top_cand.get("score")
        matched_info["match_confidence"] = top_cand.get("confidence")
        matched_info["match_explanation"] = top_cand.get("explanation")
        if original_thumbnail and not matched_info.get("thumbnail"):
            matched_info["thumbnail"] = original_thumbnail
        matched_info["match_banner"] = f"Alternative Match for: {original_title or clean_query}"
        return matched_info
    except MediaEngineError:
        raise
    except Exception as e:
        raise MediaEngineError(f"Failed to find audio match: {e}")


def execute_download(
    url: str,
    format_selector: str,
    media_type: str,
    output_path_template: str,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    abort_event: Optional[threading.Event] = None,
    audio_bitrate: str = "320k",
    ffmpeg_location: Optional[str] = None,
    merge_output_format: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a media download with real-time progress callbacks and cancellation checks."""

    class ProgressHook:
        def __call__(self, d: Dict[str, Any]) -> None:
            if abort_event and abort_event.is_set():
                raise DownloadCancelledError("Download was cancelled by user.")

            if not progress_callback:
                return

            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                percent = (downloaded / total * 100) if total > 0 else 0
                speed = d.get("speed") or 0
                eta = d.get("eta")

                progress_callback({
                    "state": "downloading",
                    "percentage": round(percent, 1),
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "speed": speed,
                    "eta": eta,
                })
            elif status == "finished":
                progress_callback({
                    "state": "processing",
                    "percentage": 100.0,
                    "downloaded_bytes": d.get("total_bytes", 0),
                    "total_bytes": d.get("total_bytes", 0),
                    "speed": 0,
                    "eta": 0,
                })

    # 1. Guard against Spotify URLs (protected DRM streams)
    spotify_match = detect_spotify_source(url)
    if spotify_match:
        raise MediaEngineError(
            "Spotify music streams are protected by Digital Rights Management (DRM) "
            "and cannot be exported as MP3 files. To listen offline, use the official "
            "Spotify desktop or mobile application."
        )

    ydl_opts: Dict[str, Any] = {
        "outtmpl": output_path_template,
        "progress_hooks": [ProgressHook()],
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
    }

    if shutil.which("node"):
        ydl_opts["js_runtimes"] = {"node": {}}

    ffmpeg_status = validate_ffmpeg_path(ffmpeg_location)
    has_ffmpeg = ffmpeg_status["available"]

    if has_ffmpeg and ffmpeg_status.get("path"):
        ydl_opts["ffmpeg_location"] = ffmpeg_status["path"]

    if media_type == "audio":
        if audio_bitrate.startswith("original") or format_selector == "best":
            ydl_opts["format"] = format_selector or "bestaudio/best"
        else:
            if not has_ffmpeg:
                raise MediaEngineError(
                    "FFmpeg is not available. Converting audio to MP3 requires FFmpeg. "
                    "Please configure an FFmpeg location in Settings or install FFmpeg via 'winget install Gyan.FFmpeg'."
                )
            ydl_opts["format"] = "bestaudio/best"
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": audio_bitrate.replace("k", ""),
            }]
    else:
        # If multi-stream merging requested (e.g. format_id+bestaudio or custom pair)
        if "+" in (format_selector or ""):
            if not has_ffmpeg:
                raise MediaEngineError(
                    "The requested format requires merging separate video and audio streams with FFmpeg, but FFmpeg is not available. "
                    "Please configure an FFmpeg location in Settings or select a direct single-stream format."
                )
            ydl_opts["format"] = format_selector
            target_container = (merge_output_format or "mp4").lower()
            ydl_opts["merge_output_format"] = target_container
        else:
            ydl_opts["format"] = format_selector or "bestvideo+bestaudio/best"
            if has_ffmpeg:
                ydl_opts["merge_output_format"] = (merge_output_format or "mp4").lower()

    if abort_event and abort_event.is_set():
        raise DownloadCancelledError("Download was cancelled by user.")

    try:
        with socket_guard_scope():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                result = ydl.download([url])
                if result != 0:
                    raise MediaEngineError(f"yt-dlp returned non-zero code: {result}")

        return {"success": True}

    except DownloadCancelledError:
        raise
    except yt_dlp.utils.DownloadError as e:
        clean_err = str(e).strip()
        if "ERROR:" in clean_err:
            clean_err = clean_err.split("ERROR:", 1)[1].strip()
        raise MediaEngineError(f"Download failed: {clean_err}")
    except Exception as e:
        if abort_event and abort_event.is_set():
            raise DownloadCancelledError("Download was cancelled.")
        raise MediaEngineError(f"Download execution error: {e}")
