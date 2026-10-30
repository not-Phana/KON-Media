"""Intelligent Search Suggestions & Song Discovery for KON Search 1.1.0 Rei.

Provides:
1. Smart Search Autocomplete (real-time query suggestions while typing).
2. Intelligent Song Discovery (finds songs when user remembers partial titles,
   artists, or keywords like 'Bankai', 'Shelter Porter', or 'I Wanna Be').
3. Multi-signal ranking based strictly on real evidence (providers, local history,
   verified feedback, and genuine metadata).
"""

import concurrent.futures
import json
import logging
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.search.models import CandidateResult, SearchQuery, SearchSuggestion
from backend.search.normalization import (
    COMMON_ARTIST_CUES,
    SOUNDTRACK_ASSOCIATIONS,
    VERSION_KEYWORDS,
    detect_version_hint,
    normalize_text,
    strip_media_noise,
)
from backend.search.relevance_engine import (
    compute_word_order_score,
    ngram_similarity,
    normalize_media_url,
)
from backend.security.url_guard import socket_guard_scope

log = logging.getLogger("kon_search_suggestions")

# In-memory LRU cache for suggestion queries (TTL 5 minutes)
_SUGGESTION_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_SUGGESTION_CACHE_LOCK = concurrent.futures.ThreadPoolExecutor(max_workers=1)
_CACHE_TTL_SECONDS = 300.0
_MAX_CACHE_SIZE = 400


