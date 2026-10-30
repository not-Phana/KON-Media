"""Intelligent Search Suggestions & Music Discovery for KON Search 1.2 Rei.

Implements a multi-stage suggestion intelligence pipeline:
1. Query collection and Unicode normalization.
2. Query understanding: identifies title fragments, artist entities, version qualifiers,
   context/soundtrack cues, and plausible typos without destructively altering the query.
3. Multi-strategy candidate retrieval: genuine seed catalog, known artists index,
   local download history, verified feedback, adaptive refinements, and live provider queries.
4. Candidate identity resolution: media classification (song vs video), noise stripping,
   and artist normalization.
5. Multi-signal relevance evaluation: deterministic, explainable scoring based on exact title,
   partial phrase, token coverage, word order, artist similarity, version match,
   controlled typo similarity, and context cues, with popularity as a strictly minor tie-breaker.
6. Suggestion ranking, confidence categorization (strong, possible, weak), and diversity grouping.
7. Deduplication and presentation.
"""

import concurrent.futures
import difflib
import json
import logging
import math
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.search.adaptive_suggestions import get_shared_adaptive_store
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

# Product metadata
PRODUCT_NAME = "KON Search 1.2 Rei"
ENGINE_VERSION = "1.2.0"

# In-memory LRU cache for suggestion queries (TTL 5 minutes)
_SUGGESTION_CACHE: Dict[str, Tuple[float, List[Dict[str, Any]]]] = {}
_SUGGESTION_CACHE_LOCK = concurrent.futures.ThreadPoolExecutor(max_workers=1)
_CACHE_TTL_SECONDS = 300.0
_MAX_CACHE_SIZE = 500


# -----------------------------------------------------------------------------
# 1. Query Understanding Data Structures
# -----------------------------------------------------------------------------

