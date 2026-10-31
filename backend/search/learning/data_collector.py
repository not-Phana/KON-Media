"""Learning Data Collector for KON Search 1.2 Rei & Rei Flash.

Collects real-world interaction signals from user search sessions, including:
- Positive: selects, audio preview starts, prolonged listening, favorites, downloads.
- Negative: quick skips (<5s), query reformulations, explicit mismatch reports.
- Multi-session consensus: repeated choices for similar queries reinforce confidence.

Privacy & Safety:
- Stores data strictly locally in state/learning_interactions.json.
- Zero personal information, account IDs, or IP addresses collected.
- Provides programmatic controls to inspect, export, clear, and disable data collection.
"""

import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.config import STATE_DIR
from backend.storage.storage import AtomicJsonStore
from backend.search.normalization import normalize_text

log = logging.getLogger("kon_data_collector")


class LearningDataCollector:
    """Manages collection, filtering, and export of search interaction signals."""

    def __init__(self, state_dir: Path = STATE_DIR):
        self.state_dir = state_dir
        self.file_path = state_dir / "learning_interactions.json"
        self.store = AtomicJsonStore(self.file_path, default_value=[])
        self.settings_file = state_dir / "learning_settings.json"
        self.settings_store = AtomicJsonStore(self.settings_file, default_value={"enabled": True})
        self._enabled = self.settings_store.load().get("enabled", True)

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> bool:
        """Enable or disable learning data collection."""
        self._enabled = bool(enabled)
        self.settings_store.save({"enabled": self._enabled})
        log.info("Learning data collector enabled state changed to: %s", self._enabled)
        return self._enabled

    def record_event(
        self,
        query: str,
        candidate_id: str,
        candidate_title: str,
        event_type: str,
        candidate_url: Optional[str] = None,
        listen_duration: Optional[float] = None,
        track_duration: Optional[float] = None,
        position_rank: Optional[int] = None,
        engine_mode: str = "rei",
        reason: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Record a single interaction event with noise filtering."""
        if not self._enabled:
            return None

        clean_query = normalize_text(query).strip()
        if not clean_query or len(clean_query) < 2:
            return None
        if not candidate_title or len(candidate_title.strip()) < 2:
            return None

        # Standardize event type
        valid_types = {
            "select", "preview", "listen", "favorite", "download",
            "skip", "reformulation", "mismatch"
        }
        event_norm = event_type.lower().strip()
        if event_norm not in valid_types:
            event_norm = "select"

        # Calculate signal quality & label
        # 1.0 = positive (target is what user wanted), 0.0 = negative (distractor / unwanted)
        label = 1.0
        weight = 1.0

        if event_norm == "favorite":
            label = 1.0
            weight = 1.5  # Adding to favorites is a very strong endorsement
        elif event_norm == "download":
            label = 1.0
            weight = 1.3  # Downloading indicates confirmed target
        elif event_norm == "listen":
            # If user listened to more than 20 seconds or > 40% of track, strong positive
            if listen_duration and ((track_duration and listen_duration / max(track_duration, 1) > 0.4) or listen_duration >= 20.0):
                label = 1.0
                weight = 1.2
            elif listen_duration and listen_duration < 4.0:
                # Discard very brief previews (<4s) unless explicit skip
                return None
            else:
                label = 1.0
                weight = 1.0
        elif event_norm == "preview":
            label = 1.0
            weight = 0.9
        elif event_norm == "select":
            label = 1.0
            weight = 0.8
        elif event_norm == "skip":
            # Only count as negative if user heard under 5s on a top 3 result
            if position_rank and position_rank <= 3 and listen_duration and listen_duration < 5.0:
                label = 0.0
                weight = 0.7
            else:
                return None  # Don't treat arbitrary skips as negative
        elif event_norm == "reformulation":
            label = 0.0
            weight = 0.5  # User changed search query without interacting
        elif event_norm == "mismatch":
            label = 0.0
            weight = 1.5  # User explicitly reported incorrect result

        entry = {
            "id": f"int_{datetime.datetime.now(datetime.timezone.utc).timestamp():.6f}",
            "query": clean_query,
            "candidate_id": candidate_id or "",
            "candidate_title": candidate_title.strip(),
            "candidate_url": candidate_url or "",
            "event_type": event_norm,
            "label": label,
            "weight": weight,
            "listen_duration": round(listen_duration, 1) if listen_duration is not None else None,
            "track_duration": round(track_duration, 1) if track_duration is not None else None,
            "position_rank": position_rank,
            "engine_mode": engine_mode.lower() if engine_mode else "rei",
            "reason": reason,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        entries = self.store.load()
        entries.insert(0, entry)
        # Cap to 2000 events to remain lightweight
        if len(entries) > 2000:
            entries = entries[:2000]
        self.store.save(entries)
        return entry

    def get_all(self) -> List[Dict[str, Any]]:
        """Return all recorded interaction records."""
        return self.store.load()

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate statistics of collected data."""
        entries = self.get_all()
        by_type: Dict[str, int] = {}
        positive_count = 0
        negative_count = 0

        for e in entries:
            t = e.get("event_type", "select")
            by_type[t] = by_type.get(t, 0) + 1
            if e.get("label", 1.0) >= 0.5:
                positive_count += 1
            else:
                negative_count += 1

        return {
            "total_events": len(entries),
            "is_enabled": self._enabled,
            "positive_events": positive_count,
            "negative_events": negative_count,
            "by_type": by_type,
            "latest_event_at": entries[0]["timestamp"] if entries else None,
        }

    def get_clean_training_examples(self, min_weight: float = 0.5) -> List[Tuple[str, str, float, float]]:
        """Extract clean, deduplicated, and validated training examples.

        Returns list of tuples: (query, candidate_title, consensus_label, aggregate_weight)
        Consolidates multiple events for identical (query, candidate) pairs.
        """
        entries = self.get_all()
        aggregated: Dict[Tuple[str, str], Dict[str, float]] = {}

        for e in entries:
            q = e.get("query", "").strip()
            title = e.get("candidate_title", "").strip()
            if not q or not title:
                continue

            pair = (q, title)
            w = float(e.get("weight", 1.0))
            lab = float(e.get("label", 1.0))

            if pair not in aggregated:
                aggregated[pair] = {"weighted_sum": 0.0, "total_weight": 0.0, "count": 0}

            aggregated[pair]["weighted_sum"] += lab * w
            aggregated[pair]["total_weight"] += w
            aggregated[pair]["count"] += 1

        examples: List[Tuple[str, str, float, float]] = []
        for (q, title), stats in aggregated.items():
            tot_w = stats["total_weight"]
            if tot_w < min_weight:
                continue

            consensus = stats["weighted_sum"] / tot_w
            # Binary threshold with soft boundary
            final_label = 1.0 if consensus >= 0.5 else 0.0
            examples.append((q, title, final_label, round(tot_w, 2)))

        return examples

    def export_data(self) -> Dict[str, Any]:
        """Export collected data with full metadata."""
        entries = self.get_all()
        return {
            "version": "1.0.0",
            "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "count": len(entries),
            "interactions": entries,
        }

    def clear(self) -> None:
        """Clear all collected learning interactions."""
        self.store.save([])
        log.info("Learning interactions cleared by user.")


# Singleton instance
_shared_data_collector: Optional[LearningDataCollector] = None


def get_learning_data_collector() -> LearningDataCollector:
    global _shared_data_collector
    if _shared_data_collector is None:
        _shared_data_collector = LearningDataCollector()
    return _shared_data_collector
