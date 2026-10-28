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
from backend.engine.ffmpeg_manager import validate_ffmpeg_path, inspect_media_streams
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


def validate_stream_pairing(
    video_stream: Optional[Dict[str, Any]],
    audio_stream: Optional[Dict[str, Any]],
    ffmpeg_available: bool = True,
) -> Dict[str, Any]:
    """Validate whether a selected video stream and audio stream can be combined.

    Handles:
    - Pre-merged video formats (already contain audio): direct download, no merge needed.
    - Video-only + audio-only streams: valid merge combination, computes recommended container.
    - Two video streams or two audio streams: rejected with clear guidance.
    - Missing FFmpeg notice if separate streams require merging.
    """
    if not video_stream:
        return {
            "valid": False,
            "is_direct": False,
            "requires_ffmpeg": False,
            "recommended_container": "mp4",
            "reason": "Please select a video stream.",
            "format_selector": "",
            "video_format_id": None,
            "audio_format_id": None,
        }

    v_has_audio = bool(video_stream.get("has_audio"))
    v_id = str(video_stream.get("format_id", ""))
    v_ext = (video_stream.get("ext") or "mp4").lower()
    v_codec = (video_stream.get("vcodec") or "").lower()

    # Case 1: Video stream already contains audio (self-contained direct stream)
    if v_has_audio:
        return {
            "valid": True,
            "is_direct": True,
            "requires_ffmpeg": False,
            "recommended_container": v_ext,
            "reason": (
                f"Video stream {v_id} already includes integrated audio ({video_stream.get('acodec')}). "
                f"It can be downloaded directly as a complete playable {v_ext.upper()} file without merging."
            ),
            "video_format_id": v_id,
            "audio_format_id": None,
            "format_selector": v_id,
        }

    # Case 2: Video is video-only; audio stream is required
    if not audio_stream:
        return {
            "valid": False,
            "is_direct": False,
            "requires_ffmpeg": True,
            "recommended_container": "mp4",
            "reason": (
                f"Video stream {v_id} is video-only (contains no audio). "
                "Please select an audio stream below to pair and merge into a single playable file."
            ),
            "format_selector": "",
            "video_format_id": v_id,
            "audio_format_id": None,
        }

    # Case 3: Incompatible selection (e.g. attempting to pair two video streams)
    if audio_stream.get("has_video"):
        return {
            "valid": False,
            "is_direct": False,
            "requires_ffmpeg": True,
            "recommended_container": "mp4",
            "reason": "Cannot pair two video streams. Please choose an audio-only stream from the audio list.",
            "format_selector": "",
            "video_format_id": v_id,
            "audio_format_id": str(audio_stream.get("format_id", "")),
        }

    a_id = str(audio_stream.get("format_id", ""))
    a_ext = (audio_stream.get("ext") or "").lower()
    a_codec = (audio_stream.get("acodec") or "").lower()

    # Case 4: Valid video-only + audio-only pairing. Determine optimal container:
    if v_ext == "webm" and a_ext in ("webm", "opus", "ogg"):
        rec_container = "webm"
        note = "lossless stream copy into WebM container"
    elif (v_ext == "mp4" or "avc" in v_codec or "h264" in v_codec) and (a_ext in ("m4a", "aac") or "aac" in a_codec or "mp4a" in a_codec):
        rec_container = "mp4"
        note = "lossless stream copy into MP4 container"
    else:
        # Cross-codec or cross-container combination
        rec_container = "mkv"
        note = "lossless multi-codec container (MKV)"

    reason = (
        f"Compatible stream pairing: Video {v_id} ({v_ext.upper()}) + Audio {a_id} ({a_ext.upper()}) "
        f"will automatically merge into a playable {rec_container.upper()} file via {note}."
    )
    if not ffmpeg_available:
        reason += " (Note: FFmpeg is required for merging separate streams. Standalone stream downloads are available below)."

    return {
        "valid": True,
        "is_direct": False,
        "requires_ffmpeg": True,
        "recommended_container": rec_container,
        "reason": reason,
        "video_format_id": v_id,
        "audio_format_id": a_id,
        "format_selector": f"{v_id}+{a_id}",
    }


