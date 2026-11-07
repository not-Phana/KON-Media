"""Video Service for KON Media.

Handles video stream resolution, local file detection, stream caching,
and byte-range HTTP proxying for in-browser video playback from any source.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote, unquote
import httpx
import yt_dlp
from starlette.responses import StreamingResponse
from fastapi import HTTPException, Request

from backend.config import DOWNLOADS_DIR
from backend.security.url_guard import validate_media_url

log = logging.getLogger("kon_video_service")

# In-memory TTL cache for resolved video stream URLs
# Key: normalized source url or id -> Value: (timestamp, resolved_metadata_dict)
_VIDEO_RESOLVE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 7200  # 2 hours


def _get_cached_video(key: str) -> Optional[Dict[str, Any]]:
    if key in _VIDEO_RESOLVE_CACHE:
        ts, data = _VIDEO_RESOLVE_CACHE[key]
        if time.time() - ts < _CACHE_TTL_SECONDS:
            return data
        else:
            del _VIDEO_RESOLVE_CACHE[key]
    return None


def _set_cached_video(key: str, data: Dict[str, Any]) -> None:
    _VIDEO_RESOLVE_CACHE[key] = (time.time(), data)
    if len(_VIDEO_RESOLVE_CACHE) > 500:
        now = time.time()
        stale = [k for k, (t, _) in _VIDEO_RESOLVE_CACHE.items() if now - t >= _CACHE_TTL_SECONDS]
        for k in stale:
            _VIDEO_RESOLVE_CACHE.pop(k, None)


def find_local_downloaded_video(
    url: str,
    title: Optional[str] = None,
    candidate_id: Optional[str] = None,
    downloads_dir: Optional[Path] = None,
    history_store: Any = None,
    uploader: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Check if the requested video has already been downloaded locally."""
    target_dir = downloads_dir or DOWNLOADS_DIR
    target_path = Path(target_dir).resolve()
    if not target_path.exists():
        return None

    video_extensions = {".mp4", ".mkv", ".webm", ".mov", ".avi"}

    # 1. Search in history store
    if history_store:
        try:
            getter = getattr(history_store, "get_all", None) or getattr(history_store, "get_history", None)
            records = getter() if getter else []
            if not isinstance(records, list) and hasattr(history_store, "get_history"):
                records = history_store.get_history()
            if isinstance(records, list):
                for rec in records:
                    if rec.get("status") == "completed" and rec.get("file_path"):
                        rec_path = Path(rec["file_path"])
                        if rec_path.exists() and rec_path.is_file() and rec_path.suffix.lower() in video_extensions:
                            matches_url = rec.get("url") and rec["url"] == url
                            matches_id = candidate_id and (
                                candidate_id in str(rec.get("url", "")) or candidate_id == rec.get("id")
                            )
                            if matches_url or matches_id:
                                mime_ext = rec_path.suffix.lstrip(".").lower()
                                return {
                                    "playable": True,
                                    "source_type": "local",
                                    "stream_url": f"/api/stream/{quote(rec_path.name)}",
                                    "direct_url": f"/api/stream/{quote(rec_path.name)}",
                                    "title": rec.get("title") or title or rec_path.stem,
                                    "uploader": rec.get("uploader") or uploader or "",
                                    "duration": rec.get("duration"),
                                    "thumbnail": rec.get("thumbnail"),
                                    "format": mime_ext or "mp4",
                                    "resolution": "Original (Local File)",
                                    "is_local": True,
                                    "file_path": str(rec_path),
                                    "resolutions": ["Original (Local File)"],
                                }
        except Exception as e:
            log.warning(f"Error checking history for local video: {e}")

    # 2. Search directly in downloads directory for candidate ID or filename
    try:
        if candidate_id and len(candidate_id) >= 5:
            for item in target_path.glob(f"*{candidate_id}*"):
                if item.is_file() and item.suffix.lower() in video_extensions:
                    return {
                        "playable": True,
                        "source_type": "local",
                        "stream_url": f"/api/stream/{quote(item.name)}",
                        "direct_url": f"/api/stream/{quote(item.name)}",
                        "title": title or item.stem,
                        "uploader": uploader or "",
                        "duration": None,
                        "thumbnail": None,
                        "format": item.suffix.lstrip(".").lower(),
                        "resolution": "Local Video",
                        "is_local": True,
                        "file_path": str(item),
                        "resolutions": ["Local Video"],
                    }
        if title and len(title) >= 3:
            clean = "".join(c for c in title if c.isalnum() or c in (" ", "-", "_")).strip()
            if clean:
                for item in target_path.glob(f"*{clean}*"):
                    if item.is_file() and item.suffix.lower() in video_extensions:
                        return {
                            "playable": True,
                            "source_type": "local",
                            "stream_url": f"/api/stream/{quote(item.name)}",
                            "direct_url": f"/api/stream/{quote(item.name)}",
                            "title": title or item.stem,
                            "uploader": uploader or "",
                            "duration": None,
                            "thumbnail": None,
                            "format": item.suffix.lstrip(".").lower(),
                            "resolution": "Local Video",
                            "is_local": True,
                            "file_path": str(item),
                            "resolutions": ["Local Video"],
                        }
    except Exception as e:
        log.warning(f"Error checking downloads dir for video: {e}")

    return None


