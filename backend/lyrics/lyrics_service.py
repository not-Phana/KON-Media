"""Lyrics extraction, synchronization parsing, and local caching service for KON Media."""

import asyncio
import logging
import re
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.config import STATE_DIR

log = logging.getLogger("kon_lyrics")

USER_AGENT = "KON-Media/1.2 (https://github.com/not-Phana/KON-Media)"
LRCLIB_BASE_URL = "https://lrclib.net/api"

# Regex patterns for cleaning titles
CLUTTER_PATTERNS = [
    r"\[(?:official|music|video|audio|lyrics?|hd|4k|mv|visualizer|remastered|live).*?\]",
    r"\((?:official|music|video|audio|lyrics?|hd|4k|mv|visualizer|remastered|live).*?\)",
    r"\b(?:official\s+(?:music\s+)?video|official\s+audio|lyrics?\s+video|lyric\s+video)\b",
    r"\b(?:4k|hd|1080p|remastered|hq)\b",
    r"【.*?】",  # Japanese bracket clutter
    r"「.*?」",  # Japanese quotation marks when used as title wrapper
]

LRC_TIMESTAMP_REGEX = re.compile(r"\[(\d{1,2}):(\d{1,2}(?:\.\d{1,3})?)\]")


def parse_lrc(lrc_text: str) -> List[Dict[str, Any]]:
    """Parse standard LRC format into a sorted list of timestamped lines.
    
    Each line format: {"time": float_seconds, "text": str}
    Handles multiple timestamps per line (e.g., [00:12.34][00:45.67] repeated chorus).
    """
    if not lrc_text:
        return []

    parsed_lines: List[Dict[str, Any]] = []

    for raw_line in lrc_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Find all timestamps on this line
        matches = list(LRC_TIMESTAMP_REGEX.finditer(line))
        if not matches:
            continue

        # The lyric text is everything after the last timestamp
        last_match = matches[-1]
        lyric_text = line[last_match.end():].strip()

        # Each timestamp on the line produces a timestamped line entry
        for m in matches:
            mins = int(m.group(1))
            secs = float(m.group(2))
            total_seconds = round(mins * 60 + secs, 2)
            parsed_lines.append({
                "time": total_seconds,
                "text": lyric_text,
            })

    # Sort strictly by timestamp
    parsed_lines.sort(key=lambda item: item["time"])
    return parsed_lines


def clean_artist_name(raw_artist: Optional[str]) -> str:
    """Clean channel/artist name by stripping common YouTube/VEVO channel suffixes."""
    if not raw_artist:
        return ""
    a = raw_artist.strip()
    # Strip VEVO, Official, Topic, Channel, Records, etc.
    a = re.sub(
        r"\b(official(?:\s+(?:channel|audio|video|music))?|vevo|topic|channel|records|music)\b",
        "",
        a,
        flags=re.IGNORECASE,
    ).strip()
    # Strip brackets e.g. [Official] or (Topic)
    a = re.sub(r"[\[\(].*?[\]\)]", "", a).strip()
    a = re.sub(r"^[-\s\"']+|[-\s\"']+$", "", a)
    return a


def clean_music_title(raw_title: str, raw_artist: Optional[str] = None) -> Tuple[str, str]:
    """Clean video title clutter and extract title and artist if bundled as 'Artist - Title'."""
    title = raw_title.strip() if raw_title else ""
    artist = clean_artist_name(raw_artist)

    # Strip bracketed clutter from title
    for pat in CLUTTER_PATTERNS:
        title = re.sub(pat, "", title, flags=re.IGNORECASE).strip()

    # If title contains ' - ' and artist is empty or matches part of it, split them
    if " - " in title:
        parts = title.split(" - ", 1)
        potential_artist = clean_artist_name(parts[0].strip())
        potential_title = parts[1].strip()

        if not artist or artist.lower() in ["youtube", "topic", "various artists"]:
            artist = potential_artist
            title = potential_title
        elif potential_artist.lower() == artist.lower():
            title = potential_title

    # Strip leftover trailing dashes or quotes
    title = re.sub(r"^[-\s\"']+|[-\s\"']+$", "", title)
    artist = re.sub(r"^[-\s\"']+|[-\s\"']+$", "", artist)

    return title, artist


