"""Query and metadata normalization, Unicode handling, typo tolerance, and token matching."""

import re
import unicodedata
from typing import List, Set, Tuple, Optional
from backend.search.models import SearchQuery

# Noise patterns commonly found in media titles
NOISE_PATTERNS = [
    re.compile(r"\[[^\]]*(official|video|audio|remaster|hd|4k|lyrics?)[^\]]*\]", re.IGNORECASE),
    re.compile(r"\([^)]*(official|video|audio|remaster|hd|4k|lyrics?|clip\s*officiel|video\s*oficial)[^)]*\)", re.IGNORECASE),
    re.compile(r"\|\s*official\s*(trailer|video)\s*.*", re.IGNORECASE),
]

VERSION_KEYWORDS = {
    "remix": ["remix", "mix", "club mix", "extended mix", "dub"],
    "live": ["live", "live aid", "in concert", "at wembley", "coachella"],
    "instrumental": ["instrumental", "backing track", "karaoke", "piano cover"],
    "acoustic": ["acoustic", "unplugged"],
    "cover": ["cover", "parody", "tribute"],
}

# Cultural media and soundtrack associations (when user searches for a movie, game, or meme and wants a song)
SOUNDTRACK_ASSOCIATIONS = {
    "titanic": ["Celine Dion - My Heart Will Go On", "Titanic Theme Song"],
    "rickroll": ["Rick Astley - Never Gonna Give You Up"],
    "cyberpunk": ["Rosa Walton - I Really Want to Stay at Your House", "SAMURAI - Chippin In"],
    "cyberpunk edgerunners": ["Rosa Walton - I Really Want to Stay at Your House"],
    "interstellar": ["Hans Zimmer - Cornfield Chase", "Hans Zimmer - S.T.A.Y."],
    "stranger things": ["Kate Bush - Running Up That Hill", "Stranger Things Theme"],
    "top gun": ["Kenny Loggins - Danger Zone", "Berlin - Take My Breath Away"],
    "shrek": ["Smash Mouth - All Star", "Rufus Wainwright - Hallelujah"],
    "the witcher": ["Toss A Coin To Your Witcher"],
    "naruto": ["KANA-BOON - Silhouette", "Ikimonogakari - Blue Bird", "Sadness and Sorrow"],
    "inception": ["Hans Zimmer - Time"],
    "skyfall": ["Adele - Skyfall"],
    "rocky": ["Survivor - Eye of the Tiger", "Bill Conti - Gonna Fly Now"],
    "undertale": ["Toby Fox - Megalovania"],
    "minecraft": ["C418 - Sweden", "C418 - Wet Hands"],
    "doom": ["Mick Gordon - The Only Thing They Fear Is You", "Mick Gordon - BFG Division"],
    "star wars": ["John Williams - The Imperial March", "John Williams - Duel of the Fates"],
    "gladiator": ["Hans Zimmer - Now We Are Free"],
    "drive": ["Kavinsky - Nightcall"],
    "pulp fiction": ["Dick Dale - Misirlou"],
}


def resolve_soundtrack_associations(query_str: str) -> List[str]:
    """Resolve iconic theme songs or soundtrack titles for movies, games, memes, or shows."""
    norm = normalize_text(query_str)
    matches = []
    for key, tracks in SOUNDTRACK_ASSOCIATIONS.items():
        if key in norm or norm in key:
            matches.extend(tracks)
    return matches


def normalize_text(text: Optional[str]) -> str:
    """Normalize text with Unicode NFKD decomposition, lowercase, and clean whitespace.

    Preserves non-Latin scripts (Japanese, Cyrillic, etc.) while stripping Latin diacritics.
    """
    if not text:
        return ""

    # NFKD decomposition
    decomposed = unicodedata.normalize("NFKD", text)
    # Strip non-spacing mark diacritics for Latin characters (e.g. é -> e, ñ -> n)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    # Lowercase
    lowered = stripped.lower().strip()
    # Replace non-alphanumeric/non-script characters with single space
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    # Collapse multiple whitespace
    return " ".join(cleaned.split())


def strip_media_noise(title: str) -> str:
    """Strip common promotional noise from titles, e.g. [Official Video] or (HD)."""
    cleaned = title
    for pat in NOISE_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    return " ".join(cleaned.split())


def detect_version_hint(text: str) -> Optional[str]:
    """Detect whether query or title explicitly requests a specific version."""
    norm = normalize_text(text)
    for version_type, keywords in VERSION_KEYWORDS.items():
        for kw in keywords:
            # Word boundary check
            if re.search(r"\b" + re.escape(kw) + r"\b", norm):
                return version_type
    return None


def parse_query_intent(
    query_str: str,
    expected_artist: Optional[str] = None,
    expected_title: Optional[str] = None,
    expected_duration: Optional[float] = None,
    media_type: str = "all",
) -> SearchQuery:
    """Parse query into structured intent: artist, title, version hint, media type."""
    norm_query = normalize_text(query_str)
    version_hint = detect_version_hint(query_str)

    detected_artist = expected_artist
    detected_title = expected_title

    # If no expected artist/title provided, try parsing "Artist - Title" or "Title by Artist"
    if not detected_artist or not detected_title:
        if " - " in query_str:
            parts = query_str.split(" - ", 1)
            detected_artist = parts[0].strip()
            detected_title = parts[1].strip()
        elif " by " in query_str.lower():
            parts = re.split(r"\s+by\s+", query_str, flags=re.IGNORECASE, maxsplit=1)
            detected_title = parts[0].strip()
            detected_artist = parts[1].strip()

    return SearchQuery(
        raw_query=query_str,
        normalized_query=norm_query,
        detected_artist=detected_artist,
        detected_title=detected_title,
        version_hint=version_hint,
        expected_duration=expected_duration,
        expected_artist=expected_artist,
        expected_title=expected_title,
        media_type=media_type,
    )


def extract_char_ngrams(s: str, n: int = 3) -> Set[str]:
    """Extract character n-grams from a normalized string for typo tolerance."""
    if len(s) < n:
        return {s} if s else set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def ngram_similarity(s1: str, s2: str, n: int = 3) -> float:
    """Calculate Jaccard similarity over character n-grams.

    Robust to typos, transpositions, and dropped characters (e.g. bohemain vs bohemian).
    """
    norm1 = normalize_text(s1)
    norm2 = normalize_text(s2)
    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 1.0

    ng1 = extract_char_ngrams(norm1, n)
    ng2 = extract_char_ngrams(norm2, n)
    union_len = len(ng1 | ng2)
    if union_len == 0:
        return 0.0
    return len(ng1 & ng2) / union_len


def token_overlap_ratio(text1: str, text2: str) -> float:
    """Calculate overlap ratio of distinct words between two texts."""
    tokens1 = set(normalize_text(text1).split())
    tokens2 = set(normalize_text(text2).split())
    if not tokens1 or not tokens2:
        return 0.0
    intersection = tokens1 & tokens2
    return len(intersection) / len(tokens1)