def extract_youtube_id(url: str, info: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Extract 11-char YouTube video ID for instant iframe embedding."""
    if info:
        ext = (info.get("extractor_key") or info.get("extractor") or "").lower()
        if "youtube" in ext and info.get("id"):
            return str(info["id"])
    if not url:
        return None
    import re
    clean = str(url).strip()
    if clean.startswith("yt_"):
        return clean[3:].replace("ch_", "")
    m = re.search(r"(?:youtu\.be/|youtube\.com/(?:embed/|v/|watch\?v=|watch\?.+&v=))([\w-]{11})", clean)
    if m:
        return m.group(1)
    if re.match(r"^[\w-]{11}$", clean):
        return clean
    return None

async def resolve_video_stream(
    url: str,
    title: Optional[str] = None,
    candidate_id: Optional[str] = None,
    downloads_dir: Optional[Path] = None,
    history_store: Any = None,
    uploader: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve a video stream for in-browser video playback from any provider or direct URL.

    Checks:
    1. Local downloaded files (zero-latency playback).
    2. In-memory stream cache.
    3. Direct video URLs (.mp4, .webm).
    4. yt-dlp video stream extraction prioritizing progressive formats with video and audio.
    """
    clean_url = (url or "").strip()
    if not clean_url:
        return {"playable": False, "error": "No URL provided"}

    # Step 1: Check local storage first
    local_match = find_local_downloaded_video(
        url=clean_url,
        title=title,
        candidate_id=candidate_id,
        downloads_dir=downloads_dir,
        history_store=history_store,
        uploader=uploader,
    )
    if local_match:
        return local_match

    # Step 2: Check cache
    cache_key = candidate_id or clean_url
    cached = _get_cached_video(cache_key)
    if cached:
        return cached

    # Step 3: Handle direct local stream path or direct video link
    if clean_url.startswith("/api/stream/"):
        return {
            "playable": True,
            "source_type": "local",
            "direct_url": clean_url,
            "stream_url": clean_url,
            "title": title or "Local Video",
            "uploader": uploader or "",
            "duration": None,
            "thumbnail": None,
            "format": "mp4",
            "resolution": "Original",
            "is_local": True,
            "resolutions": ["Original"],
        }

    # Step 3b: Handle direct video URL (.mp4, .webm, .mkv, .mov)
    from urllib.parse import urlparse
    parsed = urlparse(clean_url)
    path_lower = parsed.path.lower()
    if any(path_lower.endswith(ext) for ext in (".mp4", ".webm", ".mkv", ".mov")):
        stream_proxy = f"/api/video/stream?url={quote(clean_url)}"
        res = {
            "playable": True,
            "source_type": "direct_url",
            "direct_url": clean_url,
            "stream_url": stream_proxy,
            "title": title or Path(parsed.path).stem or "Direct Video",
            "uploader": uploader or "",
            "duration": None,
            "thumbnail": None,
            "format": path_lower.split(".")[-1],
            "resolution": "Direct Stream",
            "is_local": False,
            "resolutions": ["Direct Stream"],
        }
        _set_cached_video(cache_key, res)
        return res

    # Step 4: Validate URL security
    try:
        validated_url = validate_media_url(clean_url)
    except Exception as e:
        return {"playable": False, "error": f"Invalid URL: {e}"}

    # Step 5: Fast yt-dlp video stream extraction
    def _extract_video() -> Dict[str, Any]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "best[ext=mp4]/best[vcodec!=none][acodec!=none]/bestvideo[ext=mp4]+bestaudio/bestvideo+bestaudio/best",
            "extract_flat": False,
            "socket_timeout": 15,
            "extractor_args": {
                "youtube": {
                    "player_client": ["visionos", "android"],
                }
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(validated_url, download=False)
            if not info:
                return {"playable": False, "error": "Could not extract video stream info"}

            formats = info.get("formats", [])
            # Priority 1: Formats that have BOTH video and audio (guarantees sound)
            audio_video_fmts = [
                f for f in formats
                if f.get("vcodec") not in (None, "none")
                and f.get("acodec") not in (None, "none")
                and f.get("url")
            ]

            direct_video_url = None
            chosen_format = {}

            if audio_video_fmts:
                # Sort by height ascending so last is highest resolution with audio
                audio_video_fmts.sort(key=lambda f: (f.get("height") or 0, f.get("tbr") or 0))
                chosen_format = audio_video_fmts[-1]
                direct_video_url = chosen_format.get("url")
            elif info.get("url") and info.get("acodec") not in (None, "none"):
                direct_video_url = info.get("url")
                chosen_format = info
            else:
                # Try any format with a valid URL, preferring 720p/1080p for fast buffer startup
                valid_fmts = [f for f in formats if f.get("url") and f.get("vcodec") not in (None, "none")]
                if valid_fmts:
                    # Cap direct proxy streaming at 1080p to prevent massive 4K buffering delay
                    fast_tier = [f for f in valid_fmts if 360 <= (f.get("height") or 0) <= 1080]
                    if fast_tier:
                        fast_tier.sort(key=lambda f: f.get("height") or 0)
                        chosen_format = fast_tier[-1]
                    else:
                        chosen_format = valid_fmts[-1]
                    direct_video_url = chosen_format.get("url")

            if not direct_video_url:
                return {"playable": False, "error": "No playable video stream found"}

            # If chosen video format lacks an audio track (e.g. YouTube DASH streams),
            # extract the best matching audio stream for synchronized in-app playback
            direct_audio_url = None
            if chosen_format.get("acodec") in (None, "none"):
                audio_fmts = [
                    f for f in formats
                    if f.get("acodec") not in (None, "none")
                    and f.get("vcodec") in (None, "none")
                    and f.get("url")
                ]
                if audio_fmts:
                    # Prefer m4a (AAC) for universal browser playback
                    m4a_fmts = [f for f in audio_fmts if f.get("ext") == "m4a"]
                    if m4a_fmts:
                        m4a_fmts.sort(key=lambda f: f.get("abr") or 0)
                        chosen_audio = m4a_fmts[-1]
                    else:
                        audio_fmts.sort(key=lambda f: f.get("abr") or 0)
                        chosen_audio = audio_fmts[-1]
                    direct_audio_url = chosen_audio.get("url")

            video_title = info.get("title") or title or "Video Preview"
            resolved_uploader = uploader or info.get("uploader") or info.get("channel") or ""
            thumbnail = info.get("thumbnail")
            duration = info.get("duration")
            fmt = chosen_format.get("ext") or "mp4"
            height = chosen_format.get("height")
            res_label = f"{height}p" if height else "HD"

            available_resolutions = []
            all_heights = sorted(
                list(set(f.get("height") for f in formats if f.get("height") and f.get("vcodec") != "none")),
                reverse=True,
            )
            for h in all_heights:
                if h >= 2160:
                    lbl = f"{h}p (4K Ultra HD)"
                elif h >= 1440:
                    lbl = f"{h}p (2K Quad HD)"
                elif h >= 1080:
                    lbl = f"{h}p (Full HD)"
                elif h >= 720:
                    lbl = f"{h}p (HD)"
                else:
                    lbl = f"{h}p"
                if lbl not in available_resolutions:
                    available_resolutions.append(lbl)

            if not available_resolutions and height:
                available_resolutions.append(f"{height}p")

            yt_id = extract_youtube_id(validated_url, info)
            res = {
                "playable": True,
                "source_type": "remote",
                "youtube_id": yt_id,
                "embed_url": f"https://www.youtube-nocookie.com/embed/{yt_id}?autoplay=1&enablejsapi=1&rel=0" if yt_id else None,
                "direct_url": direct_video_url,
                "stream_url": f"/api/video/stream?url={quote(direct_video_url, safe='')}",
                "direct_audio_url": direct_audio_url,
                "audio_stream_url": f"/api/audio/stream?url={quote(direct_audio_url, safe='')}" if direct_audio_url else None,
                "has_audio": chosen_format.get("acodec") not in (None, "none") or bool(direct_audio_url),
                "title": video_title,
                "uploader": resolved_uploader,
                "duration": duration,
                "thumbnail": thumbnail,
                "format": fmt,
                "resolution": res_label,
                "width": chosen_format.get("width"),
                "height": height,
                "is_local": False,
                "resolutions": available_resolutions or ["HD"],
                "description": (info.get("description") or "")[:500],
                "channel_url": info.get("uploader_url") or info.get("channel_url"),
                "view_count": info.get("view_count"),
            }
            return res

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _extract_video)
        if result.get("playable"):
            _set_cached_video(cache_key, result)
        return result
    except Exception as e:
        raw_err = str(e)
        if "This video is not available" in raw_err or "Video unavailable" in raw_err:
            user_msg = "Video is restricted or unavailable in your region."
        elif "Private video" in raw_err:
            user_msg = "Video is set to private."
        elif "Sign in to confirm" in raw_err:
            user_msg = "Sign-in verification required by provider."
        else:
            user_msg = f"Video preview unavailable: {raw_err[:60]}"
        log.warning(f"Video resolution notice for {clean_url}: {user_msg}")
        return {"playable": False, "error": user_msg}


async def stream_video_proxy(url: str, request: Optional[Request] = None) -> StreamingResponse:
    """Proxy remote video stream with HTTP 206 Partial Content byte-range support for browser video playback."""
    target_url = unquote(url).strip()
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid video stream URL scheme")

    range_header = request.headers.get("range") if request else None
    upstream_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }
    if range_header:
        upstream_headers["Range"] = range_header

    try:
        stream_timeout = httpx.Timeout(connect=15.0, read=None, write=30.0, pool=30.0)
        client = httpx.AsyncClient(follow_redirects=True, timeout=stream_timeout)
        req = client.build_request("GET", target_url, headers=upstream_headers)
        upstream_res = await client.send(req, stream=True)
    except Exception as e:
        log.error(f"Failed to connect to upstream video stream: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to video source: {str(e)}")

    status_code = upstream_res.status_code

    raw_content_type = (upstream_res.headers.get("content-type") or "video/mp4").lower()
    if "video/mp4" in raw_content_type:
        clean_content_type = "video/mp4"
    elif "video/webm" in raw_content_type:
        clean_content_type = "video/webm"
    elif "video/quicktime" in raw_content_type:
        clean_content_type = "video/mp4"
    else:
        clean_content_type = "video/mp4"

    response_headers = {
        "Content-Type": clean_content_type,
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600",
    }
    if "content-range" in upstream_res.headers:
        response_headers["Content-Range"] = upstream_res.headers["content-range"]
    if "content-length" in upstream_res.headers:
        response_headers["Content-Length"] = upstream_res.headers["content-length"]

    async def content_iterator():
        try:
            async for chunk in upstream_res.aiter_bytes(chunk_size=262144):
                yield chunk
        finally:
            await upstream_res.aclose()
            await client.aclose()

    return StreamingResponse(
        content_iterator(),
        status_code=status_code,
        headers=response_headers,
        media_type=response_headers["Content-Type"],
    )
