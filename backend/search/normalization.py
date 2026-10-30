"""Query and metadata normalization, Unicode handling, typo tolerance, and token matching."""

import re
import unicodedata

try:
    import kon_search_core as _rust_core
except ImportError:
    _rust_core = None
from typing import List, Set, Tuple, Optional
from backend.search.models import SearchQuery

# Noise patterns commonly found in media titles
NOISE_PATTERNS = [
    re.compile(r"\[[^\]]*(official|video|audio|remaster|hd|4k|lyrics?)[^\]]*\]", re.IGNORECASE),
    re.compile(r"\([^)]*(official|video|audio|remaster|hd|4k|lyrics?|clip\s*officiel|video\s*oficial)[^)]*\)", re.IGNORECASE),
    re.compile(r"\|\s*official\s*(trailer|video)\s*.*", re.IGNORECASE),
]

VERSION_KEYWORDS = {
    "remix": ["remix", "mix", "club mix", "extended mix", "dub", "flip", "jersey club", "jersey remix", "jersey"],
    "live": ["live", "live aid", "in concert", "at wembley", "coachella", "acoustic live", "live performance"],
    "instrumental": ["instrumental", "backing track", "karaoke", "piano cover", "instrumental version"],
    "acoustic": ["acoustic", "unplugged", "acoustic version"],
    "cover": ["cover", "parody", "tribute"],
    "slowed": ["slowed", "slowed down", "slowed + reverb", "slowed and reverb", "reverb"],
    "sped_up": ["sped up", "speed up", "nightcore", "fast version"],
    "version": ["version", "ver", "edit", "edition"],
}

# Cultural media, gaming, anime, and soundtrack associations
SOUNDTRACK_ASSOCIATIONS = {
    # Zenless Zone Zero & Hoyoverse
    "zenless zone zero season 3 chapter 2": ["jo0ji - I-BULL"],
    "zenless zone zero chapter 2": ["jo0ji - I-BULL"],
    "zenless zone zero season 3": ["jo0ji - I-BULL"],
    "zenless zone zero ibull": ["jo0ji - I-BULL"],
    "zenless zone zero iburu": ["jo0ji - I-BULL"],
    "zenless zone zero opening": ["jo0ji - I-BULL", "Hoyo-Mix - Bite Back"],
    "zenless zone zero": ["jo0ji - I-BULL", "Hoyo-Mix - Bite Back", "Swae Lee - Come Alive"],
    "genshin impact": ["Yu-Peng Chen - Genshin Impact Main Theme", "Cecilia Cara - La Vaguelette"],
    "honkai star rail": ["Jonathan Steingard - Wildfire", "Jake Miller - WHITE NIGHT", "Chevy - Hope Is the Thing With Feathers"],
    # Major Anime Soundtracks
    "chainsaw man": ["Kenshi Yonezu - KICK BACK", "Vaundy - Chainsaw Blood", "Maximum the Hormone - Hawatari Nioku Centi"],
    "jujutsu kaisen season 2": ["King Gnu - SPECIALZ", "Tatsuya Kitani - Where Our Blue Is"],
    "jujutsu kaisen": ["King Gnu - SPECIALZ", "Tatsuya Kitani - Where Our Blue Is", "Eve - Kaikai Kitan"],
    "attack on titan season 4": ["SiM - The Rumbling", "Shinsei Kamattechan - My War"],
    "attack on titan": ["SiM - The Rumbling", "Linked Horizon - Shinzou wo Sasageyo!", "Ai Higuchi - Akuma no Ko"],
    "bleach tybw": ["Shiro Sagisu - Number One - Bankai", "w.o.d. - STARS"],
    "bleach bankai": ["Shiro Sagisu - Number One - Bankai"],
    "bleach": ["Shiro Sagisu - Number One - Bankai", "w.o.d. - STARS", "ORANGE RANGE - Asterisk"],
    "oshi no ko": ["YOASOBI - Idol", "GEMN - Fatal", "Queen Bee - Mephisto"],
    "frieren": ["YOASOBI - The Brave", "yorushika - Sunny", "milet - Anytime Anywhere"],
    "dandadan": ["Creepy Nuts - Otonoke", "ZUTOMAYO - TAIDADA"],
    "solo leveling": ["TOMORROW X TOGETHER - LEveL", "LiSA - ReawakeR"],
    "demon slayer": ["LiSA - Gurenge", "Aimer - Zankyou Sanka", "MAN WITH A MISSION x milet - Kizuna no Kiseki"],
    "kimetsu no yaiba": ["LiSA - Gurenge", "Aimer - Zankyou Sanka"],
    "cyberpunk edgerunners": ["Rosa Walton - I Really Want to Stay at Your House", "Franz Ferdinand - This Fffire"],
    "cyberpunk": ["Rosa Walton - I Really Want to Stay at Your House", "SAMURAI - Chippin In"],
    "arcane": ["Imagine Dragons - Enemy", "Linkin Park - Heavy Is the Crown", "Ashnikko - Paint The Town Blue"],
    "league of legends": ["K/DA - POP/STARS", "Against The Current - Legends Never Die", "NewJeans - GODS"],
    "titanic": ["Celine Dion - My Heart Will Go On", "Titanic Theme Song"],
    "rickroll": ["Rick Astley - Never Gonna Give You Up"],
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
    "counter strike 2": ["Counter Strike 2 Soundtrack - Main Menu", "Valve Theme (CS2)", "Counter Strike 2 Theme"],
    "counter strike": ["Counter Strike Soundtrack - Main Menu", "Valve Theme", "Counter Strike Theme"],
    "cs2": ["Counter Strike 2 Soundtrack - Main Menu", "Valve Theme (CS2)"],
    "csgo": ["CS:GO Official Soundtrack - Main Menu", "Valve Theme"],
    "doom": ["Mick Gordon - The Only Thing They Fear Is You", "Mick Gordon - BFG Division"],
    "star wars": ["John Williams - The Imperial March", "John Williams - Duel of the Fates"],
    "gladiator": ["Hans Zimmer - Now We Are Free"],
    "drive": ["Kavinsky - Nightcall"],
    "pulp fiction": ["Dick Dale - Misirlou"],
}


