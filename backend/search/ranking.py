"""Layer B: Multi-signal candidate ranking, version compatibility, and explainable scoring."""

import difflib
import math
from typing import Any, Dict, List, Optional
from backend.search.models import CandidateResult, RankerConfig, SearchQuery
from backend.search.normalization import (
    detect_version_hint,
    ngram_similarity,
    normalize_text,
    strip_media_noise,
    token_overlap_ratio,
)

# Unwanted version keywords when user requests original studio recording
DISQUALIFYING_VERSION_TERMS = {
    "parody": 0.40,
    "minecraft": 0.50,
    "roblox": 0.50,
    "cover": 0.25,
    "tribute": 0.25,
    "8d audio": 0.30,
    "slowed": 0.25,
    "nightcore": 0.30,
    "earrape": 0.50,
    "bass boosted": 0.20,
}

NON_MUSIC_CONTENT_TERMS = {
    "documentary": 0.20,
    "trailer": 0.20,
    "film trailer": 0.20,
    "teaser": 0.20,
    "tutorial": 0.20,
    "movie": 0.30,
    "full movie": 0.20,
    "movie clip": 0.25,
    "clip": 0.30,
    "scene": 0.25,
    "ending scene": 0.25,
    "gameplay": 0.20,
    "walkthrough": 0.20,
    "review": 0.25,
    "interview": 0.25,
    "podcast": 0.30,
    "news report": 0.20,
}


def score_artist_affinity(
    candidate: CandidateResult,
    expected_artist: Optional[str],
    query_artist: Optional[str],
) -> float:
    """Score how well candidate uploader or channel matches the expected artist."""
    target_artist = expected_artist or query_artist
    if not target_artist:
        return 0.5  # Neutral when no artist is identifiable

    norm_target = normalize_text(target_artist)
    norm_uploader = normalize_text(candidate.uploader)
    norm_title = normalize_text(candidate.title)

    # 1. Direct channel/uploader match (e.g. "Queen Official", "DaftPunkVEVO")
    if norm_target in norm_uploader or norm_uploader in norm_target:
        return 1.0

    # 2. Artist present at start of title (e.g. "Daft Punk - Get Lucky")
    if norm_title.startswith(norm_target):
        return 0.9

    # 3. Fuzzy similarity between artist and uploader
    sim = ngram_similarity(norm_target, norm_uploader, n=3)
    if sim > 0.6:
        return 0.85

    return 0.3


def score_version_compatibility(
    candidate: CandidateResult,
    query_version_hint: Optional[str],
    query_text: str = "",
    media_type: str = "all",
) -> float:
    """Evaluate version compatibility between query intent and candidate.

    Returns a multiplier from 0.1 to 1.3:
    - If user wanted remix/live/instrumental and candidate matches: boost.
    - If user wanted remix/live/instrumental and candidate is studio: penalize.
    - If user wanted standard release and candidate has unwanted mods (parody/cover/remix): heavy penalty.
    - If query indicates a song/lyrics or media_type is audio and candidate is documentary/trailer/clip: content mismatch penalty.
    """
    cand_title_norm = normalize_text(candidate.title)
    cand_version = detect_version_hint(candidate.title)
    norm_q = normalize_text(query_text)

    # Check for non-music content mismatch (e.g. Documentary, Trailer, Clip, Scene) when user asked for audio/song
    if media_type == "audio" or any(m in norm_q for m in ("song", "lyrics", "audio", "track", "music", "ost", "theme")):
        for term, penalty in NON_MUSIC_CONTENT_TERMS.items():
            if term in cand_title_norm and term not in norm_q:
                return penalty

    # Check for hard disqualifying terms (parody, minecraft parody, earrape, etc.)
    for term, penalty in DISQUALIFYING_VERSION_TERMS.items():
        if term in cand_title_norm:
            if not query_version_hint or term not in query_version_hint:
                return penalty  # e.g. 0.4 for parody

    if query_version_hint:
        # User explicitly asked for a version (e.g. "remix", "live", "instrumental")
        if cand_version == query_version_hint or query_version_hint in cand_title_norm:
            return 1.25  # Strong boost for matching requested version
        else:
            return 0.45  # Penalize studio or mismatched versions when specific version was requested
    else:
        # Standard studio track requested
        if cand_version in ("remix", "live", "instrumental", "acoustic", "cover"):
            return 0.60  # Mild penalty for alternate versions when standard release is wanted
        return 1.0  # Clean standard version match


def score_duration_compatibility(
    candidate_duration: Optional[float],
    expected_duration: Optional[float],
    query_text: str = "",
) -> float:
    """Score duration proximity. Heavy penalty for drastic divergences (e.g. 10hr loop or 15s clip)."""
    norm_q = normalize_text(query_text)

    if expected_duration and expected_duration > 0 and candidate_duration and candidate_duration > 0:
        diff = abs(candidate_duration - expected_duration)
        ratio = diff / expected_duration

        if ratio <= 0.05:  # within 5%
            return 1.0
        if ratio <= 0.15:  # within 15%
            return 0.85
        if ratio <= 0.35:  # within 35%
            return 0.65
        if ratio <= 0.70:  # within 70%
            return 0.35
        return 0.10  # Extreme divergence

    # When no expected duration is known, but query mentions song/lyrics
    if any(m in norm_q for m in ("song", "lyrics", "audio", "track")) and candidate_duration:
        # Most songs are 2 - 7 minutes. Greater than 10 minutes (600s) indicates a documentary/podcast/loop
        if candidate_duration > 600.0 and not any(term in norm_q for term in ("album", "mix", "full", "podcast", "documentary")):
            return 0.20

    return 0.7  # Neutral baseline


