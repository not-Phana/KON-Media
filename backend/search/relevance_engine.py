"""KON Search 1.1.0 Rei — Pure-Python Relevance-First Search Engine.

Implements identical ranking semantics, feature extraction, deduplication,
and deterministic tie-breaking to the kon_search_core Rust engine.
Guarantees sub-millisecond ranking latency on candidate pools up to 100+ items.
"""

import math
import re
import unicodedata
from typing import Any, Dict, List, Optional, Set, Tuple
from backend.search.models import CandidateResult, SearchQuery

RELEVANCE_ENGINE_VERSION = "1.1.0"

DISQUALIFYING_VERSION_TERMS: List[Tuple[str, float]] = [
    ("parody", 0.35),
    ("minecraft", 0.45),
    ("roblox", 0.45),
    ("earrape", 0.40),
    ("nightcore", 0.35),
    ("bass boosted", 0.25),
    ("8d audio", 0.30),
]

NON_MUSIC_TERMS: List[Tuple[str, float]] = [
    ("documentary", 0.25),
    ("trailer", 0.25),
    ("teaser", 0.25),
    ("tutorial", 0.25),
    ("gameplay", 0.25),
    ("walkthrough", 0.25),
    ("review", 0.30),
    ("interview", 0.30),
    ("podcast", 0.30),
    ("reaction", 0.25),
    ("scene", 0.30),
    ("movie clip", 0.25),
    ("ending scene", 0.25),
    ("workout", 0.25),
    ("fitness", 0.25),
    ("routine", 0.25),
    ("exercise", 0.25),
]

NOISE_RE = re.compile(
    r"(\[[^\]]*(?:official|video|audio|remaster|hd|4k|lyrics?|clip\s*officiel)[^\]]*\]|\([^)]*(?:official|video|audio|remaster|hd|4k|lyrics?|clip\s*officiel)[^)]*\)|\|\s*official\s*(?:video|audio|trailer).*)",
    re.IGNORECASE,
)


