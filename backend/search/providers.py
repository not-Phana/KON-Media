"""Layer C: Extensible search providers (YouTube, SoundCloud, Mock) and candidate aggregation."""

import concurrent.futures
import json
import logging
import shutil
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import requests
import yt_dlp

_PROVIDER_SESSION: Optional[requests.Session] = None


def get_provider_session() -> requests.Session:
    """Return a thread-safe singleton requests.Session with connection pooling."""
    global _PROVIDER_SESSION
    if _PROVIDER_SESSION is None:
        _PROVIDER_SESSION = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=50,
            max_retries=1,
            pool_block=False,
        )
        _PROVIDER_SESSION.mount("https://", adapter)
        _PROVIDER_SESSION.mount("http://", adapter)
        _PROVIDER_SESSION.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
        })
    return _PROVIDER_SESSION

try:
    import kon_search_core as _rust_core
except ImportError:
    _rust_core = None
from backend.search.models import CandidateResult
from backend.security.url_guard import socket_guard_scope
from backend.engine.ffmpeg_manager import validate_ffmpeg_path

log = logging.getLogger("kon_search_providers")


def parse_duration_str(d_str: str) -> Optional[float]:
    """Parse duration string like '4:41' or '1:02:15' into seconds."""
    if not d_str:
        return None
    try:
        parts = d_str.strip().split(":")
        if len(parts) == 1:
            return float(parts[0])
        elif len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    except Exception:
        pass
    return None


def parse_view_count(v_str: str) -> Optional[int]:
    """Parse view count text like '1.2M views' or '540K views' into integer."""
    if not v_str:
        return None
    try:
        clean = v_str.lower().replace("views", "").replace("view", "").replace(",", "").strip()
        if clean.endswith("m"):
            return int(float(clean[:-1]) * 1_000_000)
        elif clean.endswith("k"):
            return int(float(clean[:-1]) * 1_000)
        elif clean.endswith("b"):
            return int(float(clean[:-1]) * 1_000_000_000)
        return int(float(clean))
    except Exception:
        return None


def normalize_media_url(url: str) -> str:
    """Normalize media URL while preserving essential identifier parameters."""
    if _rust_core is not None:
        try:
            return _rust_core.normalize_media_url(url)
        except Exception:
            pass
    clean = url.strip()
    if "youtube.com/watch" in clean and "v=" in clean:
        import urllib.parse
        parsed = urllib.parse.urlparse(clean)
        qs = urllib.parse.parse_qs(parsed.query)
        v = qs.get("v", [""])[0]
        return f"https://www.youtube.com/watch?v={v}"
    return clean.split("&")[0].split("?")[0].rstrip("/")


class SearchProvider(ABC):
    """Abstract interface for media search providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider identifier (e.g. 'youtube', 'soundcloud')."""
        pass

    @abstractmethod
    def search(self, query: str, limit: int = 5, ffmpeg_path: Optional[str] = None) -> List[CandidateResult]:
        """Execute query search and return raw candidates."""
        pass


def extract_best_thumbnail(entry: Dict[str, Any], video_id: Optional[str] = None) -> Optional[str]:
    """Extract best high-resolution thumbnail URL across YouTube, SoundCloud, and custom extractors."""
    # 1. Direct thumbnail string
    thumb = entry.get("thumbnail")
    if thumb and isinstance(thumb, str) and thumb.startswith("http"):
        return thumb

    # 2. Inspect 'thumbnails' array (e.g. SoundCloud artwork formats: t500x500, t300x300, large)
    thumbs = entry.get("thumbnails")
    if thumbs and isinstance(thumbs, list):
        valid = [
            t for t in thumbs
            if isinstance(t, dict) and t.get("url") and isinstance(t["url"], str) and t["url"].startswith("http")
        ]
        if valid:
            preferred_ids = (
                "t500x500",
                "t300x300",
                "crop",
                "large",
                "hqdefault",
                "maxresdefault",
                "sddefault",
                "medium",
                "default",
            )
            for pid in preferred_ids:
                for t in valid:
                    if t.get("id") == pid:
                        return t["url"]
            sorted_thumbs = sorted(valid, key=lambda x: (x.get("preference") or 0, x.get("width") or 0))
            return sorted_thumbs[-1]["url"]

    # 3. Alternative metadata fields
    for field in ("artwork_url", "avatar_url", "poster", "image"):
        val = entry.get(field)
        if val and isinstance(val, str) and val.startswith("http"):
            return val

    # 4. Fallback YouTube thumbnail
    if video_id and len(video_id) == 11 and not video_id.startswith("http"):
        return f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

    return None