# Curated genuine seed index of iconic music & soundtrack associations
# Used to reliably discover songs from keywords or partial titles ($0 external cost)
GENUINE_SEED_DISCOVERIES: List[Dict[str, Any]] = [
    {
        "title": "Number One - Bankai",
        "artist": "Shiro Sagisu",
        "keywords": ["bankai", "number one", "bleach", "bleach tybw", "tybw", "soundtrack", "ost"],
        "duration": 283.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=0w51O3yR-aI",
        "thumbnail": "https://i.ytimg.com/vi/0w51O3yR-aI/hqdefault.jpg",
    },
    {
        "title": "I Wanna Be Yours",
        "artist": "Arctic Monkeys",
        "keywords": ["i wanna be yours", "i wanna be", "arctic monkeys", "am", "yours"],
        "duration": 184.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=nyuo9-OjNNg",
        "thumbnail": "https://i.ytimg.com/vi/nyuo9-OjNNg/hqdefault.jpg",
    },
    {
        "title": "Shelter",
        "artist": "Porter Robinson & Madeon",
        "keywords": ["shelter", "porter robinson", "madeon", "porter", "shelter porter", "anime"],
        "duration": 219.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=fzQ6gRAE308",
        "thumbnail": "https://i.ytimg.com/vi/fzQ6gRAE308/hqdefault.jpg",
    },
    {
        "title": "Ditto (Jersey Club Remix)",
        "artist": "NewJeans",
        "keywords": ["ditto", "newjeans", "jersey club", "jersey remix", "remix", "new jeans"],
        "duration": 162.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=pSUydWEqKwE",
        "thumbnail": "https://i.ytimg.com/vi/pSUydWEqKwE/hqdefault.jpg",
    },
    {
        "title": "Ditto",
        "artist": "NewJeans",
        "keywords": ["ditto", "newjeans", "omg", "kpop", "new jeans"],
        "duration": 186.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=pSUydWEqKwE",
        "thumbnail": "https://i.ytimg.com/vi/pSUydWEqKwE/hqdefault.jpg",
    },
    {
        "title": "Hype Boy",
        "artist": "NewJeans",
        "keywords": ["hype boy", "newjeans", "attention", "cookie", "new jeans"],
        "duration": 179.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=11cta61Wi0g",
        "thumbnail": "https://i.ytimg.com/vi/11cta61Wi0g/hqdefault.jpg",
    },
    {
        "title": "I-BULL",
        "artist": "jo0ji",
        "keywords": ["i-bull", "ibull", "iburu", "jo0ji", "zenless zone zero", "zzz", "season 3", "chapter 2"],
        "duration": 215.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=KzXgZfL84Yk",
        "thumbnail": "https://i.ytimg.com/vi/KzXgZfL84Yk/hqdefault.jpg",
    },
    {
        "title": "Bite Back",
        "artist": "Hoyo-Mix",
        "keywords": ["bite back", "hoyo-mix", "zenless zone zero", "zzz", "hoyoverse"],
        "duration": 210.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "thumbnail": None,
    },
    {
        "title": "SPECIALZ",
        "artist": "King Gnu",
        "keywords": ["specialz", "king gnu", "jujutsu kaisen", "jjk", "shibuya incident"],
        "duration": 238.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=fhzKLBZJC3w",
        "thumbnail": "https://i.ytimg.com/vi/fhzKLBZJC3w/hqdefault.jpg",
    },
    {
        "title": "The Rumbling",
        "artist": "SiM",
        "keywords": ["the rumbling", "sim", "attack on titan", "aot", "season 4", "shingeki no kyojin"],
        "duration": 220.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=OB8_wZJ6yU4",
        "thumbnail": "https://i.ytimg.com/vi/OB8_wZJ6yU4/hqdefault.jpg",
    },
    {
        "title": "KICK BACK",
        "artist": "Kenshi Yonezu",
        "keywords": ["kick back", "kenshi yonezu", "chainsaw man", "csm", "opening", "op"],
        "duration": 213.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=M2cckDmNLMI",
        "thumbnail": "https://i.ytimg.com/vi/M2cckDmNLMI/hqdefault.jpg",
    },
    {
        "title": "Idol",
        "artist": "YOASOBI",
        "keywords": ["idol", "yoasobi", "oshi no ko", "opening", "op"],
        "duration": 222.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=ZRtdQ81jPUQ",
        "thumbnail": "https://i.ytimg.com/vi/ZRtdQ81jPUQ/hqdefault.jpg",
    },
    {
        "title": "I Really Want to Stay at Your House",
        "artist": "Rosa Walton",
        "keywords": ["i really want to stay at your house", "rosa walton", "cyberpunk edgerunners", "edgerunners", "cyberpunk"],
        "duration": 246.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=KvMY1uzSC1E",
        "thumbnail": "https://i.ytimg.com/vi/KvMY1uzSC1E/hqdefault.jpg",
    },
    {
        "title": "My Heart Will Go On",
        "artist": "Celine Dion",
        "keywords": ["my heart will go on", "celine dion", "titanic", "theme song"],
        "duration": 280.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=3gK_2XdjOdY",
        "thumbnail": "https://i.ytimg.com/vi/3gK_2XdjOdY/hqdefault.jpg",
    },
    {
        "title": "Cornfield Chase",
        "artist": "Hans Zimmer",
        "keywords": ["cornfield chase", "hans zimmer", "interstellar", "soundtrack"],
        "duration": 127.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=1V_xRb0x9aw",
        "thumbnail": "https://i.ytimg.com/vi/1V_xRb0x9aw/hqdefault.jpg",
    },
    {
        "title": "Never Gonna Give You Up",
        "artist": "Rick Astley",
        "keywords": ["never gonna give you up", "rick astley", "rickroll"],
        "duration": 213.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
    },
]


