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
                vcodec = f.get("vcodec", "none")
                acodec = f.get("acodec", "none")

                if not height or vcodec == "none":
                    continue

                label_base = f"{height}p"
                if label_base in seen_resolutions:
                    continue
                seen_resolutions.add(label_base)

                format_id = f.get("format_id")
                # If audio is not included in this video stream, requires ffmpeg to merge with bestaudio
                if acodec == "none":
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

            # Define standard audio quality options (all audio extractions require FFmpeg)
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

            # If the source has standalone or direct audio streams, offer direct audio download without FFmpeg
            ext = (info.get("ext") or "mp4").lower()
            has_standalone_audio = (
                info.get("vcodec") in (None, "none")
                and ext in ("mp3", "wav", "m4a", "flac", "ogg", "opus", "aac")
            ) or any(
                f.get("vcodec") in (None, "none")
                and f.get("acodec") not in (None, "none")
                for f in raw_formats
            )

            if has_standalone_audio:
                direct_ext = ext if ext in ("mp3", "wav", "m4a", "flac", "ogg", "opus", "aac") else "m4a"
                audio_options.insert(0, {
                    "format_id": "bestaudio/best",
                    "label": f"Original Audio ({direct_ext.upper()}) (Direct)",
                    "bitrate": "original",
                    "ext": direct_ext,
                    "type": "audio",
                    "requires_ffmpeg": False,
                })

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

    Searches via yt-dlp `ytsearch1:{query}`, extracting real formats and metadata.
    Does not circumvent DRM; queries public open media sources transparently.
    """
    clean_query = (query or "").strip()
    if not clean_query:
        raise MediaEngineError("Search query cannot be empty.")

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

    try:
        with socket_guard_scope():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_term = f"ytsearch1:{clean_query}"
                res = ydl.extract_info(search_term, download=False)
                if not res or not res.get("entries"):
                    raise MediaEngineError(f"No matching public media found for: '{clean_query}'")

                entry = res["entries"][0]
                matched_url = entry.get("webpage_url") or entry.get("url")
                if not matched_url:
                    raise MediaEngineError("Search match did not return a valid URL.")

        matched_info = extract_media_info(matched_url, ffmpeg_location=ffmpeg_location)
        matched_info["is_alternative_match"] = True
        matched_info["original_spotify_title"] = original_title or clean_query
        matched_info["original_spotify_url"] = original_url
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
        # If multi-stream merging requested (e.g. format_id+bestaudio) and FFmpeg is not available
        if "+" in (format_selector or "") and not has_ffmpeg:
            raise MediaEngineError(
                "The requested format requires merging separate video and audio streams with FFmpeg, but FFmpeg is not available. "
                "Please configure an FFmpeg location in Settings or select a direct single-stream format."
            )

        ydl_opts["format"] = format_selector or "bestvideo+bestaudio/best"
        if has_ffmpeg:
            ydl_opts["merge_output_format"] = "mp4"

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