class LyricsCache:
    """Local SQLite-backed cache for lyrics records."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or (STATE_DIR / "lyrics_cache.db")
        self._init_db()

    def _init_db(self):
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lyrics_cache (
                        cache_key TEXT PRIMARY KEY,
                        track_name TEXT,
                        artist_name TEXT,
                        synced INTEGER,
                        plain_lyrics TEXT,
                        synced_lyrics TEXT,
                        instrumental INTEGER,
                        source TEXT,
                        created_at REAL
                    );
                """)
                conn.commit()
        except Exception as e:
            log.error(f"Failed to initialize lyrics cache DB: {e}")

    def _make_key(self, title: str, artist: str) -> str:
        clean_t = re.sub(r"[^\w\s]", "", title.lower()).strip()
        clean_a = re.sub(r"[^\w\s]", "", artist.lower()).strip() if artist else ""
        return f"{clean_a}::{clean_t}"

    def get(self, title: str, artist: str = "") -> Optional[Dict[str, Any]]:
        key = self._make_key(title, artist)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM lyrics_cache WHERE cache_key = ?",
                    (key,)
                )
                row = cursor.fetchone()
                if row:
                    synced_raw = row["synced_lyrics"]
                    lines = parse_lrc(synced_raw) if synced_raw else []
                    return {
                        "found": True,
                        "synced": bool(row["synced"]),
                        "track_name": row["track_name"],
                        "artist_name": row["artist_name"],
                        "lines": lines,
                        "plain_lyrics": row["plain_lyrics"],
                        "instrumental": bool(row["instrumental"]),
                        "source": row["source"],
                        "cached": True,
                    }
        except Exception as e:
            log.warning(f"Lyrics cache read error: {e}")
        return None

    def set(
        self,
        title: str,
        artist: str,
        track_name: str,
        artist_name: str,
        synced: bool,
        plain_lyrics: Optional[str],
        synced_lyrics: Optional[str],
        instrumental: bool = False,
        source: str = "lrclib",
    ):
        key = self._make_key(title, artist)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO lyrics_cache (
                        cache_key, track_name, artist_name, synced,
                        plain_lyrics, synced_lyrics, instrumental, source, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    key,
                    track_name,
                    artist_name,
                    1 if synced else 0,
                    plain_lyrics,
                    synced_lyrics,
                    1 if instrumental else 0,
                    source,
                    time.time(),
                ))
                conn.commit()
        except Exception as e:
            log.warning(f"Lyrics cache write error: {e}")


