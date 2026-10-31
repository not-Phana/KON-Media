"""Audio Service for KON Media.

Handles audio stream resolution, local file detection, stream caching,
and byte-range HTTP proxying for in-browser music preview.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Optional, Tuple
from urllib.parse import quote, unquote
import httpx
import yt_dlp

from backend.config import DOWNLOADS_DIR
from backend.security.url_guard import detect_spotify_source, validate_media_url

log = logging.getLogger("kon_audio_service")

# In-memory TTL cache for resolved audio stream URLs
# Key: normalized source url or id -> Value: (timestamp, resolved_metadata_dict)
_AUDIO_RESOLVE_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CACHE_TTL_SECONDS = 7200  # 2 hours


def _get_cached_audio(key: str) -> Optional[Dict[str, Any]]:
    if key in _AUDIO_RESOLVE_CACHE:
        ts, data = _AUDIO_RESOLVE_CACHE[key]
        if time.time() - ts < _CACHE_TTL_SECONDS:
            return data
        else:
            del _AUDIO_RESOLVE_CACHE[key]
    return None


def _set_cached_audio(key: str, data: Dict[str, Any]) -> None:
    _AUDIO_RESOLVE_CACHE[key] = (time.time(), data)
    # Prune stale entries if cache grows large
    if len(_AUDIO_RESOLVE_CACHE) > 500:
        now = time.time()
        stale = [k for k, (t, _) in _AUDIO_RESOLVE_CACHE.items() if now - t >= _CACHE_TTL_SECONDS]
        for k in stale:
            _AUDIO_RESOLVE_CACHE.pop(k, None)


def find_local_downloaded_audio(
    url: str,
    title: Optional[str] = None,
    candidate_id: Optional[str] = None,
    downloads_dir: Optional[Path] = None,
    history_store: Any = None,
) -> Optional[Dict[str, Any]]:
    """Check if the requested song has already been downloaded locally."""
    target_dir = downloads_dir or DOWNLOADS_DIR
    target_path = Path(target_dir).resolve()
    if not target_path.exists():
        return None

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
                        if rec_path.exists() and rec_path.is_file():
                            # Match by URL or ID
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
                                    "title": rec.get("title") or title or rec_path.stem,
                                    "artist": rec.get("artist") or rec.get("uploader") or "",
                                    "duration": rec.get("duration"),
                                    "thumbnail": rec.get("thumbnail"),
                                    "format": mime_ext or "mp3",
                                    "is_local": True,
                                    "file_path": str(rec_path),
                                }
        except Exception as e:
            log.warning(f"Error checking history for local audio: {e}")

    # 2. Search directly in downloads directory for candidate ID or filename
    audio_extensions = {".mp3", ".m4a", ".opus", ".webm", ".wav", ".flac", ".ogg", ".aac"}
    try:
        if candidate_id and len(candidate_id) >= 5:
            for item in target_path.glob(f"*{candidate_id}*"):
                if item.is_file() and item.suffix.lower() in audio_extensions:
                    return {
                        "playable": True,
                        "source_type": "local",
                        "stream_url": f"/api/stream/{quote(item.name)}",
                        "title": title or item.stem,
                        "artist": "",
                        "duration": None,
                        "thumbnail": None,
                        "format": item.suffix.lstrip(".").lower(),
                        "is_local": True,
                        "file_path": str(item),
                    }
    except Exception as e:
        log.warning(f"Error checking downloads dir for audio: {e}")

    return None


async def resolve_audio_stream(
    url: str,
    title: Optional[str] = None,
    candidate_id: Optional[str] = None,
    downloads_dir: Optional[Path] = None,
    history_store: Any = None,
) -> Dict[str, Any]:
    """Resolve an audio stream for in-browser music playback.

    Checks:
    1. Local downloaded files (zero-latency playback).
    2. Cached stream URLs.
    3. Spotify DRM check with automatic YouTube counterpart discovery.
    4. Fast yt-dlp audio stream extraction with multi-client fallbacks (android, ios, web).
    """
    clean_url = (url or "").strip()
    if not clean_url:
        return {"playable": False, "error": "No URL provided"}

    # Step 1: Check local storage first
    local_match = find_local_downloaded_audio(
        url=clean_url,
        title=title,
        candidate_id=candidate_id,
        downloads_dir=downloads_dir,
        history_store=history_store,
    )
    if local_match:
        return local_match

    # Step 2: Check cache
    cache_key = candidate_id or clean_url
    cached = _get_cached_audio(cache_key)
    if cached:
        return cached

    # Step 3: Handle Spotify DRM
    if detect_spotify_source(clean_url):
        from backend.engine.media_engine import find_spotify_match

        loop = asyncio.get_running_loop()
        match_res = await loop.run_in_executor(None, find_spotify_match, clean_url, title)
        if match_res.get("found") and match_res.get("matched_url"):
            matched_url = match_res["matched_url"]
            # Recursively resolve the matched YouTube audio stream
            res = await resolve_audio_stream(
                url=matched_url,
                title=match_res.get("track_title") or title,
                candidate_id=match_res.get("matched_video_id"),
                downloads_dir=downloads_dir,
                history_store=history_store,
            )
            if res.get("playable"):
                res["spotify_original"] = clean_url
                _set_cached_audio(cache_key, res)
                return res

        return {
            "playable": False,
            "is_drm": True,
            "reason": (
                "Spotify audio tracks are protected by Digital Rights Management (DRM). "
                "No public audio stream is directly available."
            ),
        }

    # Step 4: Validate URL security
    try:
        validated_url = validate_media_url(clean_url)
    except Exception as e:
        return {"playable": False, "error": f"Invalid URL: {e}"}

    # Step 5: Fast yt-dlp audio stream resolution with multi-client fallbacks
    def _extract_stream() -> Dict[str, Any]:
        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "extract_flat": False,
            "socket_timeout": 15,
            "extractor_args": {
                "youtube": {
                    "player_client": ["android", "ios", "web"]
                }
            },
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(validated_url, download=False)
            if not info:
                return {"playable": False, "error": "Could not extract stream info"}

            direct_audio_url = info.get("url")
            if not direct_audio_url:
                # Check formats list if top-level url is missing
                formats = info.get("formats", [])
                audio_formats = [f for f in formats if f.get("acodec") != "none" and f.get("url")]
                if audio_formats:
                    # Prefer m4a / aac
                    m4a_fmts = [f for f in audio_formats if f.get("ext") == "m4a"]
                    chosen = m4a_fmts[-1] if m4a_fmts else audio_formats[-1]
                    direct_audio_url = chosen.get("url")

            if not direct_audio_url:
                return {"playable": False, "error": "No playable audio stream found"}

            track_title = info.get("title") or title or "Audio Preview"
            artist = info.get("artist") or info.get("uploader") or info.get("channel") or ""
            thumbnail = info.get("thumbnail")
            duration = info.get("duration")
            fmt = info.get("ext") or "m4a"

            res = {
                "playable": True,
                "source_type": "remote",
                "direct_url": direct_audio_url,
                "stream_url": f"/api/audio/stream?url={quote(direct_audio_url, safe='')}",
                "title": track_title,
                "artist": artist,
                "duration": duration,
                "thumbnail": thumbnail,
                "format": fmt,
                "is_local": False,
            }
            return res

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, _extract_stream)
        if result.get("playable"):
            _set_cached_audio(cache_key, result)
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
            user_msg = f"Preview unavailable: {raw_err[:60]}"
        log.warning(f"Audio resolution notice for {clean_url}: {user_msg}")
        return {"playable": False, "error": user_msg}
