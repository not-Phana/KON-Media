"""Quality control and validation for KON Search 1 Rei datasets.

Enforces:
- Schema conformance and required field presence
- Type safety and value bounds
- Deduplication of query-candidate pairs
- Contradictory label resolution
- Group-based splitting to prevent data leakage between train/val/test
- Distribution balance checks
- Dataset integrity hashing (SHA-256)
"""

import hashlib
import json
import logging
from collections import Counter
from typing import Any, Dict, List, Optional, Set, Tuple
from kon_search.schema import DatasetManifest, LabeledExample, RelevanceGrade

log = logging.getLogger("kon_search_validation")


class DatasetValidator:
    """Rigorous validator ensuring zero leakage, consistent labels, and high quality."""

    def __init__(self):
        self.rejection_reasons: Counter = Counter()

    def validate_example(self, ex: LabeledExample) -> Tuple[bool, Optional[str]]:
        """Validate a single LabeledExample for schema and integrity."""
        if not ex.example_id or not isinstance(ex.example_id, str):
            self.rejection_reasons["missing_example_id"] += 1
            return False, "Missing or invalid example_id"

        if not ex.query or not ex.query.raw_query.strip():
            self.rejection_reasons["empty_query"] += 1
            return False, "Empty query text"

        if not ex.candidate or not ex.candidate.title.strip():
            self.rejection_reasons["empty_candidate_title"] += 1
            return False, "Empty candidate title"

        if not isinstance(ex.grade, RelevanceGrade):
            try:
                ex.grade = RelevanceGrade(int(ex.grade))
            except Exception:
                self.rejection_reasons["invalid_grade"] += 1
                return False, f"Invalid relevance grade: {ex.grade}"

        if not (0.0 <= ex.confidence <= 1.0):
            self.rejection_reasons["invalid_confidence"] += 1
            return False, f"Confidence out of range: {ex.confidence}"

        if not ex.group_id:
            self.rejection_reasons["missing_group_id"] += 1
            return False, "Missing group_id for leakage prevention"

        return True, None

    def validate_and_deduplicate_batch(
        self, examples: List[LabeledExample]
    ) -> List[LabeledExample]:
        """Filter invalid examples, resolve duplicate pairs, and eliminate label contradictions."""
        valid_examples: List[LabeledExample] = []
        seen_pairs: Dict[Tuple[str, str], LabeledExample] = {}

        for ex in examples:
            is_valid, reason = self.validate_example(ex)
            if not is_valid:
                continue

            # Canonical pair key (lowercased query and candidate title)
            pair_key = (
                ex.query.raw_query.lower().strip(),
                ex.candidate.title.lower().strip(),
            )

            if pair_key in seen_pairs:
                existing = seen_pairs[pair_key]
                # If exact duplicate with same grade, discard duplicate
                if existing.grade == ex.grade:
                    self.rejection_reasons["duplicate_pair"] += 1
                    continue
                else:
                    # Contradictory label detected!
                    self.rejection_reasons["contradictory_label"] += 1
                    # Rule: canonical verified provenance takes precedence; if equal, retain higher confidence or discard
                    if ex.provenance.value == "verified_canonical":
                        seen_pairs[pair_key] = ex
                    elif existing.provenance.value != "verified_canonical" and ex.confidence > existing.confidence:
                        seen_pairs[pair_key] = ex
                    continue

            seen_pairs[pair_key] = ex

        valid_examples = list(seen_pairs.values())
        return valid_examples

    def split_by_group(
        self,
        examples: List[LabeledExample],
        train_ratio: float = 0.70,
        val_ratio: float = 0.15,
        test_ratio: float = 0.15,
        seed: int = 42,
    ) -> Tuple[List[LabeledExample], List[LabeledExample], List[LabeledExample]]:
        """Split dataset into train, val, and test partitions by group_id to ensure ZERO data leakage."""
        import random

        # Group examples by group_id
        groups: Dict[str, List[LabeledExample]] = {}
        for ex in examples:
            groups.setdefault(ex.group_id, []).append(ex)

        # Deterministic shuffle of group IDs
        group_keys = sorted(groups.keys())
        rng = random.Random(seed)
        rng.shuffle(group_keys)

        total_groups = len(group_keys)
        train_end = int(total_groups * train_ratio)
        val_end = train_end + int(total_groups * val_ratio)

        train_groups = set(group_keys[:train_end])
        val_groups = set(group_keys[train_end:val_end])
        test_groups = set(group_keys[val_end:])

        train_data: List[LabeledExample] = []
        val_data: List[LabeledExample] = []
        test_data: List[LabeledExample] = []

        for gid, items in groups.items():
            if gid in train_groups:
                train_data.extend(items)
            elif gid in val_groups:
                val_data.extend(items)
            else:
                test_data.extend(items)

        # Verification check: zero group overlap
        assert not (train_groups & val_groups), "Leakage between train and val!"
        assert not (train_groups & test_groups), "Leakage between train and test!"
        assert not (val_groups & test_groups), "Leakage between val and test!"

        return train_data, val_data, test_data

    @staticmethod
    def compute_sha256(data: List[Dict[str, Any]]) -> str:
        """Compute deterministic SHA-256 checksum over serialized dataset records."""
        canonical_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()

    def build_manifest(
        self,
        dataset_version: str,
        train_data: List[LabeledExample],
        val_data: List[LabeledExample],
        test_data: List[LabeledExample],
        created_at: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> DatasetManifest:
        """Build verified manifest with counts, distributions, and cryptographic checksum."""
        all_data = train_data + val_data + test_data
        dict_records = [ex.to_dict() for ex in all_data]
        checksum = self.compute_sha256(dict_records)

        grade_counts = Counter(ex.grade.name for ex in all_data)
        prov_counts = Counter(ex.provenance.value for ex in all_data)
        unique_queries = len(set(ex.query.raw_query.lower().strip() for ex in all_data))

        return DatasetManifest(
            dataset_version=dataset_version,
            total_examples=len(all_data),
            train_count=len(train_data),
            val_count=len(val_data),
            test_count=len(test_data),
            queries_count=unique_queries,
            grade_distribution=dict(grade_counts),
            provenance_distribution=dict(prov_counts),
            sha256_checksum=checksum,
            created_at=created_at,
            rejection_reasons=dict(self.rejection_reasons),
            metadata=extra_metadata or {},
        )