class LyricsService:
    """Lyrics retrieval and synchronization coordinator."""

    def __init__(self, cache: Optional[LyricsCache] = None):
        self.cache = cache or LyricsCache()

    async def get_lyrics(
        self,
        raw_title: str,
        raw_artist: Optional[str] = None,
        duration: Optional[float] = None,
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch synchronized or plain lyrics for a track with intelligent multi-stage discovery."""
        title, artist = clean_music_title(raw_title, raw_artist)
        if not title:
            return {
                "found": False,
                "synced": False,
                "error": "Missing song title for lyrics search",
                "lines": [],
                "plain_lyrics": None,
            }

        # 1. Local sidecar .lrc check
        if file_path:
            local_res = self._check_local_lrc(file_path)
            if local_res:
                return local_res

        # 2. Local cache check
        cached = self.cache.get(title, artist)
        if cached:
            return cached

        # 3. If artist is empty, discover candidate artists from local search engine
        candidate_artists = [artist] if artist else []
        if not artist:
            discovered = self._discover_potential_artists(title)
            candidate_artists.extend([a for a in discovered if a not in candidate_artists])

        # 4. Query LRCLIB with candidate artists
        for cand_artist in candidate_artists:
            data = await self._fetch_from_lrclib(title, cand_artist, duration)
            if data and (data.get("syncedLyrics") or data.get("plainLyrics")):
                return self._process_and_cache(data, title, cand_artist)

        # 5. If still not found and duration is known, try structured search by track_name and match duration
        fallback_data = await self._search_by_track_and_duration(title, duration)
        if fallback_data:
            return self._process_and_cache(fallback_data, title, fallback_data.get("artistName", ""))

        return {
            "found": False,
            "synced": False,
            "error": "No lyrics found for this track",
            "lines": [],
            "plain_lyrics": None,
        }

    def _discover_potential_artists(self, title: str) -> List[str]:
        """Use KON Media's search engine to discover likely artist names for an ambiguous title."""
        candidates = []
        try:
            from backend.search.engine import SearchEngine
            engine = SearchEngine()
            results = engine.search(title, limit=4)
            for res in results:
                # 1. From uploader
                u = clean_artist_name(res.get("uploader", ""))
                if u and u not in candidates and u.lower() not in ["youtube", "topic"]:
                    candidates.append(u)

                # 2. From 'Artist - Title' in candidate title
                raw_t = res.get("title", "")
                if " - " in raw_t:
                    parts = raw_t.split(" - ", 1)
                    pot_a = clean_artist_name(parts[0])
                    if pot_a and pot_a not in candidates:
                        candidates.append(pot_a)
        except Exception as e:
            log.debug(f"Artist discovery error: {e}")
        return candidates

    def _process_and_cache(self, data: Dict[str, Any], query_title: str, query_artist: str) -> Dict[str, Any]:
        synced_text = data.get("syncedLyrics")
        plain_text = data.get("plainLyrics")
        has_synced = bool(synced_text)
        lines = parse_lrc(synced_text) if has_synced else []
        track_name = data.get("trackName") or query_title
        artist_name = data.get("artistName") or query_artist
        instrumental = bool(data.get("instrumental", False))

        # Store in cache under both original query key and resolved metadata key
        self.cache.set(
            title=query_title,
            artist=query_artist,
            track_name=track_name,
            artist_name=artist_name,
            synced=has_synced,
            plain_lyrics=plain_text,
            synced_lyrics=synced_text,
            instrumental=instrumental,
            source="lrclib",
        )
        if query_artist != artist_name:
            self.cache.set(
                title=query_title,
                artist=artist_name,
                track_name=track_name,
                artist_name=artist_name,
                synced=has_synced,
                plain_lyrics=plain_text,
                synced_lyrics=synced_text,
                instrumental=instrumental,
                source="lrclib",
            )

        return {
            "found": True,
            "synced": has_synced,
            "track_name": track_name,
            "artist_name": artist_name,
            "lines": lines,
            "plain_lyrics": plain_text,
            "instrumental": instrumental,
            "source": "lrclib",
            "cached": False,
        }

    def _check_local_lrc(self, file_path_str: str) -> Optional[Dict[str, Any]]:
        """Look for a matching .lrc file next to the local audio file."""
        try:
            audio_path = Path(file_path_str)
            if not audio_path.exists():
                return None

            lrc_path = audio_path.with_suffix(".lrc")
            if lrc_path.exists() and lrc_path.is_file():
                text = lrc_path.read_text(encoding="utf-8", errors="replace")
                lines = parse_lrc(text)
                return {
                    "found": True,
                    "synced": len(lines) > 0,
                    "track_name": audio_path.stem,
                    "artist_name": "",
                    "lines": lines,
                    "plain_lyrics": text,
                    "instrumental": False,
                    "source": "local_file",
                    "cached": True,
                }
        except Exception as e:
            log.warning(f"Error checking local lrc file: {e}")
        return None

    async def _fetch_from_lrclib(
        self,
        title: str,
        artist: str,
        duration: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Query LRCLIB API with exact track_name and artist_name."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            # 1. Exact GET with duration
            if duration and duration > 0 and artist:
                try:
                    res = await client.get(
                        f"{LRCLIB_BASE_URL}/get",
                        params={"track_name": title, "artist_name": artist, "duration": int(duration)}
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("plainLyrics") or data.get("syncedLyrics"):
                            return data
                except Exception as e:
                    log.debug(f"LRCLIB get with duration failed: {e}")

            # 2. Exact GET without duration
            if artist:
                try:
                    res = await client.get(
                        f"{LRCLIB_BASE_URL}/get",
                        params={"track_name": title, "artist_name": artist}
                    )
                    if res.status_code == 200:
                        data = res.json()
                        if data.get("plainLyrics") or data.get("syncedLyrics"):
                            return data
                except Exception as e:
                    log.debug(f"LRCLIB get without duration failed: {e}")

            # 3. Structured search by track_name and artist_name
            if artist:
                try:
                    res = await client.get(
                        f"{LRCLIB_BASE_URL}/search",
                        params={"track_name": title, "artist_name": artist}
                    )
                    if res.status_code == 200:
                        results = res.json()
                        if isinstance(results, list) and len(results) > 0:
                            for item in results:
                                if item.get("syncedLyrics"):
                                    return item
                            for item in results:
                                if item.get("plainLyrics"):
                                    return item
                except Exception as e:
                    log.debug(f"LRCLIB structured search failed: {e}")

        return None

    async def _search_by_track_and_duration(
        self,
        title: str,
        duration: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Structured search using track_name, matching duration when available."""
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }

        async with httpx.AsyncClient(timeout=8.0, headers=headers) as client:
            try:
                res = await client.get(
                    f"{LRCLIB_BASE_URL}/search",
                    params={"track_name": title}
                )
                if res.status_code == 200:
                    results = res.json()
                    if isinstance(results, list) and len(results) > 0:
                        # If duration is known, find closest candidate
                        if duration and duration > 0:
                            best_match = None
                            best_diff = 999.0
                            for item in results:
                                item_dur = item.get("duration")
                                if item_dur:
                                    diff = abs(float(item_dur) - float(duration))
                                    if diff < best_diff and diff <= 4.0:
                                        best_diff = diff
                                        best_match = item
                            if best_match and (best_match.get("syncedLyrics") or best_match.get("plainLyrics")):
                                return best_match

                        # Otherwise return first synced result
                        for item in results:
                            if item.get("syncedLyrics"):
                                return item
                        for item in results:
                            if item.get("plainLyrics"):
                                return item
            except Exception as e:
                log.debug(f"Search by track name fallback failed: {e}")

        return None


# Global singleton instance
_lyrics_service = LyricsService()


def get_lyrics_service() -> LyricsService:
    return _lyrics_service