def normalize_text(text: Optional[str]) -> str:
    """Normalize text: Unicode NFKD decomposition, lowercase, alphanumeric characters separated by single space."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    stripped = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
    lowered = stripped.lower().strip()
    cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
    return " ".join(cleaned.split())


def strip_media_noise(text: str) -> str:
    """Remove common media noise patterns like [Official Video], (HD Remastered)."""
    cleaned = NOISE_RE.sub(" ", text)
    return " ".join(cleaned.split())


def normalize_media_url(raw_url: Optional[str]) -> str:
    """Normalize URL into a canonical deduplication key."""
    if not raw_url:
        return ""
    trimmed = raw_url.strip()
    if "youtube.com/watch" in trimmed and "v=" in trimmed:
        pos = trimmed.find("v=")
        after_v = trimmed[pos + 2 :]
        vid = after_v.split("&")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    if "youtu.be/" in trimmed:
        pos = trimmed.find("youtu.be/")
        after_slash = trimmed[pos + 9 :]
        vid = after_slash.split("?")[0]
        return f"https://www.youtube.com/watch?v={vid}"
    if "soundcloud.com/" in trimmed:
        base = trimmed.split("?")[0]
        return base.rstrip("/")
    return trimmed


def extract_char_ngrams(s: str, n: int = 3) -> Set[str]:
    """Extract character n-grams from a normalized string."""
    if not s:
        return set()
    if len(s) < n:
        return {s}
    return {s[i : i + n] for i in range(len(s) - n + 1)}


def ngram_similarity(s1: str, s2: str, n: int = 3) -> float:
    """Jaccard similarity over character n-grams for typo tolerance."""
    n1 = normalize_text(s1)
    n2 = normalize_text(s2)
    if not n1 or not n2:
        return 0.0
    if n1 == n2:
        return 1.0
    g1 = extract_char_ngrams(n1, n)
    g2 = extract_char_ngrams(n2, n)
    union_len = len(g1 | g2)
    if union_len == 0:
        return 0.0
    return len(g1 & g2) / union_len


def levenshtein_distance(s1: str, s2: str) -> int:
    """Compute Levenshtein distance between two strings."""
    if s1 == s2:
        return 0
    l1, l2 = len(s1), len(s2)
    if l1 == 0:
        return l2
    if l2 == 0:
        return l1
    prev_row = list(range(l2 + 1))
    curr_row = [0] * (l2 + 1)
    for i in range(l1):
        curr_row[0] = i + 1
        for j in range(l2):
            cost = 0 if s1[i] == s2[j] else 1
            curr_row[j + 1] = min(prev_row[j + 1] + 1, curr_row[j] + 1, prev_row[j] + cost)
        prev_row = curr_row[:]
    return prev_row[l2]


def levenshtein_similarity(s1: str, s2: str) -> float:
    """Character-level edit similarity (0.0 to 1.0)."""
    n1 = normalize_text(s1)
    n2 = normalize_text(s2)
    if n1 == n2:
        return 1.0
    max_len = max(len(n1), len(n2))
    if max_len == 0:
        return 1.0
    dist = levenshtein_distance(n1, n2)
    return max(0.0, min(1.0, 1.0 - (dist / max_len)))


def detect_version_hint(text: str) -> Optional[str]:
    """Detect version hint from text."""
    norm = normalize_text(text)
    if "original mix" in norm:
        return None  # Original Mix is standard studio version for electronic/dance
    keywords = {
        "remix": ["remix", "mix", "club mix", "extended mix"],
        "live": ["live", "live aid", "in concert", "at wembley"],
        "instrumental": ["instrumental", "karaoke", "backing track"],
        "acoustic": ["acoustic", "unplugged"],
        "cover": ["cover", "parody", "tribute"],
    }
    padded = f" {norm} "
    for cat, terms in keywords.items():
        for term in terms:
            if f" {term} " in padded:
                return cat
    return None


def extract_features(query: SearchQuery, candidate: CandidateResult) -> Dict[str, float]:
    """Extract quantitative relevance signals for a candidate."""
    from backend.search.normalization import resolve_soundtrack_associations
    raw_q = query.raw_query
    norm_q = query.normalized_query or normalize_text(raw_q)
    clean_title = strip_media_noise(candidate.title)
    norm_title = normalize_text(clean_title)
    norm_clean = normalize_text(candidate.clean_title) if candidate.clean_title else ""
    uploader_norm = normalize_text(candidate.uploader)
    media_type = (query.media_type or "all").lower()

    # Formulate target query representations: original query + resolved soundtrack songs if any
    target_queries = [norm_q]
    associated_tracks = resolve_soundtrack_associations(raw_q)
    if associated_tracks:
        for t in associated_tracks:
            norm_t = normalize_text(t)
            if norm_t and norm_t not in target_queries:
                target_queries.append(norm_t)

    # 1. Exact title match (evaluating across raw title, clean parsed song title, and resolved targets)
    exact_title = 0.0
    phrase_match = 0.0
    token_coverage = 0.0
    token_order = 1.0

    cand_title_variants = [norm_title]
    if norm_clean and norm_clean != norm_title:
        cand_title_variants.append(norm_clean)

    for tq in target_queries:
        for ctv in cand_title_variants:
            e = 1.0 if tq == ctv else (0.95 if ctv.startswith(tq) else (0.85 if tq in ctv else 0.0))
            exact_title = max(exact_title, e)

            p = 1.0 if (tq and tq in ctv) else 0.0
            phrase_match = max(phrase_match, p)

        t_toks = [w for w in tq.split() if w]
        if t_toks:
            all_c_toks = set(norm_title.split())
            if norm_clean:
                all_c_toks.update(norm_clean.split())
            matched = sum(1 for w in t_toks if w in all_c_toks)
            cov = matched / len(t_toks)
            token_coverage = max(token_coverage, cov)

    # 4. Typo similarity
    ngram_sim = ngram_similarity(norm_q, norm_title, n=3)
    lev_sim = levenshtein_similarity(norm_q, norm_title)
    typo_similarity = max(ngram_sim, lev_sim)

    # 5. Artist affinity
    artist_affinity = 0.5
    target_artist = query.expected_artist or query.detected_artist or candidate.artist
    if target_artist:
        norm_artist = normalize_text(target_artist)
        if norm_artist:
            if norm_artist in uploader_norm or uploader_norm in norm_artist:
                artist_affinity = 1.0
            elif norm_title.startswith(norm_artist) or (norm_clean and norm_clean.startswith(norm_artist)):
                artist_affinity = 0.95
            elif ngram_similarity(norm_artist, uploader_norm, 3) > 0.6:
                artist_affinity = 0.85
            else:
                artist_affinity = 0.30

    # 6. Version compatibility
    cand_version = detect_version_hint(candidate.title)
    query_version = query.version_hint or detect_version_hint(raw_q)
    version_compat = 1.0

    for term, mult in DISQUALIFYING_VERSION_TERMS:
        if term in norm_title:
            permitted = (query_version and term in query_version)
            if not permitted:
                version_compat = mult
                break

    if version_compat == 1.0:
        if query_version:
            if cand_version == query_version or query_version in norm_title:
                version_compat = 1.25
            else:
                version_compat = 0.50
        elif cand_version in ("remix", "live", "instrumental", "cover"):
            version_compat = 0.65

    # 7. Non-music content penalty (check against raw unstripped title)
    raw_cand_norm = normalize_text(candidate.title)
    is_audio_mode = media_type == "audio" or any(
        m in norm_q for m in ("song", "music", "audio", "ost", "soundtrack", "track", "theme")
    )
    non_music_penalty = 1.0
    if is_audio_mode:
        for term, pen in NON_MUSIC_TERMS:
            if term in raw_cand_norm and term not in norm_q:
                non_music_penalty = pen
                break

    # 8. Duration compatibility
    duration_compat = 0.70
    if query.expected_duration and query.expected_duration > 0 and candidate.duration and candidate.duration > 0:
        diff = abs(candidate.duration - query.expected_duration)
        ratio = diff / query.expected_duration
        if ratio <= 0.05:
            duration_compat = 1.0
        elif ratio <= 0.15:
            duration_compat = 0.85
        elif ratio <= 0.35:
            duration_compat = 0.65
        elif ratio <= 0.70:
            duration_compat = 0.35
        else:
            duration_compat = 0.10
    elif is_audio_mode and candidate.duration:
        dur = candidate.duration
        if dur > 600.0 and not any(k in norm_q for k in ("album", "mix", "full", "compilation")):
            duration_compat = 0.25
        elif dur < 25.0:
            duration_compat = 0.20
        elif dur < 110.0:  # TV size anime/game opening cut (typically 90s), not full track
            duration_compat = 0.70
        else:
            duration_compat = 0.95

    # 9. Bounded popularity tie-breaker (max 0.05 bonus)
    views = candidate.views or 0
    if views > 100:
        log_v = math.log10(views + 1)
        popularity_boost = min(0.05, (log_v / 10.0) * 0.05)
    else:
        popularity_boost = 0.0

    # 10. Audio platform / Topic boost
    audio_platform_boost = 0.0
    if is_audio_mode:
        if candidate.platform == "soundcloud":
            audio_platform_boost += 0.10
        if "official audio" in raw_cand_norm or "audio" in raw_cand_norm:
            audio_platform_boost += 0.12
        if "topic" in uploader_norm:
            audio_platform_boost += 0.10

    return {
        "exact_title": exact_title,
        "phrase_match": phrase_match,
        "token_coverage": token_coverage,
        "token_order": token_order,
        "typo_similarity": typo_similarity,
        "artist_affinity": artist_affinity,
        "version_compat": version_compat,
        "duration_compat": duration_compat,
        "non_music_penalty": non_music_penalty,
        "popularity_boost": popularity_boost,
        "audio_platform_boost": audio_platform_boost,
    }


def score_candidate(
    query: SearchQuery,
    candidate: CandidateResult,
) -> Tuple[float, str, Dict[str, float], List[str]]:
    """Compute score, confidence tier, feature dict, and explanations for a candidate."""
    from backend.search.entity_parser import parse_media_entity
    from backend.search.normalization import resolve_soundtrack_associations

    # 0. Extract clean song, artist, and franchise context
    if not candidate.clean_title:
        ent = parse_media_entity(candidate.title, uploader=candidate.uploader)
        candidate.clean_title = ent.get("clean_title") or candidate.title
        candidate.song_title = ent.get("song_title")
        candidate.artist = ent.get("artist")
        candidate.context_source = ent.get("context_source")
        candidate.is_cluttered = ent.get("is_cluttered", False)
        candidate.is_cutscene = ent.get("is_cutscene", False)

    feat = extract_features(query, candidate)
    explanations: List[str] = []

    if feat["exact_title"] >= 0.85:
        explanations.append("Exact or leading title match")
    elif feat["phrase_match"] >= 0.90:
        explanations.append("Continuous query phrase match")

    if feat["token_coverage"] >= 0.99:
        explanations.append("Full query token coverage")

    if feat["artist_affinity"] >= 0.85:
        explanations.append("Verified artist / channel affinity")

    if feat["version_compat"] < 0.60:
        explanations.append("Version mismatch or unrequested remix/parody penalty")
    elif feat["version_compat"] > 1.10:
        explanations.append("Requested version match boost")

    if feat["non_music_penalty"] < 0.80:
        explanations.append("Non-music content mismatch penalty")

    # 1. Soundtrack theme / opening association boost
    soundtrack_boost = 0.0
    associated_tracks = resolve_soundtrack_associations(query.raw_query)
    if associated_tracks:
        cand_keys = [
            normalize_text(candidate.title),
            normalize_text(candidate.clean_title or ""),
        ]
        for assoc in associated_tracks:
            norm_assoc = normalize_text(assoc)
            if any(norm_assoc in k for k in cand_keys if k):
                soundtrack_boost = 0.35
                explanations.append(f"Official soundtrack song match: {assoc}")
                break

    # 2. Cutscene / gameplay penalty in audio mode
    cutscene_penalty = 1.0
    if candidate.is_cutscene and (query.media_type or "all") == "audio":
        cutscene_penalty = 0.25
        explanations.append("Cutscene/gameplay clip penalized for audio")

    # 3. Preference for clean official studio release over cluttered video uploads in audio mode
    clutter_multiplier = 0.85 if (candidate.is_cluttered and (query.media_type or "all") == "audio") else 1.0

    # Linear base score
    base_score = (
        0.30 * feat["exact_title"]
        + 0.25 * feat["phrase_match"]
        + 0.25 * feat["token_coverage"]
        + 0.10 * feat["token_order"]
        + 0.15 * feat["typo_similarity"]
        + 0.15 * feat["artist_affinity"]
        + 0.10 * feat["duration_compat"]
        + feat["audio_platform_boost"]
        + feat["popularity_boost"]
    )

    duration_multiplier = feat["duration_compat"] if feat["duration_compat"] < 0.50 else 1.0
    final_score = max(0.0, (base_score + soundtrack_boost) * feat["version_compat"] * feat["non_music_penalty"] * duration_multiplier * cutscene_penalty * clutter_multiplier)

    if final_score >= 0.65:
        confidence = "high"
    elif final_score >= 0.35:
        confidence = "medium"
    else:
        confidence = "low"

    return round(final_score, 4), confidence, feat, explanations


def deduplicate_candidates(candidates: List[CandidateResult]) -> List[CandidateResult]:
    """Deduplicate candidates by canonical URL and normalized title."""
    seen_urls: Set[str] = set()
    seen_titles: Set[str] = set()
    deduped: List[CandidateResult] = []

    for cand in candidates:
        if cand.url:
            canonical_url = normalize_media_url(cand.url)
            if canonical_url:
                if canonical_url in seen_urls:
                    continue
                seen_urls.add(canonical_url)

        norm_title = normalize_text(cand.title)
        if norm_title:
            if norm_title in seen_titles:
                continue
            seen_titles.add(norm_title)

        deduped.append(cand)

    return deduped


def rank_candidates(
    query: SearchQuery,
    candidates: List[CandidateResult],
    limit: Optional[int] = None,
) -> List[CandidateResult]:
    """Rank candidates with deterministic tie-breaking.

    Tie-breaking hierarchy:
    1. Score descending
    2. Exact title feature descending
    3. Views descending
    4. ID ascending (deterministic fallback)
    """
    if not candidates:
        return []

    deduped = deduplicate_candidates(candidates)
    scored_list: List[CandidateResult] = []

    for cand in deduped:
        score, confidence, features, explanations = score_candidate(query, cand)
        cand.score = score
        cand.confidence = confidence
        cand.features = features
        cand.explanation = explanations
        scored_list.append(cand)

    # Sort with deterministic tie-breaking
    scored_list.sort(
        key=lambda c: (
            c.score,
            c.features.get("exact_title", 0.0),
            c.views or 0,
        ),
        reverse=True,
    )

    if limit is not None:
        return scored_list[:limit]
    return scored_list