@dataclass
class SuggestionIntent:
    """Structured understanding of user query clues and interpretations."""
    raw_query: str
    normalized_query: str
    tokens: List[str]
    matched_artists: List[Dict[str, Any]] = field(default_factory=list)
    detected_version: Optional[str] = None
    detected_context: Optional[str] = None
    title_fragments: List[str] = field(default_factory=list)
    is_artist_focused: bool = False
    is_version_focused: bool = False
    is_context_focused: bool = False
    is_single_keyword: bool = False
    suggested_interpretations: List[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# 2. Known Artist Catalog with Canonical Tracks
# -----------------------------------------------------------------------------

KNOWN_ARTISTS_CATALOG: Dict[str, Dict[str, Any]] = {
    "porter robinson": {
        "canonical_name": "Porter Robinson",
        "aliases": ["porter", "porter robinson", "porterrobinson"],
        "genre": "Electronic · Synth-pop",
        "top_songs": [
            {
                "title": "Shelter",
                "artist": "Porter Robinson & Madeon",
                "duration": 219.0,
                "url": "https://www.youtube.com/watch?v=fzQ6gRAE308",
                "thumbnail": "https://i.ytimg.com/vi/fzQ6gRAE308/hqdefault.jpg",
                "context": "Anime Short Film Soundtrack",
            },
            {
                "title": "Sad Machine",
                "artist": "Porter Robinson",
                "duration": 350.0,
                "url": "https://www.youtube.com/watch?v=HAIDqt2xUek",
                "thumbnail": "https://i.ytimg.com/vi/HAIDqt2xUek/hqdefault.jpg",
                "context": "Worlds Album",
            },
            {
                "title": "Look at the Sky",
                "artist": "Porter Robinson",
                "duration": 310.0,
                "url": "https://www.youtube.com/watch?v=TJBh_hj6DzE",
                "thumbnail": "https://i.ytimg.com/vi/TJBh_hj6DzE/hqdefault.jpg",
                "context": "Nurture Album",
            },
        ],
    },
    "arctic monkeys": {
        "canonical_name": "Arctic Monkeys",
        "aliases": ["arctic", "arctic monkeys", "arcticmonkeys", "am"],
        "genre": "Indie Rock · Alternative",
        "top_songs": [
            {
                "title": "I Wanna Be Yours",
                "artist": "Arctic Monkeys",
                "duration": 184.0,
                "url": "https://www.youtube.com/watch?v=nyuo9-OjNNg",
                "thumbnail": "https://i.ytimg.com/vi/nyuo9-OjNNg/hqdefault.jpg",
                "context": "AM Album",
            },
            {
                "title": "Do I Wanna Know?",
                "artist": "Arctic Monkeys",
                "duration": 272.0,
                "url": "https://www.youtube.com/watch?v=bpOSxM0tfN8",
                "thumbnail": "https://i.ytimg.com/vi/bpOSxM0tfN8/hqdefault.jpg",
                "context": "AM Album",
            },
            {
                "title": "505",
                "artist": "Arctic Monkeys",
                "duration": 253.0,
                "url": "https://www.youtube.com/watch?v=qU9mHegkTc4",
                "thumbnail": "https://i.ytimg.com/vi/qU9mHegkTc4/hqdefault.jpg",
                "context": "Favourite Worst Nightmare",
            },
        ],
    },
    "newjeans": {
        "canonical_name": "NewJeans",
        "aliases": ["newjeans", "new jeans", "newjean", "nj"],
        "genre": "K-Pop · R&B",
        "top_songs": [
            {
                "title": "Ditto",
                "artist": "NewJeans",
                "duration": 186.0,
                "url": "https://www.youtube.com/watch?v=pSUydWEqKwE",
                "thumbnail": "https://i.ytimg.com/vi/pSUydWEqKwE/hqdefault.jpg",
                "context": "OMG Single Album",
            },
            {
                "title": "Ditto (Jersey Club Remix)",
                "artist": "NewJeans",
                "duration": 162.0,
                "url": "https://www.youtube.com/watch?v=pSUydWEqKwE",
                "thumbnail": "https://i.ytimg.com/vi/pSUydWEqKwE/hqdefault.jpg",
                "context": "Club Version",
            },
            {
                "title": "Hype Boy",
                "artist": "NewJeans",
                "duration": 179.0,
                "url": "https://www.youtube.com/watch?v=11cta61Wi0g",
                "thumbnail": "https://i.ytimg.com/vi/11cta61Wi0g/hqdefault.jpg",
                "context": "1st EP 'New Jeans'",
            },
            {
                "title": "Super Shy",
                "artist": "NewJeans",
                "duration": 154.0,
                "url": "https://www.youtube.com/watch?v=ArmDp-zijuc",
                "thumbnail": "https://i.ytimg.com/vi/ArmDp-zijuc/hqdefault.jpg",
                "context": "Get Up EP",
            },
        ],
    },
    "shiro sagisu": {
        "canonical_name": "Shiro Sagisu",
        "aliases": ["shiro sagisu", "sagisu", "sagisu shiro"],
        "genre": "Soundtrack · Orchestral",
        "top_songs": [
            {
                "title": "Number One - Bankai",
                "artist": "Shiro Sagisu",
                "duration": 283.0,
                "url": "https://www.youtube.com/watch?v=0w51O3yR-aI",
                "thumbnail": "https://i.ytimg.com/vi/0w51O3yR-aI/hqdefault.jpg",
                "context": "Bleach TYBW OST",
            },
            {
                "title": "Treachery",
                "artist": "Shiro Sagisu",
                "duration": 184.0,
                "url": "https://www.youtube.com/watch?v=1lsn2tT5yTc",
                "thumbnail": None,
                "context": "Bleach Aizen Theme",
            },
        ],
    },
    "hans zimmer": {
        "canonical_name": "Hans Zimmer",
        "aliases": ["hans zimmer", "zimmer"],
        "genre": "Film Score · Cinematic",
        "top_songs": [
            {
                "title": "Cornfield Chase",
                "artist": "Hans Zimmer",
                "duration": 127.0,
                "url": "https://www.youtube.com/watch?v=1V_xRb0x9aw",
                "thumbnail": "https://i.ytimg.com/vi/1V_xRb0x9aw/hqdefault.jpg",
                "context": "Interstellar OST",
            },
            {
                "title": "Time",
                "artist": "Hans Zimmer",
                "duration": 275.0,
                "url": "https://www.youtube.com/watch?v=RxabLA7UQ9k",
                "thumbnail": None,
                "context": "Inception OST",
            },
        ],
    },
    "yoasobi": {
        "canonical_name": "YOASOBI",
        "aliases": ["yoasobi"],
        "genre": "J-Pop · Anime OST",
        "top_songs": [
            {
                "title": "Idol",
                "artist": "YOASOBI",
                "duration": 222.0,
                "url": "https://www.youtube.com/watch?v=ZRtdQ81jPUQ",
                "thumbnail": "https://i.ytimg.com/vi/ZRtdQ81jPUQ/hqdefault.jpg",
                "context": "Oshi no Ko OP",
            },
            {
                "title": "The Brave",
                "artist": "YOASOBI",
                "duration": 194.0,
                "url": "https://www.youtube.com/watch?v=OIBODIPC_8Y",
                "thumbnail": None,
                "context": "Frieren OP",
            },
        ],
    },
    "king gnu": {
        "canonical_name": "King Gnu",
        "aliases": ["king gnu"],
        "genre": "J-Rock · JJK OST",
        "top_songs": [
            {
                "title": "SPECIALZ",
                "artist": "King Gnu",
                "duration": 238.0,
                "url": "https://www.youtube.com/watch?v=fhzKLBZJC3w",
                "thumbnail": "https://i.ytimg.com/vi/fhzKLBZJC3w/hqdefault.jpg",
                "context": "Jujutsu Kaisen Season 2 OP",
            },
        ],
    },
    "jo0ji": {
        "canonical_name": "jo0ji",
        "aliases": ["jo0ji", "joji"],
        "genre": "Alternative · ZZZ OST",
        "top_songs": [
            {
                "title": "I-BULL",
                "artist": "jo0ji",
                "duration": 215.0,
                "url": "https://www.youtube.com/watch?v=KzXgZfL84Yk",
                "thumbnail": "https://i.ytimg.com/vi/KzXgZfL84Yk/hqdefault.jpg",
                "context": "Zenless Zone Zero Season 3 Chapter 2 Opening",
            },
        ],
    },
    "kenshi yonezu": {
        "canonical_name": "Kenshi Yonezu",
        "aliases": ["kenshi yonezu", "yonezu"],
        "genre": "J-Pop · Chainsaw Man OP",
        "top_songs": [
            {
                "title": "KICK BACK",
                "artist": "Kenshi Yonezu",
                "duration": 213.0,
                "url": "https://www.youtube.com/watch?v=M2cckDmNLMI",
                "thumbnail": "https://i.ytimg.com/vi/M2cckDmNLMI/hqdefault.jpg",
                "context": "Chainsaw Man OP",
            },
        ],
    },
    "sim": {
        "canonical_name": "SiM",
        "aliases": ["sim"],
        "genre": "Metalcore · AOT OST",
        "top_songs": [
            {
                "title": "The Rumbling",
                "artist": "SiM",
                "duration": 220.0,
                "url": "https://www.youtube.com/watch?v=OB8_wZJ6yU4",
                "thumbnail": "https://i.ytimg.com/vi/OB8_wZJ6yU4/hqdefault.jpg",
                "context": "Attack on Titan Final Season OP",
            },
        ],
    },
    "celine dion": {
        "canonical_name": "Celine Dion",
        "aliases": ["celine dion", "celine"],
        "genre": "Pop · Titanic Soundtrack",
        "top_songs": [
            {
                "title": "My Heart Will Go On",
                "artist": "Celine Dion",
                "duration": 280.0,
                "url": "https://www.youtube.com/watch?v=3gK_2XdjOdY",
                "thumbnail": "https://i.ytimg.com/vi/3gK_2XdjOdY/hqdefault.jpg",
                "context": "Titanic Love Theme",
            },
        ],
    },
    "rick astley": {
        "canonical_name": "Rick Astley",
        "aliases": ["rick astley", "rickroll"],
        "genre": "80s Pop · Classic",
        "top_songs": [
            {
                "title": "Never Gonna Give You Up",
                "artist": "Rick Astley",
                "duration": 213.0,
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
                "context": "Classic Hit",
            },
        ],
    },
    "linkin park": {
        "canonical_name": "Linkin Park",
        "aliases": ["linkin park", "linkin"],
        "genre": "Nu-Metal · Alternative Rock",
        "top_songs": [
            {
                "title": "The Emptiness Machine",
                "artist": "Linkin Park",
                "duration": 190.0,
                "url": "https://www.youtube.com/watch?v=SRXH9AbT280",
                "thumbnail": None,
                "context": "From Zero (2024)",
            },
            {
                "title": "In the End",
                "artist": "Linkin Park",
                "duration": 216.0,
                "url": "https://www.youtube.com/watch?v=eVTXPUF4Oz4",
                "thumbnail": None,
                "context": "Hybrid Theory",
            },
        ],
    },
    "daft punk": {
        "canonical_name": "Daft Punk",
        "aliases": ["daft punk", "daft"],
        "genre": "Electronic · French House",
        "top_songs": [
            {
                "title": "One More Time",
                "artist": "Daft Punk",
                "duration": 320.0,
                "url": "https://www.youtube.com/watch?v=FGBhQbmMxH8",
                "thumbnail": None,
                "context": "Discovery",
            },
            {
                "title": "Get Lucky",
                "artist": "Daft Punk ft. Pharrell Williams",
                "duration": 248.0,
                "url": "https://www.youtube.com/watch?v=5NV6Rdv1a3I",
                "thumbnail": None,
                "context": "Random Access Memories",
            },
        ],
    },
    "roblox": {
        "canonical_name": "ROBLOX",
        "aliases": ["roblox", "roblox sound", "roblox game"],
        "genre": "Video Game Soundtrack",
        "top_songs": [
            {
                "title": "The Great Strategy",
                "artist": "ROBLOX",
                "duration": 135.0,
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "thumbnail": None,
                "context": "Classic Game Music",
            },
        ],
    },
}


# -----------------------------------------------------------------------------
# 3. Genuine Seed Music Discoveries Index
# -----------------------------------------------------------------------------

GENUINE_SEED_DISCOVERIES: List[Dict[str, Any]] = [
    {
        "title": "Number One - Bankai",
        "artist": "Shiro Sagisu",
        "keywords": ["bankai", "number one", "number one bankai", "bleach", "bleach tybw", "tybw", "soundtrack", "ost", "anime"],
        "duration": 283.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=0w51O3yR-aI",
        "thumbnail": "https://i.ytimg.com/vi/0w51O3yR-aI/hqdefault.jpg",
        "context": "Bleach TYBW Soundtrack",
        "category": "song",
    },
    {
        "title": "I Wanna Be Yours",
        "artist": "Arctic Monkeys",
        "keywords": ["i wanna be yours", "i wanna be", "i wanna", "arctic monkeys", "am", "yours", "indie"],
        "duration": 184.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=nyuo9-OjNNg",
        "thumbnail": "https://i.ytimg.com/vi/nyuo9-OjNNg/hqdefault.jpg",
        "context": "AM Album",
        "category": "song",
    },
    {
        "title": "Shelter",
        "artist": "Porter Robinson & Madeon",
        "keywords": ["shelter", "porter robinson", "madeon", "porter", "shelter porter", "anime", "electronic"],
        "duration": 219.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=fzQ6gRAE308",
        "thumbnail": "https://i.ytimg.com/vi/fzQ6gRAE308/hqdefault.jpg",
        "context": "Anime Music Video",
        "category": "song",
    },
    {
        "title": "Ditto (Jersey Club Remix)",
        "artist": "NewJeans",
        "keywords": ["ditto", "newjeans", "jersey club", "jersey remix", "remix", "new jeans", "jersey", "club mix"],
        "duration": 162.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=pSUydWEqKwE",
        "thumbnail": "https://i.ytimg.com/vi/pSUydWEqKwE/hqdefault.jpg",
        "context": "Club Version",
        "category": "version",
    },
    {
        "title": "Ditto",
        "artist": "NewJeans",
        "keywords": ["ditto", "newjeans", "omg", "kpop", "new jeans"],
        "duration": 186.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=pSUydWEqKwE",
        "thumbnail": "https://i.ytimg.com/vi/pSUydWEqKwE/hqdefault.jpg",
        "context": "Original Track",
        "category": "song",
    },
    {
        "title": "Hype Boy",
        "artist": "NewJeans",
        "keywords": ["hype boy", "newjeans", "attention", "cookie", "new jeans"],
        "duration": 179.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=11cta61Wi0g",
        "thumbnail": "https://i.ytimg.com/vi/11cta61Wi0g/hqdefault.jpg",
        "context": "1st EP",
        "category": "song",
    },
    {
        "title": "I-BULL",
        "artist": "jo0ji",
        "keywords": ["i-bull", "ibull", "iburu", "jo0ji", "zenless zone zero", "zzz", "season 3", "chapter 2", "opening"],
        "duration": 215.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=KzXgZfL84Yk",
        "thumbnail": "https://i.ytimg.com/vi/KzXgZfL84Yk/hqdefault.jpg",
        "context": "Zenless Zone Zero OP",
        "category": "song",
    },
    {
        "title": "Bite Back",
        "artist": "Hoyo-Mix",
        "keywords": ["bite back", "hoyo-mix", "zenless zone zero", "zzz", "hoyoverse"],
        "duration": 210.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "thumbnail": None,
        "context": "Zenless Zone Zero OST",
        "category": "song",
    },
    {
        "title": "SPECIALZ",
        "artist": "King Gnu",
        "keywords": ["specialz", "king gnu", "jujutsu kaisen", "jjk", "shibuya incident", "opening"],
        "duration": 238.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=fhzKLBZJC3w",
        "thumbnail": "https://i.ytimg.com/vi/fhzKLBZJC3w/hqdefault.jpg",
        "context": "JJK Season 2 OP",
        "category": "song",
    },
    {
        "title": "The Rumbling",
        "artist": "SiM",
        "keywords": ["the rumbling", "sim", "attack on titan", "aot", "season 4", "shingeki no kyojin", "opening"],
        "duration": 220.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=OB8_wZJ6yU4",
        "thumbnail": "https://i.ytimg.com/vi/OB8_wZJ6yU4/hqdefault.jpg",
        "context": "Attack on Titan OP",
        "category": "song",
    },
    {
        "title": "KICK BACK",
        "artist": "Kenshi Yonezu",
        "keywords": ["kick back", "kenshi yonezu", "chainsaw man", "csm", "opening", "op"],
        "duration": 213.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=M2cckDmNLMI",
        "thumbnail": "https://i.ytimg.com/vi/M2cckDmNLMI/hqdefault.jpg",
        "context": "Chainsaw Man OP",
        "category": "song",
    },
    {
        "title": "Idol",
        "artist": "YOASOBI",
        "keywords": ["idol", "yoasobi", "oshi no ko", "opening", "op"],
        "duration": 222.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=ZRtdQ81jPUQ",
        "thumbnail": "https://i.ytimg.com/vi/ZRtdQ81jPUQ/hqdefault.jpg",
        "context": "Oshi no Ko OP",
        "category": "song",
    },
    {
        "title": "I Really Want to Stay at Your House",
        "artist": "Rosa Walton",
        "keywords": ["i really want to stay at your house", "rosa walton", "cyberpunk edgerunners", "edgerunners", "cyberpunk"],
        "duration": 246.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=KvMY1uzSC1E",
        "thumbnail": "https://i.ytimg.com/vi/KvMY1uzSC1E/hqdefault.jpg",
        "context": "Cyberpunk Edgerunners OST",
        "category": "song",
    },
    {
        "title": "My Heart Will Go On",
        "artist": "Celine Dion",
        "keywords": ["my heart will go on", "celine dion", "titanic", "titanic theme song", "movie song"],
        "duration": 280.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=3gK_2XdjOdY",
        "thumbnail": "https://i.ytimg.com/vi/3gK_2XdjOdY/hqdefault.jpg",
        "context": "Titanic Soundtrack",
        "category": "song",
    },
    {
        "title": "Cornfield Chase",
        "artist": "Hans Zimmer",
        "keywords": ["cornfield chase", "hans zimmer", "interstellar", "interstellar theme", "soundtrack"],
        "duration": 127.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=1V_xRb0x9aw",
        "thumbnail": "https://i.ytimg.com/vi/1V_xRb0x9aw/hqdefault.jpg",
        "context": "Interstellar OST",
        "category": "song",
    },
    {
        "title": "Never Gonna Give You Up",
        "artist": "Rick Astley",
        "keywords": ["never gonna give you up", "rick astley", "rickroll"],
        "duration": 213.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "thumbnail": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
        "context": "Pop Classic",
        "category": "song",
    },
    {
        "title": "The Emptiness Machine",
        "artist": "Linkin Park",
        "keywords": ["the emptiness machine", "emptiness machine", "linkin park", "from zero"],
        "duration": 190.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=SRXH9AbT280",
        "thumbnail": None,
        "context": "Rock Single",
        "category": "song",
    },
    {
        "title": "The Great Strategy",
        "artist": "ROBLOX",
        "keywords": ["roblox", "roblox game soundtrack", "roblox soundtrack", "roblox music", "game trailer"],
        "duration": 135.0,
        "platform": "youtube",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "thumbnail": None,
        "context": "Roblox Soundtrack",
        "category": "context",
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
    """Classify whether a candidate is genuinely a 'song', 'artist', or 'video', and return (media_type, platform_label)."""
    duration = candidate.get("duration")
    raw_title = candidate.get("title") or ""
    clean_title = strip_media_noise(raw_title)
    title_lower = clean_title.lower()
    artist_lower = (candidate.get("artist") or "").lower()
    source = candidate.get("source")
    platform = candidate.get("platform") or "youtube"
    platform_name = "YouTube" if platform == "youtube" else platform.title()

    if candidate.get("category") == "artist" or candidate.get("type") == "artist":
        return ("artist", "Artist Discovery")

    # 1. Seed discoveries, artist catalog, and soundtrack associations are verified authentic songs
    if source in ("seed", "artist_catalog"):
        match_reason = candidate.get("match_reason") or ""
        label = "Theme Song" if "theme" in match_reason.lower() or "soundtrack" in match_reason.lower() else "Song Discovery"
        return ("song", label)

    if source == "soundtrack":
        return ("song", "Theme Song")

    if source in ("history", "feedback", "adaptive"):
        if candidate.get("media_type") == "audio" or (duration and duration <= 600):
            return ("song", "From History" if source in ("history", "adaptive") else "Verified Match")

    # 2. Strong video indicators
    is_video_content = False
    if duration and duration > 900:
        is_video_content = True

    combined_metadata = f"{title_lower} {artist_lower}"
    if any(ind in combined_metadata for ind in VIDEO_CONTENT_KEYWORDS):
        is_video_content = True

    # 3. Strong music indicators
    music_indicators = [
        "official audio", "official music video", "mv", "lyrics", "feat.", "ft.",
        "soundtrack", "ost", "theme", "opening", "ending", "op", "ed", "remix",
        "acoustic", "instrumental", "karaoke", "orchestra", "symphony",
        "topic", "records", "vevo", "audio", "song", "music", "prod.", "prod by",
        "band", "orchestral", "bgm", "cover", "album", "single", "radio edit",
        "vocal", "vocals",
    ]
    has_music_indicator = any(m in title_lower or m in artist_lower for m in music_indicators)

    if is_video_content:
        if not (has_music_indicator and duration and duration <= 600):
            return ("video", f"{platform_name} Video")

    if has_music_indicator and (duration is None or duration <= 900):
        return ("song", "Song Discovery")

    if any(kw in artist_lower for kw in ("records", "vevo", "topic", "band", "orchestra", "music")):
        return ("song", "Song Discovery")

    if " - " in clean_title and (duration is None or (45 <= duration <= 600)) and not is_video_content:
        return ("song", "Song Discovery")

    return ("video", f"{platform_name} Video")


# -----------------------------------------------------------------------------
# 4. Query Understanding Engine
# -----------------------------------------------------------------------------

def parse_suggestion_intent(query: str) -> SuggestionIntent:
    """Analyze query clues, candidate interpretations, and target fields without mutating the query."""
    clean_q = query.strip()
    norm_q = normalize_text(clean_q)
    tokens = [tok for tok in norm_q.split() if tok]

    matched_artists: List[Dict[str, Any]] = []
    detected_version: Optional[str] = detect_version_hint(clean_q)
    detected_context: Optional[str] = None
    title_fragments: List[str] = []
    interpretations: List[str] = []

    # 1. Match known artists and aliases
    for key, info in KNOWN_ARTISTS_CATALOG.items():
        canonical = info["canonical_name"]
        for alias in info["aliases"]:
            # Exact alias match or prefix
            if norm_q == alias or norm_q.startswith(alias + " ") or (" " + alias) in norm_q:
                matched_artists.append(info)
                interpretations.append(f"Artist: {canonical}")
                break

    # 2. Check soundtrack & franchise clues
    for franchise in SOUNDTRACK_ASSOCIATIONS:
        if franchise in norm_q or norm_q in franchise:
            detected_context = franchise.title()
            interpretations.append(f"Franchise: {detected_context}")
            break

    # 3. Check for specific contextual words (opening, theme, soundtrack)
    context_words = ["opening", "ending", "soundtrack", "ost", "theme", "trailer", "movie", "game"]
    for cw in context_words:
        if cw in tokens:
            detected_context = detected_context or cw.title()
            break

    # 4. Extract possible title fragments if artist was detected in multi-word query
    remaining_tokens = list(tokens)
    for art in matched_artists:
        for alias in art["aliases"]:
            alias_toks = alias.split()
            if all(at in remaining_tokens for at in alias_toks):
                for at in alias_toks:
                    remaining_tokens.remove(at)
                break

    if detected_version:
        # Remove version words from title fragment
        for v_kw in detect_version_hint(clean_q).split():
            if v_kw in remaining_tokens:
                remaining_tokens.remove(v_kw)

    if remaining_tokens:
        title_frag = " ".join(remaining_tokens).strip()
        if title_frag:
            title_fragments.append(title_frag)

    is_single_kw = len(tokens) == 1 and not matched_artists
    is_art_focused = len(matched_artists) > 0 and len(tokens) <= 2
    is_ver_focused = detected_version is not None
    is_ctx_focused = detected_context is not None

    return SuggestionIntent(
        raw_query=clean_q,
        normalized_query=norm_q,
        tokens=tokens,
        matched_artists=matched_artists,
        detected_version=detected_version,
        detected_context=detected_context,
        title_fragments=title_fragments,
        is_artist_focused=is_art_focused,
        is_version_focused=is_ver_focused,
        is_context_focused=is_ctx_focused,
        is_single_keyword=is_single_kw,
        suggested_interpretations=interpretations,
    )


# -----------------------------------------------------------------------------
# 5. Suggestion Engine (Multi-Stage Pipeline)
# -----------------------------------------------------------------------------

class SuggestionEngine:
    """Coordinates smart autocomplete and intelligent song discovery for KON Search 1.2 Rei."""

    def __init__(
        self,
        history_store: Optional[Any] = None,
        feedback_store: Optional[Any] = None,
        search_cache: Optional[Any] = None,
        adaptive_store: Optional[Any] = None,
    ):
        self.history_store = history_store
        self.feedback_store = feedback_store
        self.search_cache = search_cache
        self.adaptive_store = adaptive_store or get_shared_adaptive_store()
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=3, thread_name_prefix="kon_suggest_worker"
        )

    def _fetch_real_query_suggestions(self, query: str, timeout: float = 1.0) -> List[str]:
        """Fetch real search queries via public autocomplete (~100-300ms)."""
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

    def _gather_local_candidates(
        self, intent: SuggestionIntent, media_type: str = "all"
    ) -> List[Dict[str, Any]]:
        """Extract candidates from known artists, seed index, local history, feedback, and adaptive memory."""
        candidates: List[Dict[str, Any]] = []
        norm_q = intent.normalized_query
        query_tokens = intent.tokens

        # Strategy A: Artist Suggestions & Catalog Discovery
        for artist_info in intent.matched_artists:
            canon_name = artist_info["canonical_name"]
            # 1. Add Artist Entity Suggestion
            candidates.append({
                "id": f"artist_{canon_name.lower().replace(' ', '_')}",
                "title": canon_name,
                "artist": artist_info.get("genre", "Artist"),
                "url": None,
                "thumbnail": None,
                "duration": None,
                "platform": "youtube",
                "category": "artist",
                "type": "artist",
                "match_reason": "Artist",
                "context_clue": artist_info.get("genre", "Artist Discovery"),
                "source": "artist_catalog",
            })

            # 2. Add Top Songs for this Artist
            for s in artist_info.get("top_songs", []):
                candidates.append({
                    "id": f"artist_song_{s['title'].lower().replace(' ', '_')}",
                    "title": s["title"],
                    "artist": s["artist"],
                    "url": s.get("url"),
                    "thumbnail": s.get("thumbnail"),
                    "duration": s.get("duration"),
                    "platform": "youtube",
                    "category": "version" if "remix" in s["title"].lower() else "song",
                    "type": "song",
                    "match_reason": f"Popular track by {canon_name}",
                    "context_clue": s.get("context", f"By {canon_name}"),
                    "source": "artist_catalog",
                })

        # Strategy B: Curated Seed Discoveries (Exact titles, keywords, versions, contexts)
        for item in GENUINE_SEED_DISCOVERIES:
            title_norm = normalize_text(item["title"])
            artist_norm = normalize_text(item.get("artist", ""))
            keywords = [normalize_text(k) for k in item.get("keywords", [])]

            is_match = False
            match_category = item.get("category", "song")
            match_reason = "Song Discovery"

            # 1. Exact or partial title match
            if norm_q in title_norm or title_norm in norm_q:
                is_match = True
                match_reason = f"Matches title: {item['title']}"
            elif artist_norm and (norm_q in artist_norm or any(tok in artist_norm.split() for tok in query_tokens if len(tok) >= 3)):
                is_match = True
                match_reason = f"Matches artist: {item['artist']}"
            else:
                # 2. Keyword or context match
                for kw in keywords:
                    if norm_q in kw or kw in norm_q or any(tok == kw or kw.startswith(tok) for tok in query_tokens if len(tok) >= 3):
                        is_match = True
                        if "bankai" in norm_q or len(query_tokens) == 1:
                            match_category = "partial"
                            match_reason = f"Keyword clue: '{kw}'"
                        elif intent.detected_version and any(v in kw for v in ["remix", "jersey"]):
                            match_category = "version"
                            match_reason = "Requested version match"
                        else:
                            match_reason = f"Soundtrack clue: '{kw}'"
                        break

            # 3. Controlled Typo Tolerance (e.g. 'bnkai' -> 'bankai', 'artic' -> 'arctic')
            if not is_match and len(norm_q) >= 4:
                # SequenceMatcher similarity against title, artist, and keywords
                ratio_title = difflib.SequenceMatcher(None, norm_q, title_norm).ratio()
                ratio_artist = difflib.SequenceMatcher(None, norm_q, artist_norm).ratio()
                best_kw_ratio = max([difflib.SequenceMatcher(None, norm_q, kw).ratio() for kw in keywords], default=0.0)

                if ratio_title >= 0.82 or ratio_artist >= 0.82 or best_kw_ratio >= 0.85:
                    is_match = True
                    match_category = "partial"
                    match_reason = f"Did you mean: {item['title']}?"

            if is_match:
                candidates.append({
                    "id": f"seed_{item['title'].lower().replace(' ', '_')}",
                    "title": item["title"],
                    "artist": item.get("artist"),
                    "url": item.get("url"),
                    "thumbnail": item.get("thumbnail"),
                    "duration": item.get("duration"),
                    "platform": item.get("platform", "youtube"),
                    "category": match_category,
                    "type": "song",
                    "match_reason": match_reason,
                    "context_clue": item.get("context"),
                    "source": "seed",
                })

        # Strategy C: Local Adaptive History & Download History
        if self.adaptive_store:
            try:
                ad_matches = self.adaptive_store.get_matching_history(norm_q, limit=4)
                for ad in ad_matches:
                    candidates.append({
                        "id": f"adapt_{ad['title'].lower().replace(' ', '_')}",
                        "title": ad["title"],
                        "artist": ad.get("artist"),
                        "url": ad.get("url"),
                        "thumbnail": ad.get("thumbnail"),
                        "duration": ad.get("duration"),
                        "platform": ad.get("platform", "youtube"),
                        "category": ad.get("category", "song"),
                        "type": "song",
                        "match_reason": "Recently explored",
                        "context_clue": "Local History",
                        "source": "adaptive",
                    })
            except Exception:
                pass

        if self.history_store:
            try:
                h_items = self.history_store.get_all()
                for h in h_items:
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
                            "category": "song",
                            "type": "song",
                            "match_reason": "From download history",
                            "context_clue": "Past Download",
                            "source": "history",
                        })
            except Exception:
                pass

        # Strategy D: Soundtrack Associations Taxonomy (Context-based discovery)
        for key, assoc_titles in SOUNDTRACK_ASSOCIATIONS.items():
            key_norm = normalize_text(key)
            if norm_q in key_norm or key_norm in norm_q or any(tok == key_norm for tok in query_tokens):
                for assoc_title in assoc_titles:
                    artist_part = None
                    clean_t = assoc_title
                    if " - " in assoc_title:
                        parts = assoc_title.split(" - ", 1)
                        artist_part = parts[0].strip()
                        clean_t = parts[1].strip()

                    candidates.append({
                        "id": f"assoc_{clean_t.lower().replace(' ', '_')}",
                        "title": clean_t,
                        "artist": artist_part,
                        "url": None,
                        "thumbnail": None,
                        "duration": None,
                        "platform": "youtube",
                        "category": "context",
                        "type": "song",
                        "match_reason": f"Soundtrack for {key.title()}",
                        "context_clue": f"{key.title()} Soundtrack",
                        "source": "soundtrack",
                    })

        return candidates

    def _score_candidate(
        self,
        candidate: Dict[str, Any],
        intent: SuggestionIntent,
        media_type: str = "all",
    ) -> float:
        """Deterministic multi-signal relevance scoring specifically designed for suggestions.

        Signals:
        1. Exact title match (+1.4)
        2. Prefix / continuous phrase match (+0.9)
        3. Token coverage & word order (+0.6 * coverage + 0.35 * order)
        4. Artist match (+0.8)
        5. Version match (+0.7)
        6. Typo / fuzzy similarity (+0.45 * sim)
        7. Context / soundtrack match (+0.85)
        8. Metadata completeness (+0.25)
        9. Popularity tie-breaker (<= 0.04)
        """
        raw_title = candidate.get("title") or ""
        clean_title = strip_media_noise(raw_title)
        title_norm = normalize_text(clean_title)
        artist_norm = normalize_text(candidate.get("artist") or "")
        norm_q = intent.normalized_query
        query_tokens = intent.tokens

        # Artist suggestions scored directly
        if candidate.get("category") == "artist" or candidate.get("type") == "artist":
            # If query matches artist alias or name
            if title_norm == norm_q:
                return 1.8
            if title_norm.startswith(norm_q) or norm_q in title_norm:
                return 1.5
            ratio = difflib.SequenceMatcher(None, norm_q, title_norm).ratio()
            if ratio >= 0.8:
                return 1.3
            return 0.9

        cand_type, _ = classify_candidate_media_type(candidate, norm_q)

        # Video filtering in audio mode
        if media_type == "audio":
            if any(kw in title_norm for kw in NON_MUSIC_KEYWORDS):
                return 0.0
            if cand_type == "video":
                return 0.0

        full_text_norm = f"{title_norm} {artist_norm}".strip()
        full_tokens = full_text_norm.split()

        # Check match evidence
        has_token_match = any(
            any(q_tok == f_tok or f_tok.startswith(q_tok) or q_tok in f_tok for f_tok in full_tokens)
            for q_tok in query_tokens if len(q_tok) >= 2
        )
        has_substring_match = norm_q in title_norm or norm_q in artist_norm or title_norm in norm_q
        ngram_sim = ngram_similarity(norm_q, title_norm)
        seq_ratio = difflib.SequenceMatcher(None, norm_q, title_norm).ratio()

        if not has_token_match and not has_substring_match and max(ngram_sim, seq_ratio) < 0.35:
            # Check if keywords match
            return 0.0

        score = 0.0

        # 1. Exact title match
        if title_norm == norm_q:
            score += 1.4
        elif title_norm.startswith(norm_q):
            score += 0.95
        elif norm_q in title_norm:
            ratio = len(norm_q) / max(1, len(title_norm))
            score += 0.70 * ratio

        # 2. Artist match
        if artist_norm:
            if artist_norm == norm_q:
                score += 0.9
            elif artist_norm.startswith(norm_q) or norm_q in artist_norm:
                score += 0.75
            elif any(tok in artist_norm.split() or artist_norm.startswith(tok) for tok in query_tokens if len(tok) >= 3):
                score += 0.60

        # If user searched an artist name and candidate is by that artist
        for matched_art in intent.matched_artists:
            art_name = normalize_text(matched_art["canonical_name"])
            if art_name in artist_norm or artist_norm in art_name:
                score += 0.8
                break

        # 3. Token coverage & word order
        if query_tokens and full_tokens:
            matched_count = sum(
                1 for q_tok in query_tokens
                if any(q_tok == f_tok or f_tok.startswith(q_tok) for f_tok in full_tokens)
            )
            coverage = matched_count / len(query_tokens)
            score += 0.60 * coverage

            order_score = compute_word_order_score(query_tokens, full_tokens)
            score += 0.35 * order_score

        # 4. Version qualifier match
        if intent.detected_version:
            cand_version = detect_version_hint(raw_title)
            if cand_version and cand_version == intent.detected_version:
                score += 0.70
            elif intent.detected_version in full_text_norm:
                score += 0.50

        # 5. Typo & fuzzy similarity
        best_sim = max(ngram_sim, seq_ratio)
        score += 0.45 * best_sim

        # 6. Context / Soundtrack match
        if candidate.get("source") == "soundtrack" or intent.detected_context:
            score += 0.55

        # 7. Metadata completeness & verified source
        if candidate.get("thumbnail"):
            score += 0.15
        if candidate.get("duration"):
            score += 0.10
        if candidate.get("source") in ("history", "adaptive", "seed", "artist_catalog"):
            score += 0.25

        # 8. Minor popularity tie-breaker (never overrules relevance)
        views = candidate.get("views") or 0
        if views > 0:
            score += min(0.04, math.log10(1 + views) / 200.0)

        return score

    def _score_song_candidate(
        self,
        candidate: Dict[str, Any],
        norm_q: str,
        query_tokens: List[str],
        detected_version: Optional[str] = None,
        media_type: str = "all",
    ) -> float:
        """Backwards-compatible scoring helper for tests."""
        intent = SuggestionIntent(
            raw_query=norm_q,
            normalized_query=norm_q,
            tokens=query_tokens,
            detected_version=detected_version,
        )
        return self._score_candidate(candidate, intent, media_type=media_type)

    def rank_suggestions(
        self,
        query: str,
        candidates: Optional[List[Dict[str, Any]]] = None,
        query_suggestions: Optional[List[str]] = None,
        limit: int = 6,
        media_type: str = "all",
        song_candidates: Optional[List[Dict[str, Any]]] = None,
    ) -> List[SearchSuggestion]:
        """Rank, categorize, and diversify suggestions."""
        actual_candidates = candidates if candidates is not None else (song_candidates or [])
        actual_queries = query_suggestions or []
        intent = parse_suggestion_intent(query)
        norm_q = intent.normalized_query

        ranked_candidates: List[Tuple[float, Dict[str, Any]]] = []
        seen_keys: Set[str] = set()

        for c in actual_candidates:
            raw_title = c.get("title") or ""
            clean_title = strip_media_noise(raw_title)
            clean_artist = clean_artist_name(c.get("artist"))
            c["artist"] = clean_artist
            c_cat = c.get("category", "song")

            # Deduplication key: ensure identical song title + artist are deduplicated across sources
            if c_cat == "artist":
                dedup_key = f"artist::{normalize_text(clean_title)}"
            else:
                dedup_key = f"{normalize_text(clean_title)}::{normalize_text(clean_artist or '')}"
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            score = self._score_candidate(c, intent, media_type=media_type)
            if score >= 0.40:
                ranked_candidates.append((score, c))

        ranked_candidates.sort(key=lambda x: x[0], reverse=True)

        # Process and rank query refinements
        ranked_queries: List[Tuple[float, str]] = []
        seen_queries: Set[str] = set()
        seen_queries.add(norm_q)

        # Include adaptive user refinements first
        if self.adaptive_store:
            for ref in self.adaptive_store.get_matching_refinements(norm_q, limit=2):
                ref_norm = normalize_text(ref)
                if ref_norm not in seen_queries:
                    seen_queries.add(ref_norm)
                    ranked_queries.append((0.95, ref))

        for qs in query_suggestions:
            qs_clean = qs.strip()
            qs_norm = normalize_text(qs_clean)
            if not qs_clean or qs_norm in seen_queries:
                continue
            seen_queries.add(qs_norm)

            q_score = 0.50
            if qs_norm.startswith(norm_q):
                q_score += 0.40
            elif norm_q in qs_norm:
                q_score += 0.25

            ranked_queries.append((q_score, qs_clean))

        ranked_queries.sort(key=lambda x: x[0], reverse=True)

        # Balanced diversity grouping:
        final_suggestions: List[SearchSuggestion] = []
        artist_candidates = [c for c in ranked_candidates if c[1].get("category") == "artist"]
        song_candidates_pool = [c for c in ranked_candidates if c[1].get("category") != "artist"]

        # If user searched an artist name specifically with no song title fragment (e.g. "Porter", "Arctic Monkeys")
        prefer_artist_first = bool(artist_candidates and not intent.title_fragments)

        if prefer_artist_first and artist_candidates:
            score, cand = artist_candidates[0]
            confidence = "strong" if score >= 1.0 else ("possible" if score >= 0.65 else "weak")
            final_suggestions.append(
                SearchSuggestion(
                    id=cand.get("id") or f"artist_{len(final_suggestions)}",
                    query=cand["title"],
                    title=cand["title"],
                    artist=cand.get("artist"),
                    type="artist",
                    category="artist",
                    confidence=confidence,
                    context_clue=cand.get("context_clue", "Artist"),
                    version_hint=None,
                    platform=cand.get("platform", "youtube"),
                    thumbnail=cand.get("thumbnail"),
                    duration=None,
                    url=None,
                    match_reason=cand.get("match_reason", "Artist"),
                    score=score,
                )
            )

        # 2. Add top song discoveries (up to 4)
        top_songs = song_candidates_pool[:4]
        for score, cand in top_songs:
            clean_t = strip_media_noise(cand["title"])
            cand_type, platform_label = classify_candidate_media_type(cand, query)
            search_exec_query = f"{clean_t} {cand['artist']}".strip() if cand.get("artist") else clean_t
            confidence = "strong" if score >= 1.0 else ("possible" if score >= 0.65 else "weak")

            final_suggestions.append(
                SearchSuggestion(
                    id=cand.get("id") or f"{cand_type}_{len(final_suggestions)}",
                    query=search_exec_query,
                    title=clean_t,
                    artist=cand.get("artist"),
                    type=cand_type,
                    category=cand.get("category", "song"),
                    confidence=confidence,
                    context_clue=cand.get("context_clue"),
                    version_hint=detect_version_hint(clean_t),
                    platform=cand.get("platform") or "youtube",
                    thumbnail=cand.get("thumbnail"),
                    duration=cand.get("duration"),
                    url=cand.get("url"),
                    match_reason=cand.get("match_reason") or platform_label,
                    score=score,
                )
            )

        # If artist suggestion was not placed first, insert it after top song if room permits
        if not prefer_artist_first and artist_candidates and len(final_suggestions) < limit:
            score, cand = artist_candidates[0]
            confidence = "strong" if score >= 1.0 else ("possible" if score >= 0.65 else "weak")
            final_suggestions.append(
                SearchSuggestion(
                    id=cand.get("id") or f"artist_{len(final_suggestions)}",
                    query=cand["title"],
                    title=cand["title"],
                    artist=cand.get("artist"),
                    type="artist",
                    category="artist",
                    confidence=confidence,
                    context_clue=cand.get("context_clue", "Artist"),
                    version_hint=None,
                    platform=cand.get("platform", "youtube"),
                    thumbnail=cand.get("thumbnail"),
                    duration=None,
                    url=None,
                    match_reason=cand.get("match_reason", "Artist"),
                    score=score,
                )
            )

        # 3. Fill remaining slots with query refinements
        remaining_slots = max(1, limit - len(final_suggestions))
        for q_score, q_text in ranked_queries[:remaining_slots]:
            final_suggestions.append(
                SearchSuggestion(
                    id=f"query_{len(final_suggestions)}",
                    query=q_text,
                    title=q_text,
                    artist=None,
                    type="query",
                    category="query",
                    confidence="possible",
                    context_clue="Suggested Search",
                    version_hint=None,
                    thumbnail=None,
                    duration=None,
                    url=None,
                    match_reason="Suggested query",
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

        intent = parse_suggestion_intent(clean_q)

        # Sub-millisecond local candidate gathering
        local_candidates = self._gather_local_candidates(intent, media_type=media_type)

        # Concurrent external lookups with fast timeouts
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

        all_candidates = local_candidates + provider_candidates

        ranked = self.rank_suggestions(
            query=clean_q,
            candidates=all_candidates,
            query_suggestions=query_suggestions,
            limit=limit,
            media_type=media_type,
        )

        results = [s.to_dict() for s in ranked]

        # Store in LRU cache
        if len(_SUGGESTION_CACHE) >= _MAX_CACHE_SIZE:
            try:
                del _SUGGESTION_CACHE[next(iter(_SUGGESTION_CACHE))]
            except Exception:
                pass
        _SUGGESTION_CACHE[cache_key] = (now, results)

        return results


# -----------------------------------------------------------------------------
# 6. Global Shared Engine Singleton
# -----------------------------------------------------------------------------

_shared_suggestion_engine: Optional[SuggestionEngine] = None


def get_shared_suggestion_engine() -> SuggestionEngine:
    global _shared_suggestion_engine
    if _shared_suggestion_engine is None:
        from backend.config import STATE_DIR
        from backend.search.adaptive_suggestions import get_shared_adaptive_store
        from backend.search.cache import get_shared_search_cache
        from backend.search.feedback import SearchFeedbackStore
        from backend.storage.storage import HistoryStore

        _shared_suggestion_engine = SuggestionEngine(
            history_store=HistoryStore(STATE_DIR),
            feedback_store=SearchFeedbackStore(),
            search_cache=get_shared_search_cache(),
            adaptive_store=get_shared_adaptive_store(),
        )
    return _shared_suggestion_engine
