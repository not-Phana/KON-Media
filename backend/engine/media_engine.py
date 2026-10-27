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


def get_engine_health() -> Dict[str, Any]:
    """Inspect and return the health status of yt-dlp and FFmpeg."""
    ffmpeg_path = shutil.which("ffmpeg")
    ffmpeg_version = None
    if ffmpeg_path:
        try:
            res = subprocess.run([ffmpeg_path, "-version"], capture_output=True, text=True, timeout=5)
            first_line = res.stdout.splitlines()[0] if res.stdout else ""
            ffmpeg_version = first_line.strip()
        except Exception:
            ffmpeg_version = "available"

    return {
        "ytdlp_available": True,
        "ytdlp_version": ytdlp_version,
        "ffmpeg_available": bool(ffmpeg_path),
        "ffmpeg_path": ffmpeg_path,
        "ffmpeg_version": ffmpeg_version,
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


def extract_media_info(url: str, abort_event: Optional[threading.Event] = None) -> Dict[str, Any]:
    """Analyze a media URL without downloading, extracting supported formats and metadata."""
    ydl_opts = {
        "skip_download": True,
        "extract_flat": False,
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
    }

    if abort_event and abort_event.is_set():
        raise DownloadCancelledError("Download was cancelled by user.")

    try:
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

                label = f"{height}p"
                if label in seen_resolutions:
                    continue
                seen_resolutions.add(label)

                format_id = f.get("format_id")
                # If audio is not included in this video stream, request bestaudio merge
                if acodec == "none":
                    format_selector = f"{format_id}+bestaudio/best"
                else:
                    format_selector = str(format_id)

                filesize = f.get("filesize") or f.get("filesize_approx")

                video_options.append({
                    "format_id": format_selector,
                    "label": f"{height}p MP4",
                    "height": height,
                    "ext": "mp4",
                    "filesize": filesize,
                    "type": "video",
                })

            # Define standard audio quality options
            audio_options = [
                {
                    "format_id": "bestaudio/best",
                    "label": "MP3 High (320 kbps)",
                    "bitrate": "320k",
                    "ext": "mp3",
                    "type": "audio",
                },
                {
                    "format_id": "bestaudio/best",
                    "label": "MP3 Standard (192 kbps)",
                    "bitrate": "192k",
                    "ext": "mp3",
                    "type": "audio",
                },
                {
                    "format_id": "bestaudio/best",
                    "label": "MP3 Compact (128 kbps)",
                    "bitrate": "128k",
                    "ext": "mp3",
                    "type": "audio",
                },
            ]

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
            }

    except yt_dlp.utils.DownloadError as e:
        clean_err = str(e).strip()
        if "ERROR:" in clean_err:
            clean_err = clean_err.split("ERROR:", 1)[1].strip()
        raise MediaEngineError(f"Media extraction failed: {clean_err}")
    except Exception as e:
        raise MediaEngineError(f"Unexpected extraction error: {e}")


def execute_download(
    url: str,
    format_selector: str,
    media_type: str,
    output_path_template: str,
    progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
    abort_event: Optional[threading.Event] = None,
    audio_bitrate: str = "320k",
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

    ydl_opts: Dict[str, Any] = {
        "outtmpl": output_path_template,
        "progress_hooks": [ProgressHook()],
        "quiet": True,
        "no_warnings": True,
        "no_color": True,
    }

    if media_type == "audio":
        ydl_opts["format"] = "bestaudio/best"
        ydl_opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": audio_bitrate.replace("k", ""),
        }]
    else:
        ydl_opts["format"] = format_selector or "bestvideo+bestaudio/best"
        ydl_opts["merge_output_format"] = "mp4"

    if abort_event and abort_event.is_set():
        raise DownloadCancelledError("Download was cancelled by user.")

    try:
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