def extract_media_info(
    url: str,
    abort_event: Optional[threading.Event] = None,
    ffmpeg_location: Optional[str] = None,
) -> Dict[str, Any]:
    """Analyze a media URL without downloading, extracting supported formats, streams, and metadata."""
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
            "video_streams": [],
            "audio_streams": [],
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

            # Process available formats and individual streams
            raw_formats = info.get("formats", [])
            video_options = []
            seen_resolutions = set()
            video_streams = []
            audio_streams = []

            # Filter and categorize formats
            for f in sorted(raw_formats, key=lambda x: (x.get("height") or 0, x.get("tbr") or 0), reverse=True):
                format_id = str(f.get("format_id", ""))
                height = f.get("height")
                width = f.get("width")
                fps = f.get("fps")
                vcodec = f.get("vcodec")
                acodec = f.get("acodec")
                f_ext = (f.get("ext") or "mp4").lower()
                filesize = f.get("filesize") or f.get("filesize_approx")
                tbr = f.get("tbr")
                abr = f.get("abr")

                has_v = bool(vcodec and vcodec != "none")
                has_a = bool(acodec and acodec != "none")

                # Video streams (both video-only and pre-merged combined streams)
                if has_v:
                    res_str = f"{height}p" if height else "Video"
                    fps_str = f"{fps}fps" if fps and fps > 30 else ""
                    codec_short = vcodec.split(".")[0].upper() if vcodec else f_ext.upper()
                    type_tag = "[Audio + Video]" if has_a else "[Video Only]"
                    v_desc_parts = [res_str]
                    if fps_str:
                        v_desc_parts.append(fps_str)
                    v_desc_parts.append(f"({codec_short}, {f_ext.upper()})")
                    v_desc_parts.append(type_tag)
                    v_stream_label = " ".join(v_desc_parts)

                    video_streams.append({
                        "format_id": format_id,
                        "label": v_stream_label,
                        "height": height,
                        "width": width,
                        "fps": fps,
                        "vcodec": vcodec,
                        "acodec": acodec,
                        "ext": f_ext,
                        "filesize": filesize,
                        "tbr": tbr,
                        "has_video": True,
                        "has_audio": has_a,
                        "stream_type": "combined" if has_a else "video_only",
                        "requires_ffmpeg": not has_a,
                    })

                    # Quick-select video_options (one per resolution height)
                    if height and height not in seen_resolutions:
                        seen_resolutions.add(height)
                        if not has_a:
                            format_selector = f"{format_id}+bestaudio/best"
                            requires_ffmpeg = True
                            label = f"{height}p MP4"
                        else:
                            format_selector = str(format_id)
                            requires_ffmpeg = False
                            label = f"{height}p MP4 (Direct)"

                        video_options.append({
                            "format_id": format_selector,
                            "label": label,
                            "height": height,
                            "ext": "mp4",
                            "filesize": filesize,
                            "type": "video",
                            "requires_ffmpeg": requires_ffmpeg,
                        })

                # Standalone audio streams
                elif has_a and not has_v:
                    codec_short = acodec.split(".")[0].upper() if acodec else f_ext.upper()
                    br_val = abr or tbr
                    br_str = f"{int(br_val)} kbps" if br_val else "Audio"
                    a_stream_label = f"{br_str} ({codec_short}, {f_ext.upper()}) [Audio Only]"

                    audio_streams.append({
                        "format_id": format_id,
                        "label": a_stream_label,
                        "bitrate": f"{int(br_val)}k" if br_val else f_ext,
                        "abr": br_val,
                        "acodec": acodec,
                        "ext": f_ext,
                        "filesize": filesize,
                        "has_video": False,
                        "has_audio": True,
                        "stream_type": "audio_only",
                        "requires_ffmpeg": False,
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

            # Sort audio streams by bitrate descending
            audio_streams.sort(key=lambda x: (x.get("abr") or 0), reverse=True)

            # Define standard audio quality options (MP3 conversion requires FFmpeg)
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

            # If standalone or direct audio streams exist, offer direct audio download without FFmpeg
            ext_info = (info.get("ext") or "mp4").lower()
            has_standalone_audio = bool(audio_streams) or (
                info.get("vcodec") in (None, "none")
                and ext_info in ("mp3", "wav", "m4a", "flac", "ogg", "opus", "aac")
            )

            if has_standalone_audio:
                # Prefer m4a for maximum desktop compatibility if available, otherwise highest bitrate stream
                m4a_stream = next((a for a in audio_streams if a.get("ext") == "m4a"), None)
                if ext_info in ("mp3", "wav", "m4a", "flac", "ogg", "opus", "aac"):
                    direct_ext = ext_info
                    direct_fmt_id = "bestaudio/best"
                elif m4a_stream:
                    direct_ext = "m4a"
                    direct_fmt_id = "bestaudio[ext=m4a]/bestaudio/best"
                elif audio_streams:
                    best_audio = audio_streams[0]
                    direct_ext = best_audio["ext"]
                    direct_fmt_id = best_audio["format_id"]
                else:
                    direct_ext = "m4a"
                    direct_fmt_id = "bestaudio/best"

                audio_options.insert(0, {
                    "format_id": direct_fmt_id,
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
                "video_streams": video_streams,
                "audio_streams": audio_streams,
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
    merge_output_format: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute a media download with real-time progress callbacks, stage reporting, and cancellation checks."""

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

                # Detect active stream stage from info_dict
                info_dict = d.get("info_dict", {})
                vcodec = info_dict.get("vcodec")
                acodec = info_dict.get("acodec")
                has_v = bool(vcodec and vcodec != "none")
                has_a = bool(acodec and acodec != "none")

                if has_v and not has_a:
                    stage = "downloading_video"
                    stage_label = "Downloading video stream..."
                elif has_a and not has_v:
                    stage = "downloading_audio"
                    stage_label = "Downloading audio stream..."
                else:
                    stage = "downloading"
                    stage_label = "Downloading media data..."

                progress_callback({
                    "state": "downloading",
                    "stage": stage,
                    "stage_label": stage_label,
                    "percentage": round(percent, 1),
                    "downloaded_bytes": downloaded,
                    "total_bytes": total,
                    "speed": speed,
                    "eta": eta,
                })
            elif status == "finished":
                progress_callback({
                    "state": "processing",
                    "stage": "processing",
                    "stage_label": "Processing downloaded stream...",
                    "percentage": 100.0,
                    "downloaded_bytes": d.get("total_bytes", 0),
                    "total_bytes": d.get("total_bytes", 0),
                    "speed": 0,
                    "eta": 0,
                })

    class PostprocessorHook:
        def __call__(self, d: Dict[str, Any]) -> None:
            if abort_event and abort_event.is_set():
                raise DownloadCancelledError("Download was cancelled by user.")

            if not progress_callback:
                return

            pp_name = d.get("postprocessor", "")
            status = d.get("status", "")

            if pp_name == "Merger":
                if status == "started":
                    progress_callback({
                        "state": "processing",
                        "stage": "merging",
                        "stage_label": "Merging video and audio streams with FFmpeg...",
                        "percentage": 100.0,
                    })
                elif status == "finished":
                    progress_callback({
                        "state": "processing",
                        "stage": "verifying",
                        "stage_label": "Verifying merged output...",
                        "percentage": 100.0,
                    })
            elif pp_name == "FFmpegExtractAudio":
                if status == "started":
                    progress_callback({
                        "state": "processing",
                        "stage": "converting",
                        "stage_label": "Converting audio to MP3 with FFmpeg...",
                        "percentage": 100.0,
                    })
                elif status == "finished":
                    progress_callback({
                        "state": "processing",
                        "stage": "verifying",
                        "stage_label": "Verifying converted audio...",
                        "percentage": 100.0,
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
        "postprocessor_hooks": [PostprocessorHook()],
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
        # Multi-stream merging requested (e.g. format_id+bestaudio or format_id+audio_id)
        if "+" in (format_selector or "") and not has_ffmpeg:
            raise MediaEngineError(
                "The requested format requires merging separate video and audio streams with FFmpeg, but FFmpeg is not available. "
                "Please configure an FFmpeg location in Settings or select a direct single-stream format."
            )

        ydl_opts["format"] = format_selector or "bestvideo+bestaudio/best"
        if has_ffmpeg:
            # Set target container (e.g. mp4, webm, mkv)
            ydl_opts["merge_output_format"] = merge_output_format or "mp4"

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