class YouTubeSearchProvider(SearchProvider):
    """High-performance YouTube search using direct Innertube API (~1.2s) with resilient yt-dlp fallback."""

    @property
    def name(self) -> str:
        return "youtube"

    def _search_innertube(self, query: str, limit: int = 5) -> List[CandidateResult]:
        """Query YouTube Innertube public endpoint for sub-second candidate retrieval with pooled keep-alive."""
        url = "https://www.youtube.com/youtubei/v1/search?prettyPrint=false"
        payload = {
            "context": {
                "client": {
                    "clientName": "WEB",
                    "clientVersion": "2.20230501.00.00",
                    "hl": "en",
                    "gl": "US",
                }
            },
            "query": query,
        }
        candidates: List[CandidateResult] = []
        try:
            session = get_provider_session()
            with socket_guard_scope():
                resp = session.post(
                    url,
                    json=payload,
                    timeout=3.5,
                    headers={"Content-Type": "application/json"},
                )
                if resp.status_code != 200:
                    return []
                data = resp.json()

            contents = (
                data.get("contents", {})
                .get("twoColumnSearchResultsRenderer", {})
                .get("primaryContents", {})
                .get("sectionListRenderer", {})
                .get("contents", [])
            )
            for sec in contents:
                items = sec.get("itemSectionRenderer", {}).get("contents", [])
                for item in items:
                    vr = item.get("videoRenderer")
                    if not vr:
                        continue
                    vid = vr.get("videoId")
                    if not vid:
                        continue

                    title = "".join(r.get("text", "") for r in vr.get("title", {}).get("runs", [])) or vr.get("title", {}).get("simpleText", "Untitled")
                    uploader = "".join(r.get("text", "") for r in vr.get("ownerText", {}).get("runs", [])) or ""
                    duration = parse_duration_str(vr.get("lengthText", {}).get("simpleText", ""))
                    views = parse_view_count(vr.get("viewCountText", {}).get("simpleText", ""))
                    thumbs = vr.get("thumbnail", {}).get("thumbnails", [])
                    thumb = thumbs[-1].get("url") if thumbs else None

                    cand = CandidateResult(
                        id=f"yt_{vid}",
                        title=title,
                        uploader=uploader,
                        url=f"https://www.youtube.com/watch?v={vid}",
                        duration=duration,
                        thumbnail=thumb,
                        platform="youtube",
                        views=views,
                    )
                    candidates.append(cand)
                    if len(candidates) >= limit:
                        return candidates
            return candidates
        except Exception as e:
            log.debug("Innertube search bypassed or timed out: %s", e)
            return []

    def _search_ytdlp(self, query: str, limit: int = 5, ffmpeg_path: Optional[str] = None) -> List[CandidateResult]:
        """Fallback extraction using yt-dlp flat playlist."""
        ffmpeg_status = validate_ffmpeg_path(ffmpeg_path)
        ydl_opts: Dict[str, Any] = {
            "skip_download": True,
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "socket_timeout": 6,
        }
        if shutil.which("node"):
            ydl_opts["js_runtimes"] = {"node": {}}
        if ffmpeg_status["available"]:
            ydl_opts["ffmpeg_location"] = ffmpeg_status["path"]

        search_term = f"ytsearch{limit}:{query}"
        candidates: List[CandidateResult] = []

        try:
            with socket_guard_scope():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    res = ydl.extract_info(search_term, download=False)
                    if not res or not res.get("entries"):
                        return []

                    for entry in res["entries"]:
                        if not entry or not isinstance(entry, dict):
                            continue
                        url = entry.get("url") or entry.get("webpage_url")
                        if not url:
                            continue
                        if not url.startswith("http"):
                            url = f"https://www.youtube.com/watch?v={url}"

                        cand = CandidateResult(
                            id=f"yt_{entry.get('id', str(len(candidates)))}",
                            title=entry.get("title") or "Untitled",
                            uploader=entry.get("uploader") or entry.get("channel") or "",
                            url=url,
                            duration=float(entry.get("duration") or 0.0) or None,
                            thumbnail=extract_best_thumbnail(entry, video_id=entry.get("id")),
                            platform="youtube",
                            views=entry.get("view_count"),
                        )
                        candidates.append(cand)
            return candidates
        except Exception as e:
            log.warning("YouTube search provider encountered error: %s", e)
            return []

    def search(self, query: str, limit: int = 5, ffmpeg_path: Optional[str] = None) -> List[CandidateResult]:
        clean_query = query.strip()
        if not clean_query:
            return []

        # 1. Fast Innertube lookup (~1.2s)
        candidates = self._search_innertube(clean_query, limit=limit)
        if candidates:
            return candidates

        # 2. Resilient yt-dlp fallback
        return self._search_ytdlp(clean_query, limit=limit, ffmpeg_path=ffmpeg_path)


