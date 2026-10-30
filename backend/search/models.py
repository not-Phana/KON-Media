"""Data models for KON Media search engine, candidate results, ranking, and feedback."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CandidateResult:
    """A search candidate retrieved from a media provider."""
    id: str
    title: str
    uploader: str = ""
    url: str = ""
    duration: Optional[float] = None
    duration_formatted: str = ""
    thumbnail: Optional[str] = None
    platform: str = "youtube"
    views: Optional[int] = None
    score: float = 0.0
    confidence: str = "low"  # "low", "medium", "high"
    features: Dict[str, float] = field(default_factory=dict)
    explanation: List[str] = field(default_factory=list)
    is_verified_match: bool = False
    clean_title: Optional[str] = None
    song_title: Optional[str] = None
    artist: Optional[str] = None
    context_source: Optional[str] = None
    is_cluttered: bool = False
    is_cutscene: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "clean_title": self.clean_title or self.title,
            "song_title": self.song_title,
            "artist": self.artist,
            "context_source": self.context_source,
            "is_cluttered": self.is_cluttered,
            "is_cutscene": self.is_cutscene,
            "uploader": self.uploader,
            "url": self.url,
            "duration": self.duration,
            "duration_formatted": self.duration_formatted,
            "thumbnail": self.thumbnail,
            "platform": self.platform,
            "views": self.views,
            "score": round(self.score, 4),
            "confidence": self.confidence,
            "features": {k: round(v, 4) for k, v in self.features.items()},
            "explanation": self.explanation,
            "is_verified_match": self.is_verified_match,
        }


@dataclass
class SearchQuery:
    """Parsed and normalized search query with intent signals."""
    raw_query: str
    normalized_query: str = ""
    detected_artist: Optional[str] = None
    detected_title: Optional[str] = None
    version_hint: Optional[str] = None  # e.g., "live", "remix", "instrumental", "acoustic", "cover", "slowed", "sped_up"
    qualifier: Optional[str] = None  # e.g., "jersey club", "speed up", "slowed + reverb", "live aid"
    edition: Optional[str] = None  # e.g., "version", "deluxe", "remaster"
    expected_duration: Optional[float] = None
    expected_artist: Optional[str] = None
    expected_title: Optional[str] = None
    media_type: str = "all"  # "all", "audio", "video"
    exact_phrases: List[str] = field(default_factory=list)


@dataclass
class RankerConfig:
    """Weights and thresholds for candidate ranking."""
    weight_exact_title: float = 0.35
    weight_fuzzy_title: float = 0.25
    weight_token_overlap: float = 0.15
    weight_artist_match: float = 0.15
    weight_version_match: float = 0.15
    weight_duration_match: float = 0.10
    weight_feedback_boost: float = 0.20
    penalty_version_mismatch: float = 0.30
    penalty_duration_divergence: float = 0.20
    min_confidence_threshold: float = 0.35
    high_confidence_threshold: float = 0.70


@dataclass
class SearchFeedbackEntry:
    """User feedback or verified ground truth for search results."""
    query: str
    selected_id: str
    selected_title: str
    selected_url: str
    is_mismatch: bool = False
    reason: Optional[str] = None
    timestamp: str = ""
    provider: str = "youtube"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "query": self.query,
            "selected_id": self.selected_id,
            "selected_title": self.selected_title,
            "selected_url": self.selected_url,
            "is_mismatch": self.is_mismatch,
            "reason": self.reason,
            "timestamp": self.timestamp,
            "provider": self.provider,
        }


@dataclass
class SearchSuggestion:
    """A search autocomplete suggestion or intelligent song discovery."""
    id: str
    query: str
    title: str
    artist: Optional[str] = None
    type: str = "query"  # "song" or "query"
    thumbnail: Optional[str] = None
    duration: Optional[float] = None
    url: Optional[str] = None
    match_reason: str = "Suggested query"
    score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "title": self.title,
            "artist": self.artist,
            "type": self.type,
            "thumbnail": self.thumbnail,
            "duration": self.duration,
            "url": self.url,
            "match_reason": self.match_reason,
            "score": round(self.score, 4),
        }
