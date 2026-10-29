"""Feature extractor generating rich, explainable ML ranking vectors for KON Search 1 Rei."""

import difflib
import math
import re
from typing import Any, Dict, List, Set
from kon_search.schema import CandidateRecord, QueryRecord

FEATURE_NAMES = [
    "exact_title_match",
    "exact_artist_match",
    "token_overlap_jaccard",
    "token_containment_ratio",
    "char_3gram_similarity",
    "seq_matcher_ratio",
    "query_to_artist_ratio",
    "title_length_ratio",
    "media_type_audio_match",
    "media_type_video_match",
    "non_music_clip_penalty",
    "version_live_indicator",
    "version_remix_indicator",
    "version_cover_indicator",
    "view_count_log_scale",
]


def normalize_text(text: str) -> str:
    """Normalize text: lowercase, remove special characters, collapse whitespace."""
    if not text:
        return ""
    clean = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(clean.split())


def extract_char_ngrams(s: str, n: int = 3) -> Set[str]:
    """Extract character n-grams."""
    if len(s) < n:
        return {s} if s else set()
    return {s[i : i + n] for i in range(len(s) - n + 1)}


class RankingFeatureExtractor:
    """Transforms (Query, Candidate) pairs into numerical feature arrays for ML ranking."""

    def __init__(self):
        self.feature_names = list(FEATURE_NAMES)

    def extract_features(self, query: QueryRecord, candidate: CandidateRecord) -> Dict[str, float]:
        """Extract multi-signal ranking features."""
        norm_q = normalize_text(query.raw_query)
        norm_t = normalize_text(candidate.title)
        norm_a = normalize_text(candidate.artist_or_uploader)

        q_tokens = set(norm_q.split())
        t_tokens = set(norm_t.split())
        a_tokens = set(norm_a.split())

        # 1. Exact matches
        exact_title = 1.0 if norm_q == norm_t or norm_q in norm_t else 0.0
        exact_artist = 1.0 if (norm_a and (norm_a in norm_q or any(tok in a_tokens for tok in q_tokens if len(tok) > 3))) else 0.0

        # 2. Token overlap metrics
        union_tokens = q_tokens | t_tokens
        intersect_tokens = q_tokens & t_tokens
        jaccard = len(intersect_tokens) / len(union_tokens) if union_tokens else 0.0
        containment = len(intersect_tokens) / len(q_tokens) if q_tokens else 0.0

        # 3. Fuzzy character n-gram similarity
        q_ngrams = extract_char_ngrams(norm_q, n=3)
        t_ngrams = extract_char_ngrams(norm_t, n=3)
        ngram_union = q_ngrams | t_ngrams
        ngram_sim = len(q_ngrams & t_ngrams) / len(ngram_union) if ngram_union else 0.0

        # 4. Sequence matcher ratios
        seq_ratio = difflib.SequenceMatcher(None, norm_q, norm_t).ratio()
        artist_ratio = difflib.SequenceMatcher(None, norm_q, norm_a).ratio() if norm_a else 0.0

        # 5. Length ratio
        len_q = len(norm_q)
        len_t = len(norm_t)
        len_ratio = (min(len_q, len_t) / max(len_q, len_t)) if max(len_q, len_t) > 0 else 0.0

        # 6. Media type alignment
        q_is_audio = query.media_type in ("audio", "all")
        c_is_audio = candidate.media_type == "audio"
        q_is_video = query.media_type in ("video", "all")
        c_is_video = candidate.media_type == "video"

        audio_match = 1.0 if (q_is_audio and c_is_audio) else 0.0
        video_match = 1.0 if (q_is_video and c_is_video) else 0.0

        # 7. Non-music video clip indicator (clip, scene, review, trailer)
        non_music_keywords = ("clip", "scene", "ending scene", "review", "trailer", "breakdown", "analysis", "interview")
        is_clip_title = any(kw in norm_t for kw in non_music_keywords)
        non_music_penalty = 1.0 if (is_clip_title and query.media_type == "audio") else 0.0

        # 8. Version indicators
        live_ind = 1.0 if ("live" in norm_t or "concert" in norm_t) else 0.0
        remix_ind = 1.0 if ("remix" in norm_t or "mix" in norm_t) else 0.0
        cover_ind = 1.0 if any(kw in norm_t for kw in ("cover", "piano", "acoustic", "karaoke", "instrumental")) else 0.0

        # 9. View count log scale
        views = candidate.view_count or 0
        view_scale = min(1.0, math.log10(1 + views) / 8.0) if views > 0 else 0.0

        return {
            "exact_title_match": exact_title,
            "exact_artist_match": exact_artist,
            "token_overlap_jaccard": round(jaccard, 4),
            "token_containment_ratio": round(containment, 4),
            "char_3gram_similarity": round(ngram_sim, 4),
            "seq_matcher_ratio": round(seq_ratio, 4),
            "query_to_artist_ratio": round(artist_ratio, 4),
            "title_length_ratio": round(len_ratio, 4),
            "media_type_audio_match": audio_match,
            "media_type_video_match": video_match,
            "non_music_clip_penalty": non_music_penalty,
            "version_live_indicator": live_ind,
            "version_remix_indicator": remix_ind,
            "version_cover_indicator": cover_ind,
            "view_count_log_scale": round(view_scale, 4),
        }

    def extract_vector(self, query: QueryRecord, candidate: CandidateRecord) -> List[float]:
        """Return features in ordered list matching FEATURE_NAMES."""
        feats = self.extract_features(query, candidate)
        return [feats[name] for name in self.feature_names]