class SoundCloudSearchProvider(SearchProvider):
    """Searches SoundCloud public catalog via yt-dlp `scsearch{limit}:{query}`."""

    @property
    def name(self) -> str:
        return "soundcloud"

    def search(self, query: str, limit: int = 5, ffmpeg_path: Optional[str] = None) -> List[CandidateResult]:
        clean_query = query.strip()
        if not clean_query:
            return []

        ydl_opts: Dict[str, Any] = {
            "skip_download": True,
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "no_color": True,
            "socket_timeout": 5,
        }

        search_term = f"scsearch{limit}:{clean_query}"
        candidates: List[CandidateResult] = []

        try:
            with socket_guard_scope():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    res = ydl.extract_info(search_term, download=False)
                    if not res or not res.get("entries"):
                        return []

                    for entry in res["entries"]:
                        if not entry or not isinstance(entry, dict):
                            continue
                        url = entry.get("webpage_url") or entry.get("url")
                        if not url or not url.startswith("http"):
                            continue

                        cand = CandidateResult(
                            id=f"sc_{entry.get('id', str(len(candidates)))}",
                            title=entry.get("title") or "Untitled",
                            uploader=entry.get("uploader") or "",
                            url=url,
                            duration=float(entry.get("duration") or 0.0) or None,
                            thumbnail=extract_best_thumbnail(entry),
                            platform="soundcloud",
                            views=entry.get("view_count"),
                        )
                        candidates.append(cand)
            return candidates
        except Exception as e:
            log.warning("SoundCloud search provider encountered error: %s", e)
            return []


class MultiProviderAggregator:
    """Aggregates and deduplicates candidate results from multiple media providers with adaptive concurrency."""

    def __init__(self, providers: Optional[List[SearchProvider]] = None):
        self.providers: List[SearchProvider] = providers or [
            YouTubeSearchProvider(),
            SoundCloudSearchProvider(),
        ]
        self.last_status: Dict[str, Any] = {
            "completed": [],
            "timed_out": [],
            "failed": [],
            "is_complete": True,
        }

    def aggregate_candidates(
        self,
        query: str,
        limit_per_provider: int = 5,
        ffmpeg_path: Optional[str] = None,
        preferred_provider: Optional[str] = None,
        media_type: str = "all",
        timeout: float = 12.0,
    ) -> List[CandidateResult]:
        """Query providers concurrently with early-exit optimization and deduplication."""
        all_candidates: List[CandidateResult] = []
        seen_urls = set()
        seen_titles = set()

        active_providers = list(self.providers)
        # If media_type is video, exclude audio-only SoundCloud
        if media_type == "video":
            active_providers = [p for p in active_providers if p.name != "soundcloud"]

        if preferred_provider:
            active_providers.sort(key=lambda p: 0 if p.name == preferred_provider else 1)

        completed_providers: List[str] = []
        timed_out_providers: List[str] = []
        failed_providers: List[str] = []

        max_pool_target = min(max(limit_per_provider * (len(active_providers) or 1), 24), 60)
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=len(active_providers) or 2)
        future_to_provider = {
            executor.submit(p.search, query, limit_per_provider, ffmpeg_path): p
            for p in active_providers
        }
        try:
            for future in concurrent.futures.as_completed(future_to_provider, timeout=timeout):
                p = future_to_provider[future]
                try:
                    results = future.result()
                    completed_providers.append(p.name)
                    for cand in results:
                        norm_url = normalize_media_url(cand.url)
                        if norm_url in seen_urls:
                            continue
                        seen_urls.add(norm_url)

                        title_key = cand.title.lower().strip()
                        if title_key in seen_titles:
                            continue
                        seen_titles.add(title_key)

                        all_candidates.append(cand)

                    # Stop collecting if we reached max pool target
                    if len(all_candidates) >= max_pool_target:
                        break

                    # Fast-path early completion:
                    # If primary provider (YouTube or preferred) completed and returned sufficient candidates,
                    # don't wait seconds for slow secondary providers like SoundCloud.
                    is_primary = (p.name == "youtube") if not preferred_provider else (p.name == preferred_provider)
                    if is_primary and (len(all_candidates) >= 8 or len(results) >= 5):
                        break
                except Exception as e:
                    failed_providers.append(p.name)
                    log.warning("Provider %s search error: %s", p.name, e)
        except TimeoutError:
            # Mark remaining outstanding providers as timed out
            for future, p in future_to_provider.items():
                if not future.done() and p.name not in timed_out_providers:
                    timed_out_providers.append(p.name)
            log.warning("Search completed with partial provider results due to timeout (%s timed out).", timed_out_providers)
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        self.last_status = {
            "completed": completed_providers,
            "timed_out": timed_out_providers,
            "failed": failed_providers,
            "is_complete": len(timed_out_providers) == 0 and len(failed_providers) == 0,
        }

        return all_candidates
