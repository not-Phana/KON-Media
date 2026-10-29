"""Data models and schemas for KON Search 1 Rei dataset factory and ranking model."""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Dict, List, Optional
import time
import hashlib
import json


class RelevanceGrade(int, Enum):
    """Graded relevance scale for media search ranking.

    3 - Strong, direct, verified match for the intended media.
    2 - Relevant match (e.g. official remix, official live release, alternate canonical master).
    1 - Partially relevant (e.g. cover, tribute, soundtrack clip, related artist piece).
    0 - Irrelevant or misleading (noise, unrelated track, video clip when audio sought, parody).
    """
    IRRELEVANT = 0
    PARTIALLY_RELEVANT = 1
    RELEVANT = 2
    EXACT_MATCH = 3


class ProvenanceType(str, Enum):
    """Provenance tracking for data records."""
    VERIFIED_CANONICAL = "verified_canonical"
    SYNTHETIC_VARIATION = "synthetic_variation"
    HARD_NEGATIVE = "hard_negative"
    USER_FEEDBACK = "user_feedback"
    MANUALLY_REVIEWED = "manually_reviewed"


@dataclass
class QueryRecord:
    """Represents a search query with intent metadata."""
    query_id: str
    raw_query: str
    normalized_query: str
    media_type: str = "all"  # "audio", "video", "all"
    target_media_id: Optional[str] = None
    variation_type: str = "original"  # "original", "typo", "casing", "partial", "reordered", "soundtrack"


@dataclass
class CandidateRecord:
    """Represents a media candidate result."""
    candidate_id: str
    title: str
    artist_or_uploader: str = ""
    duration_seconds: Optional[float] = None
    media_type: str = "all"
    source_platform: str = "youtube"
    source_url: str = ""
    view_count: Optional[int] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LabeledExample:
    """A pair of query and candidate with assigned relevance grade and provenance."""
    example_id: str
    query: QueryRecord
    candidate: CandidateRecord
    grade: RelevanceGrade
    provenance: ProvenanceType
    confidence: float = 1.0
    group_id: str = ""  # Used for group-based split to avoid data leakage
    notes: str = ""
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "example_id": self.example_id,
            "query": asdict(self.query),
            "candidate": asdict(self.candidate),
            "grade": int(self.grade),
            "provenance": self.provenance.value,
            "confidence": self.confidence,
            "group_id": self.group_id,
            "notes": self.notes,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "LabeledExample":
        q = QueryRecord(**d["query"])
        c = CandidateRecord(**d["candidate"])
        return cls(
            example_id=d["example_id"],
            query=q,
            candidate=c,
            grade=RelevanceGrade(d["grade"]),
            provenance=ProvenanceType(d["provenance"]),
            confidence=float(d.get("confidence", 1.0)),
            group_id=d.get("group_id", ""),
            notes=d.get("notes", ""),
            created_at=float(d.get("created_at", time.time())),
        )


@dataclass
class DatasetManifest:
    """Metadata and integrity checksum for a versioned dataset."""
    dataset_version: str
    total_examples: int
    train_count: int
    val_count: int
    test_count: int
    queries_count: int
    grade_distribution: Dict[str, int]
    provenance_distribution: Dict[str, int]
    sha256_checksum: str
    created_at: str
    rejection_reasons: Dict[str, int] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ModelMetadata:
    """Metadata recording training configuration, versions, and performance."""
    model_name: str = "KON Search 1 Rei"
    model_version: str = "1.0.0"
    architecture: str = "GradientBoostingRanker"
    dataset_version: str = "v1.0.0"
    dataset_sha256: str = ""
    feature_schema: List[str] = field(default_factory=list)
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    training_samples: int = 0
    training_duration_seconds: float = 0.0
    software_versions: Dict[str, str] = field(default_factory=dict)
    metrics_baseline: Dict[str, float] = field(default_factory=dict)
    metrics_model: Dict[str, float] = field(default_factory=dict)
    status: str = "candidate"  # "candidate", "accepted", "rejected"
    trained_at: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