def rank_candidates(
    query: SearchQuery,
    candidates: List[CandidateResult],
    config: Optional[RankerConfig] = None,
    feedback_lookup: Optional[Dict[str, str]] = None,
    learning_model: Optional[Any] = None,
) -> List[CandidateResult]:
    """Score and rank candidates using explainable multi-signal features and self-learning neural associations."""
    if not candidates:
        return []

    cfg = config or RankerConfig()
    norm_query = query.normalized_query or normalize_text(query.raw_query)

    ranked_results: List[CandidateResult] = []

    for cand in candidates:
        features: Dict[str, float] = {}
        explanation: List[str] = []

        clean_title = strip_media_noise(cand.title)
        norm_title = normalize_text(clean_title)

        # 1. Exact string and sequence matching
        if norm_query in norm_title or norm_title in norm_query:
            exact_score = 1.0
            explanation.append("Exact title sequence match")
        else:
            matcher = difflib.SequenceMatcher(None, norm_query, norm_title)
            exact_score = matcher.ratio()
        features["exact_title"] = exact_score

        # 2. Fuzzy n-gram similarity (typo tolerance)
        fuzzy_score = ngram_similarity(norm_query, norm_title, n=3)
        features["fuzzy_title"] = fuzzy_score

        # 3. Token overlap ratio
        tok_score = token_overlap_ratio(norm_query, norm_title)
        features["token_overlap"] = tok_score

        # 4. Artist / Channel Affinity
        artist_score = score_artist_affinity(
            cand,
            expected_artist=query.expected_artist,
            query_artist=query.detected_artist,
        )
        features["artist_affinity"] = artist_score
        if artist_score >= 0.85:
            explanation.append("Verified artist/channel match")

        # 5. Version Compatibility
        version_mod = score_version_compatibility(
            cand,
            query_version_hint=query.version_hint,
            query_text=query.raw_query,
            media_type=query.media_type,
        )
        features["version_compat"] = version_mod
        if version_mod < 0.6:
            explanation.append("Version mismatch penalty applied")
        elif version_mod > 1.1:
            explanation.append("Requested version match boost")

        # 6. Duration Compatibility
        duration_score = score_duration_compatibility(cand.duration, query.expected_duration, query.raw_query)
        features["duration_compat"] = duration_score

        # 7. Historical Feedback Boost (Layer D)
        feedback_boost = 0.0
        if feedback_lookup and feedback_lookup.get(norm_query) == cand.id:
            feedback_boost = 1.0
            explanation.append("Verified user match from historical feedback")
        features["feedback_boost"] = feedback_boost

        # 8. Media Type & Soundtrack / Song Association Boost
        from backend.search.normalization import resolve_soundtrack_associations
        associated_songs = resolve_soundtrack_associations(query.raw_query)
        assoc_boost = 0.0
        if associated_songs:
            for assoc in associated_songs:
                norm_assoc = normalize_text(assoc)
                if norm_assoc in norm_title or any(w in norm_title for w in norm_assoc.split() if len(w) > 3):
                    assoc_boost = 0.35
                    explanation.append(f"Associated song: {assoc}")
                    break

        audio_affinity_boost = 0.0
        if query.media_type == "audio":
            if cand.platform == "soundcloud":
                audio_affinity_boost += 0.12
                explanation.append("Native audio platform")
            if "official audio" in norm_title or "audio" in norm_title:
                audio_affinity_boost += 0.15
                explanation.append("Official audio release")
            if "topic" in normalize_text(cand.uploader):
                audio_affinity_boost += 0.10
                explanation.append("Verified artist topic channel")

        # 9. Learned Neural Association & Semantic Embedding
        learned_boost = 0.0
        if learning_model is not None:
            try:
                prob, semantic_sim = learning_model.predict_score(features, norm_query, cand.title)
                features["semantic_similarity"] = semantic_sim
                sem_weight = learning_model.weights.get("semantic_embedding", 0.30)
                learned_boost = sem_weight * semantic_sim
                if semantic_sim >= 0.45:
                    explanation.append(f"Learned neural affinity ({int(semantic_sim * 100)}%)")
                if query.media_type == "audio" and semantic_sim >= 0.50:
                    learned_boost += 0.35  # High-priority boost for matching soundtrack/theme song
                    explanation.append(f"High-confidence song theme match ({int(semantic_sim * 100)}%)")
            except Exception:
                pass

        # Linear weighted composite score
        base_score = (
            cfg.weight_exact_title * exact_score
            + cfg.weight_fuzzy_title * fuzzy_score
            + cfg.weight_token_overlap * tok_score
            + cfg.weight_artist_match * artist_score
            + cfg.weight_duration_match * duration_score
            + cfg.weight_feedback_boost * feedback_boost
            + assoc_boost
            + audio_affinity_boost
            + learned_boost
        )

        # Multiply by version modifier (e.g. 0.4 for parody, 1.25 for matching remix)
        final_score = base_score * version_mod
        cand.score = final_score
        cand.features = features
        cand.explanation = explanation

        # Assign confidence tiers
        if final_score >= cfg.high_confidence_threshold:
            cand.confidence = "high"
        elif final_score >= cfg.min_confidence_threshold:
            cand.confidence = "medium"
        else:
            cand.confidence = "low"

        ranked_results.append(cand)

    # Sort descending by final score
    ranked_results.sort(key=lambda c: c.score, reverse=True)
    return ranked_results