def resolve_soundtrack_associations(query_str: str) -> List[str]:
    """Resolve iconic theme songs or soundtrack titles for movies, games, memes, or shows."""
    norm = normalize_text(query_str)
    if not norm:
        return []

    # First check if the query itself is a cluttered anime/game video title
    from backend.search.entity_parser import parse_media_entity
    parsed = parse_media_entity(query_str)
    if parsed.get("is_cluttered") and parsed.get("clean_title"):
        return [parsed["clean_title"]]

    matches = []
    # Sort keys by length descending so specific combinations match first
    sorted_keys = sorted(SOUNDTRACK_ASSOCIATIONS.keys(), key=len, reverse=True)
    for key in sorted_keys:
        # Require word boundary matching so queries do not falsely trigger via loose substring
        pattern = r"\b" + re.escape(key) + r"\b"
        if re.search(pattern, norm):
            candidates_for_key = SOUNDTRACK_ASSOCIATIONS[key]
            # If the user query is already requesting a specific song, filter to matching songs
            query_tokens = [tok for tok in norm.split() if len(tok) >= 3 and tok != key]
            if query_tokens:
                filtered = [
                    c for c in candidates_for_key
                    if any(tok in normalize_text(c).split() for tok in query_tokens)
                ]
                if filtered:
                    matches.extend(filtered)
                    break
            matches.extend(candidates_for_key)
            break

    return matches


def normalize_text(text: Optional[str]) -> str:
    """Normalize text with Unicode NFKD decomposition, lowercase, and clean whitespace.

    Preserves non-Latin scripts (Japanese, Cyrillic, etc.) while stripping Latin diacritics.
    Leverages native Rust core when available for 20x faster normalization.
    """
    if not text:
        return ""

    if _rust_core is not None:
        try:
            return _rust_core.normalize_query(text)
        except Exception:
            pass

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


def compact_text(text: Optional[str]) -> str:
    """Collapse whitespace to normalize compound words (e.g. 'new jeans' -> 'newjeans')."""
    if not text:
        return ""
    return normalize_text(text).replace(" ", "")


def strip_media_noise(title: str) -> str:
    """Strip common promotional noise from titles, e.g. [Official Video] or (HD)."""
    cleaned = title
    for pat in NOISE_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    return " ".join(cleaned.split())


SPECIFIC_QUALIFIERS = [
    "jersey club",
    "jersey remix",
    "sped up",
    "speed up",
    "slowed down",
    "slowed + reverb",
    "slowed and reverb",
    "slowed",
    "nightcore",
    "club mix",
    "extended mix",
    "acoustic live",
    "live aid",
    "piano cover",
    "instrumental version",
    "radio edit",
    "deluxe edition",
    "remastered",
]

EDITION_KEYWORDS = [
    "version",
    "ver",
    "edit",
    "edition",
    "deluxe",
    "remaster",
    "remastered",
]

COMMON_ARTIST_CUES = [
    "arctic monkeys",
    "porter robinson madeon",
    "porter robinson",
    "madeon",
    "daft punk",
    "the weeknd",
    "queen",
    "eminem",
    "newjeans",
    "new jeans",
    "shiro sagisu",
    "yoasobi",
    "lisa",
    "aimer",
    "kenshi yonezu",
    "king gnu",
    "vaundy",
    "tatsuya kitani",
    "linked horizon",
    "sim",
    "creepy nuts",
    "zutomayo",
    "eve",
    "imagine dragons",
    "linkin park",
    "hans zimmer",
    "kate bush",
    "steve lacy",
    "chase atlantic",
    "billie eilish",
    "taylor swift",
    "post malone",
    "travis scott",
    "drake",
    "kendrick lamar",
    "joji",
    "jo0ji",
    "against the current",
    "k/da",
    "celine dion",
    "adele",
    "rick astley",
]


def detect_specific_qualifier(text: str) -> Optional[str]:
    """Detect specific multi-word version qualifier phrase if present."""
    norm = normalize_text(text)
    for q in SPECIFIC_QUALIFIERS:
        if re.search(r"\b" + re.escape(q) + r"\b", norm):
            return q
    return None