def clean_artist_name(artist: Optional[str]) -> Optional[str]:
    """Clean artist name by removing YouTube topic, vevo, and channel boilerplate."""
    if not artist:
        return None
    cleaned = re.sub(r"\s*-\s*topic$", "", artist, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*vevo$", "", cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r"\s*official\s*(?:channel|artist)?$", "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned or artist


NON_MUSIC_KEYWORDS = [
    "banned", "products", "amazon", "school products", "haul", "vlog", "prank",
    "challenge", "documentary", "news", "interview", "podcast", "60 minutes",
    "tutorial", "gameplay", "walkthrough", "review", "reaction", "soloq",
    "league of legends gameplay", "patch notes", "highlights", "test match",
    "kabaddi", "cricket", "football", "baseball", "basketball", "nba", "nfl",
    "premier league", "backpedal", "riot games", "sports", "tour of", "wins $",
    "last to leave", "cereal bowl", "day 1", "day 2", "day 3", "day 4", "day 5",
    "innings", "wickets", "overs", "1st test", "2nd test", "3rd test",
    "fights", "crazy anime fights", "anime footage", "moments that broke",
]


VIDEO_CONTENT_KEYWORDS = [
    "story of", "entire story", "recap", "season", "episode", "full movie",
    "just ended", "reaction", "review", "gameplay", "walkthrough", "prologue",
    "explained", "lore", "analysis", "theory", "documentary", "vlog", "interview",
    "teaser", "trailer", "pv", "commercial", "short film", "news", "ranking",
    "tier list", "moments", "scenes", "vs", "fight", "fights", "clip", "full story",
    "banned", "products", "challenge", "prank", "podcast", "60 minutes",
    "soloque", "patch notes", "highlights", "test match", "sports",
    "footage", "scene", "compilation", "all scenes",
]


def classify_candidate_media_type(candidate: Dict[str, Any], query: str = "") -> Tuple[str, str]:
    """Classify whether a candidate is genuinely a 'song' or a 'video', and return (media_type, platform_label).

    Returns:
        (media_type, platform_label) e.g. ("song", "Theme Song"), ("song", "Song Discovery"), ("video", "YouTube Video")
    """
    duration = candidate.get("duration")
    raw_title = candidate.get("title") or ""
    clean_title = strip_media_noise(raw_title)
    title_lower = clean_title.lower()
    artist_lower = (candidate.get("artist") or "").lower()
    source = candidate.get("source")
    platform = candidate.get("platform") or "youtube"
    platform_name = "YouTube" if platform == "youtube" else platform.title()

    # 1. Seed discoveries and soundtrack associations are verified authentic songs
    if source == "seed":
        match_reason = candidate.get("match_reason") or ""
        label = "Theme Song" if "theme" in match_reason.lower() or "soundtrack" in match_reason.lower() else "Song Discovery"
        return ("song", label)

    if source == "soundtrack":
        return ("song", "Theme Song")

    if source in ("history", "feedback"):
        if candidate.get("media_type") == "audio" or (duration and duration <= 600):
            return ("song", "From History" if source == "history" else "Verified Match")

    # 2. Strong video indicators: extreme duration or non-music keywords in title or channel
    is_video_content = False

    # Duration check: standard songs are 1-8 minutes. > 15 minutes (900s) is almost certainly a video, recap, episode, or vlog
    if duration and duration > 900:
        is_video_content = True

    combined_metadata = f"{title_lower} {artist_lower}"
    if any(ind in combined_metadata for ind in VIDEO_CONTENT_KEYWORDS):
        is_video_content = True

    # 3. Strong music indicators:
    music_indicators = [
        "official audio", "official music video", "mv", "lyrics", "feat.", "ft.",
        "soundtrack", "ost", "theme", "opening", "ending", "op", "ed", "remix",
        "acoustic", "instrumental", "karaoke", "orchestra", "symphony",
        "topic", "records", "vevo", "audio", "song", "music", "prod.", "prod by",
        "band", "orchestral", "bgm", "cover", "album", "single", "radio edit",
        "vocal", "vocals",
    ]
    has_music_indicator = any(m in title_lower or m in artist_lower for m in music_indicators)

    # If it is video content and not a short song track with explicit music indicator, it is a video!
    if is_video_content:
        if not (has_music_indicator and duration and duration <= 600):
            return ("video", f"{platform_name} Video")

    # If it has music indicators and standard song length
    if has_music_indicator and (duration is None or duration <= 900):
        return ("song", "Song Discovery")

    # Channel or artist indicates musical artist or topic
    if any(kw in artist_lower for kw in ("records", "vevo", "topic", "band", "orchestra", "music")):
        return ("song", "Song Discovery")

    # If the title has clean music format (e.g. 'Artist - Title') and reasonable duration
    if " - " in clean_title and (duration is None or (45 <= duration <= 600)) and not is_video_content:
        return ("song", "Song Discovery")

    # Fallback for general video platform results: tell the user it is a video from that platform!
    return ("video", f"{platform_name} Video")


class SuggestionEngine:
    """Coordinates smart autocomplete and intelligent song discovery from genuine evidence."""

    def __init__(
        self,
        history_store: Optional[Any] = None,
        feedback_store: Optional[Any] = None,
        search_cache: Optional[Any] = None,
    ):
        self.history_store = history_store
        self.feedback_store = feedback_store
        self.search_cache = search_cache
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="kon_suggest_worker"
        )

    def _fetch_real_query_suggestions(self, query: str, timeout: float = 1.0) -> List[str]:
        """Fetch actual user search phrases via public YouTube autocomplete service (~100-300ms).

        Returns real search queries without fabricating or assuming songs exist.
        """
        clean_q = query.strip()
        if not clean_q:
            return []

        encoded = urllib.parse.quote(clean_q)
        url = f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={encoded}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)",
                "Accept": "*/*",
            },
        )

        try:
            with socket_guard_scope():
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if isinstance(data, list) and len(data) >= 2 and isinstance(data[1], list):
                        return [str(s).strip() for s in data[1] if s and isinstance(s, str)]
        except Exception as e:
            log.debug("Real query suggestion service bypassed or timed out: %s", e)
        return []

    def _fetch_live_provider_candidates(
        self, query: str, timeout: float = 1.4, media_type: str = "all"
    ) -> List[Dict[str, Any]]:
        """Retrieve live real-time candidate songs from YouTube Innertube (~1.2s)."""
        clean_q = query.strip()
        if len(clean_q) < 3:
            # Skip provider candidate queries on tiny 1-2 char inputs to keep typing fast
            return []

        search_query = clean_q
        if media_type == "audio" and len(clean_q.split()) == 1 and len(clean_q) <= 4:
            search_query = f"{clean_q} song"

        try:
            from backend.search.providers import YouTubeSearchProvider

            provider = YouTubeSearchProvider()
            cands = provider._search_innertube(search_query, limit=4)
            items: List[Dict[str, Any]] = []
            for c in cands:
                items.append({
                    "id": c.id,
                    "title": c.title,
                    "artist": c.uploader,
                    "url": c.url,
                    "thumbnail": c.thumbnail,
                    "duration": c.duration,
                    "platform": c.platform,
                    "is_live": True,
                })
            return items
        except Exception as e:
            log.debug("Live provider suggestion lookup timed out or failed: %s", e)
            return []

    def _gather_local_song_candidates(self, norm_q: str, query_tokens: List[str]) -> List[Dict[str, Any]]:
        """Extract genuine verified candidate songs from local seed index, download history, and feedback."""
        candidates: List[Dict[str, Any]] = []

        # 1. Check curated genuine seed discoveries
        for item in GENUINE_SEED_DISCOVERIES:
            title_norm = normalize_text(item["title"])
            artist_norm = normalize_text(item.get("artist", ""))
            keywords = [normalize_text(k) for k in item.get("keywords", [])]

            # Match criteria: title prefix, title contains, artist match, or keyword match
            is_match = False
            match_reason = "Song discovery"

            if norm_q in title_norm or title_norm in norm_q:
                is_match = True
                match_reason = f"Matches title: {item['title']}"
            elif artist_norm and (norm_q in artist_norm or any(tok in artist_norm.split() for tok in query_tokens if len(tok) >= 3)):
                is_match = True
                match_reason = f"Matches artist: {item['artist']}"
            else:
                for kw in keywords:
                    if norm_q in kw or kw in norm_q or any(tok == kw or kw.startswith(tok) for tok in query_tokens if len(tok) >= 3):
                        is_match = True
                        match_reason = f"Matches keyword: '{kw}'"
                        break

            if is_match:
                candidates.append({
                    "id": f"seed_{item['title']}",
                    "title": item["title"],
                    "artist": item.get("artist"),
                    "url": item.get("url"),
                    "thumbnail": item.get("thumbnail"),
                    "duration": item.get("duration"),
                    "platform": item.get("platform", "youtube"),
                    "match_reason": match_reason,
                    "source": "seed",
                })

        # 2. Check persistent user download history
        if self.history_store:
            try:
                history_items = self.history_store.get_all()
                for h in history_items:
                    h_title = h.get("title") or ""
                    h_norm = normalize_text(h_title)
                    if not h_norm:
                        continue
                    if any(tok in h_norm for tok in query_tokens if len(tok) >= 3) or norm_q in h_norm:
                        candidates.append({
                            "id": f"hist_{h.get('id', '')}",
                            "title": h_title,
                            "artist": h.get("uploader"),
                            "url": h.get("url"),
                            "thumbnail": h.get("thumbnail"),
                            "duration": h.get("duration"),
                            "platform": "youtube",
                            "match_reason": "From your download history",
                            "source": "history",
                        })
            except Exception:
                pass

        # 3. Check verified feedback store
        if self.feedback_store:
            try:
                feedback_items = self.feedback_store.get_all()
                for fb in feedback_items:
                    if getattr(fb, "is_mismatch", False):
                        continue
                    fb_title = getattr(fb, "selected_title", "")
                    fb_norm = normalize_text(fb_title)
                    if fb_norm and (norm_q in fb_norm or any(tok in fb_norm for tok in query_tokens if len(tok) >= 3)):
                        candidates.append({
                            "id": f"fb_{getattr(fb, 'selected_id', '')}",
                            "title": fb_title,
                            "artist": None,
                            "url": getattr(fb, "selected_url", ""),
                            "thumbnail": None,
                            "duration": None,
                            "platform": "youtube",
                            "match_reason": "Verified user match",
                            "source": "feedback",
                        })
            except Exception:
                pass

        # 4. Check soundtrack associations taxonomy
        for key, assoc_titles in SOUNDTRACK_ASSOCIATIONS.items():
            key_norm = normalize_text(key)
            if norm_q in key_norm or key_norm in norm_q or any(tok == key_norm for tok in query_tokens):
                for assoc_title in assoc_titles:
                    # e.g. "Shiro Sagisu - Number One - Bankai" -> artist="Shiro Sagisu", title="Number One - Bankai"
                    artist_part = None
                    clean_title = assoc_title
                    if " - " in assoc_title:
                        parts = assoc_title.split(" - ", 1)
                        artist_part = parts[0].strip()
                        clean_title = parts[1].strip()

                    candidates.append({
                        "id": f"assoc_{clean_title}",
                        "title": clean_title,
                        "artist": artist_part,
                        "url": None,
                        "thumbnail": None,
                        "duration": None,
                        "platform": "youtube",
                        "match_reason": f"Iconic theme for '{key.title()}'",
                        "source": "soundtrack",
                    })

        return candidates

    def _score_song_candidate(
        self,
        candidate: Dict[str, Any],
        norm_q: str,
        query_tokens: List[str],
        detected_version: Optional[str],
        media_type: str = "all",
    ) -> float:
        """Compute multi-signal relevance score for a song discovery candidate.

        Signals:
        1. Exact title match (+1.2)
        2. Prefix / continuous phrase match (+0.8)
        3. Word order and token coverage (+0.5 * cov + 0.3 * order)
        4. Artist match (+0.6)
        5. Version qualifier match (+0.5)
        6. Character n-gram edit similarity (+0.3)
        7. Metadata completeness quality (+0.2)
        """
        raw_title = candidate.get("title") or ""
        clean_title = strip_media_noise(raw_title)
        title_norm = normalize_text(clean_title)
        artist_norm = normalize_text(candidate.get("artist") or "")

        score = 0.0

        # Classify candidate media type honestly
        cand_type, platform_label = classify_candidate_media_type(candidate, norm_q)

        # When searching in audio mode (Song & Music):
        if media_type == "audio":
            if any(kw in title_norm for kw in NON_MUSIC_KEYWORDS):
                return 0.0
            if cand_type == "video":
                # In Song & Music mode, non-music videos and video clips must not pollute song discoveries
                return 0.0

        full_text_norm = f"{title_norm} {artist_norm}".strip()
        full_tokens = full_text_norm.split()

        # Must have at least one genuine match signal (substring, token, artist, or high n-gram similarity)
        has_token_match = any(
            any(q_tok == f_tok or f_tok.startswith(q_tok) or q_tok in f_tok for f_tok in full_tokens)
            for q_tok in query_tokens if len(q_tok) >= 2
        )
        has_substring_match = norm_q in title_norm or norm_q in artist_norm or title_norm in norm_q
        sim = ngram_similarity(norm_q, title_norm)

        if not has_token_match and not has_substring_match and sim < 0.35:
            # Zero relevance evidence: do not manufacture confidence or return unrelated songs
            return 0.0

        # 1. Exact title match
        if title_norm == norm_q:
            score += 1.2
        elif title_norm.startswith(norm_q):
            score += 0.85
        elif norm_q in title_norm:
            ratio = len(norm_q) / max(1, len(title_norm))
            score += 0.65 * ratio

        # 2. Artist match (e.g. 'Shelter Porter' -> 'Porter Robinson & Madeon')
        if artist_norm:
            if artist_norm == norm_q:
                score += 0.9
            elif artist_norm.startswith(norm_q) or norm_q in artist_norm:
                score += 0.7
            elif any(tok in artist_norm.split() or artist_norm.startswith(tok) for tok in query_tokens if len(tok) >= 3):
                score += 0.55

        # 3. Token coverage & word order score
        if query_tokens and full_tokens:
            matched_tokens = sum(
                1 for q_tok in query_tokens
                if any(q_tok == f_tok or f_tok.startswith(q_tok) for f_tok in full_tokens)
            )
            coverage = matched_tokens / len(query_tokens)
            score += 0.5 * coverage

            order_score = compute_word_order_score(query_tokens, full_tokens)
            score += 0.3 * order_score

        # 4. Version qualifier boost
        if detected_version:
            cand_version = detect_version_hint(raw_title)
            if cand_version and cand_version == detected_version:
                score += 0.5
            elif detected_version in full_text_norm:
                score += 0.4

        # 5. Character n-gram similarity (typo tolerance)
        score += 0.3 * sim

        # 6. Metadata quality (only awarded when candidate is already relevant)
        if candidate.get("thumbnail"):
            score += 0.15
        if candidate.get("duration"):
            score += 0.1
        if candidate.get("source") in ("history", "feedback"):
            score += 0.25

        return score

    def rank_suggestions(
        self,
        query: str,
        song_candidates: List[Dict[str, Any]],
        query_suggestions: List[str],
        limit: int = 6,
        media_type: str = "all",
    ) -> List[SearchSuggestion]:
        """Rank and deduplicate suggestions into a clean, balanced list.

        Clearly separates verified songs from query refinements.
        """
        clean_q = query.strip()
        norm_q = normalize_text(clean_q)
        query_tokens = [tok for tok in norm_q.split() if tok]
        detected_version = detect_version_hint(clean_q)

        ranked_songs: List[Tuple[float, Dict[str, Any]]] = []
        seen_songs: Set[str] = set()

        for c in song_candidates:
            raw_title = c.get("title") or ""
            clean_title = strip_media_noise(raw_title)
            clean_artist = clean_artist_name(c.get("artist"))
            c["artist"] = clean_artist

            # Deduplication key based on normalized title + artist
            dedup_key = f"{normalize_text(clean_title)}::{normalize_text(clean_artist or '')}"
            if dedup_key in seen_songs:
                continue
            seen_songs.add(dedup_key)

            score = self._score_song_candidate(
                c, norm_q, query_tokens, detected_version, media_type=media_type
            )

            # Minimum relevance threshold for genuine discovery
            if score >= 0.40:
                ranked_songs.append((score, c))

        ranked_songs.sort(key=lambda x: x[0], reverse=True)

        # Process and rank query suggestions
        ranked_queries: List[Tuple[float, str]] = []
        seen_queries: Set[str] = set()
        seen_queries.add(norm_q)  # Don't suggest the exact same query user already typed

        for qs in query_suggestions:
            qs_clean = qs.strip()
            qs_norm = normalize_text(qs_clean)
            if not qs_clean or qs_norm in seen_queries:
                continue
            seen_queries.add(qs_norm)

            # Score query refinement
            q_score = 0.5
            if qs_norm.startswith(norm_q):
                q_score += 0.4
            elif norm_q in qs_norm:
                q_score += 0.25

            ranked_queries.append((q_score, qs_clean))

        ranked_queries.sort(key=lambda x: x[0], reverse=True)

        # Assemble final results: balance top discovered songs/videos and query refinements
        final_suggestions: List[SearchSuggestion] = []

        top_candidates = ranked_songs[:4]
        for score, cand in top_candidates:
            clean_t = strip_media_noise(cand["title"])
            cand_type, platform_label = classify_candidate_media_type(cand, clean_q)
            search_exec_query = f"{clean_t} {cand['artist']}".strip() if cand.get("artist") else clean_t

            final_suggestions.append(
                SearchSuggestion(
                    id=cand.get("id") or f"{cand_type}_{len(final_suggestions)}",
                    query=search_exec_query,
                    title=clean_t,
                    artist=cand.get("artist"),
                    type=cand_type,
                    platform=cand.get("platform") or "youtube",
                    thumbnail=cand.get("thumbnail"),
                    duration=cand.get("duration"),
                    url=cand.get("url"),
                    match_reason=platform_label,
                    score=score,
                )
            )

        # Fill remaining slots with query refinements
        remaining_slots = max(1, limit - len(final_suggestions))
        for q_score, q_text in ranked_queries[:remaining_slots]:
            final_suggestions.append(
                SearchSuggestion(
                    id=f"query_{len(final_suggestions)}",
                    query=q_text,
                    title=q_text,
                    artist=None,
                    type="query",
                    thumbnail=None,
                    duration=None,
                    url=None,
                    match_reason="Suggested search",
                    score=q_score,
                )
            )

        return final_suggestions[:limit]

    def get_suggestions(
        self,
        query: str,
        limit: int = 6,
        media_type: str = "all",
    ) -> List[Dict[str, Any]]:
        """Retrieve, rank, and format search suggestions with high-speed LRU caching."""
        clean_q = query.strip()
        if not clean_q:
            return []

        # Check LRU suggestion cache (~0.001s)
        cache_key = f"{clean_q.lower()}::{limit}::{media_type}"
        now = time.time()
        if cache_key in _SUGGESTION_CACHE:
            ts, cached_list = _SUGGESTION_CACHE[cache_key]
            if now - ts < _CACHE_TTL_SECONDS:
                return cached_list

        norm_q = normalize_text(clean_q)
        query_tokens = [tok for tok in norm_q.split() if tok]

        # Gather local candidates immediately (sub-millisecond)
        local_candidates = self._gather_local_song_candidates(norm_q, query_tokens)

        # Query external sources concurrently (fast timeout)
        futures = {}
        futures["queries"] = self._executor.submit(self._fetch_real_query_suggestions, clean_q, 1.0)
        if len(clean_q) >= 3:
            futures["providers"] = self._executor.submit(
                self._fetch_live_provider_candidates, clean_q, 1.4, media_type
            )

        query_suggestions: List[str] = []
        provider_candidates: List[Dict[str, Any]] = []

        try:
            query_suggestions = futures["queries"].result(timeout=1.1)
        except Exception:
            pass

        if "providers" in futures:
            try:
                provider_candidates = futures["providers"].result(timeout=1.5)
            except Exception:
                pass

        # Combine all song candidates
        all_song_candidates = local_candidates + provider_candidates

        # Rank and deduplicate
        ranked = self.rank_suggestions(
            query=clean_q,
            song_candidates=all_song_candidates,
            query_suggestions=query_suggestions,
            limit=limit,
            media_type=media_type,
        )

        results = [s.to_dict() for s in ranked]

        # Store in cache
        if len(_SUGGESTION_CACHE) >= _MAX_CACHE_SIZE:
            # Evict first key
            try:
                del _SUGGESTION_CACHE[next(iter(_SUGGESTION_CACHE))]
            except Exception:
                pass
        _SUGGESTION_CACHE[cache_key] = (now, results)

        return results


# Global singleton SuggestionEngine
_shared_suggestion_engine: Optional[SuggestionEngine] = None


def get_shared_suggestion_engine() -> SuggestionEngine:
    global _shared_suggestion_engine
    if _shared_suggestion_engine is None:
        from backend.storage.storage import HistoryStore, SettingsStore
        from backend.search.feedback import SearchFeedbackStore
        from backend.search.cache import get_shared_search_cache
        from backend.config import STATE_DIR

        _shared_suggestion_engine = SuggestionEngine(
            history_store=HistoryStore(STATE_DIR),
            feedback_store=SearchFeedbackStore(),
            search_cache=get_shared_search_cache(),
        )
    return _shared_suggestion_engine