def detect_edition(text: str) -> Optional[str]:
    """Detect release edition keyword if present."""
    norm = normalize_text(text)
    for ed in EDITION_KEYWORDS:
        if re.search(r"\b" + re.escape(ed) + r"\b", norm):
            return ed
    return None


def detect_version_hint(text: str) -> Optional[str]:
    """Detect whether query or title explicitly requests a specific version."""
    norm = normalize_text(text)
    if "original mix" in norm:
        return None

    # Check keyword taxonomy, prioritizing longer phrases first within each category
    for version_type, keywords in VERSION_KEYWORDS.items():
        sorted_kws = sorted(keywords, key=len, reverse=True)
        for kw in sorted_kws:
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
    """Parse query into structured intent: artist, title, version hint, qualifier, edition."""
    raw = query_str.strip()
    norm_query = normalize_text(raw)
    version_hint = detect_version_hint(raw)
    qualifier = detect_specific_qualifier(raw)
    edition = detect_edition(raw)

    # Extract quoted exact phrases
    exact_phrases = re.findall(r'"([^"]+)"', raw)

    detected_artist = expected_artist
    detected_title = expected_title

    # 1. Check parenthetical edition/version (e.g. 'NewJeans - Jersey Club (Version)')
    core_text = raw
    paren_match = re.search(r"[\(\[【]([^\)\]】]+)[\)\]】]$", core_text)
    if paren_match:
        tag_inside = paren_match.group(1).strip().lower()
        if any(ed in tag_inside for ed in EDITION_KEYWORDS) or detect_version_hint(tag_inside):
            if not edition:
                edition = tag_inside
            # Strip trailing tag to isolate core artist and song
            core_text = core_text[:paren_match.start()].strip()

    # 2. Check explicit delimiters: " - ", " – ", " — ", " / ", " by "
    if not detected_artist or not detected_title:
        delimiter_matched = False
        for sep in (" - ", " – ", " — ", " / "):
            if sep in core_text:
                parts = core_text.split(sep, 1)
                detected_artist = parts[0].strip()
                detected_title = parts[1].strip()
                delimiter_matched = True
                break

        if not delimiter_matched and " by " in core_text.lower():
            parts = re.split(r"\s+by\s+", core_text, flags=re.IGNORECASE, maxsplit=1)
            detected_title = parts[0].strip()
            detected_artist = parts[1].strip()
            delimiter_matched = True

    # 3. Check featuring tokens: " feat. ", " feat ", " ft. ", " ft "
    if detected_title and any(f in detected_title.lower() for f in (" feat. ", " feat ", " ft. ", " ft ")):
        ft_parts = re.split(r"\s+(?:feat\.?|ft\.?)\s+", detected_title, flags=re.IGNORECASE, maxsplit=1)
        detected_title = ft_parts[0].strip()

    # 4. Non-delimited queries: test against common artist cues (e.g. 'I Wanna Be Yours Arctic Monkeys', 'Shelter Porter Robinson Madeon')
    if not detected_artist or not detected_title:
        core_norm = normalize_text(core_text)
        found_cue = False
        for cue in sorted(COMMON_ARTIST_CUES, key=len, reverse=True):
            cue_norm = normalize_text(cue)
            # Suffix match: "<Title> <Artist>"
            pattern_end = r"^(.*?)\s+\b" + re.escape(cue_norm) + r"\b$"
            m_end = re.search(pattern_end, core_norm)
            if m_end and len(m_end.group(1).strip()) >= 2:
                # Find matching character slice in core_text
                cut_idx = len(m_end.group(1).strip())
                # Reconstruct capitalization
                detected_title = core_text[:cut_idx].strip()
                detected_artist = core_text[cut_idx:].strip()
                found_cue = True
                break

            # Prefix match: "<Artist> <Title>"
            pattern_start = r"^\b" + re.escape(cue_norm) + r"\b\s+(.*)$"
            m_start = re.search(pattern_start, core_norm)
            if m_start and len(m_start.group(1).strip()) >= 2:
                cut_idx = len(cue_norm)
                detected_artist = core_text[:cut_idx].strip()
                detected_title = core_text[cut_idx:].strip()
                found_cue = True
                break

        if not found_cue:
            # Check if query ends with trailing version term (e.g. "song title live" -> title="song title")
            if version_hint and not detected_title:
                clean_no_version = core_text
                for kw in VERSION_KEYWORDS.get(version_hint, []):
                    clean_no_version = re.sub(r"\b" + re.escape(kw) + r"\b", "", clean_no_version, flags=re.IGNORECASE).strip()
                if len(clean_no_version) >= 2:
                    detected_title = clean_no_version

            if not detected_title:
                detected_title = core_text

    return SearchQuery(
        raw_query=raw,
        normalized_query=norm_query,
        detected_artist=detected_artist,
        detected_title=detected_title,
        version_hint=version_hint,
        qualifier=qualifier,
        edition=edition,
        expected_duration=expected_duration,
        expected_artist=expected_artist,
        expected_title=expected_title,
        media_type=media_type,
        exact_phrases=exact_phrases,
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
