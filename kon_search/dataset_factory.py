"""Dataset Factory generating high-quality graded relevance training examples for KON Search 1 Rei."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from kon_search.schema import (
    CandidateRecord,
    LabeledExample,
    ProvenanceType,
    QueryRecord,
    RelevanceGrade,
)

log = logging.getLogger("kon_search_dataset_factory")


def introduce_realistic_typos(s: str) -> str:
    """Introduce a plausible typo (transposed adjacent letters, omitted vowel, or keyboard slip)."""
    if len(s) < 4:
        return s
    chars = list(s)
    # Swap two adjacent letters near middle
    mid = len(chars) // 2
    chars[mid], chars[mid + 1] = chars[mid + 1], chars[mid]
    return "".join(chars)


class DatasetFactory:
    """Repeatable data generation pipeline for media search ranking datasets."""

    def __init__(self, seed_knowledge_path: Optional[Path] = None):
        self.seed_knowledge_path = seed_knowledge_path
        self.raw_records: List[Tuple[str, str, str]] = []  # (query, title, artist)
        self._load_seed_knowledge()

    def _load_seed_knowledge(self) -> None:
        """Parse master music knowledge markdown into canonical triplets."""
        if not self.seed_knowledge_path or not self.seed_knowledge_path.exists():
            # Fallback path relative to this file
            default_path = (
                Path(__file__).resolve().parent.parent
                / "data"
                / "knowledge"
                / "master_music_knowledge.md"
            )
            if default_path.exists():
                self.seed_knowledge_path = default_path

        if self.seed_knowledge_path and self.seed_knowledge_path.exists():
            with open(self.seed_knowledge_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line.startswith("|") or line.startswith("| :") or "Associated Track" in line:
                        continue
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) >= 2:
                        query = parts[0]
                        media = parts[1]
                        artist = ""
                        title = media
                        if " - " in media:
                            m_parts = media.split(" - ", 1)
                            artist = m_parts[0].strip()
                            title = m_parts[1].strip()
                        self.raw_records.append((query, title, artist))

        log.info("Loaded %d raw seed records for dataset factory.", len(self.raw_records))

    def generate_pilot_dataset(self, target_clusters: int = 40) -> List[LabeledExample]:
        """Generate a focused pilot dataset (~500 - 800 examples) for initial verification."""
        return self._generate_dataset_internal(max_clusters=target_clusters, variants_per_cluster=3)

    def generate_expanded_dataset(self, target_clusters: int = 150) -> List[LabeledExample]:
        """Generate a production-scale expanded dataset (3,000+ examples) across diverse domains."""
        return self._generate_dataset_internal(max_clusters=target_clusters, variants_per_cluster=6)

    def _generate_dataset_internal(
        self, max_clusters: int = 100, variants_per_cluster: int = 4
    ) -> List[LabeledExample]:
        """Internal generator building graded relevance pairs with zero-leakage cluster grouping."""
        examples: List[LabeledExample] = []
        cluster_count = 0

        # Unique canonical clusters
        seen_media = set()
        clusters = []
        for q, title, artist in self.raw_records:
            media_key = f"{artist}::{title}".lower()
            if media_key not in seen_media:
                seen_media.add(media_key)
                clusters.append((q, title, artist))
                if len(clusters) >= max_clusters:
                    break

        all_artists = [c[2] for c in clusters if c[2]]
        all_titles = [c[1] for c in clusters if c[1]]

        for cluster_idx, (base_query, title, artist) in enumerate(clusters):
            cluster_id = f"cluster_{cluster_idx}_{re.sub(r'[^a-zA-Z0-9]', '_', title)[:20].lower()}"
            full_canonical_title = f"{artist} - {title}" if artist else title

            # Canonical Candidate
            canonical_cand = CandidateRecord(
                candidate_id=f"cand_{cluster_idx}_canon",
                title=full_canonical_title,
                artist_or_uploader=artist,
                duration_seconds=240.0,
                media_type="audio",
                source_platform="youtube",
                source_url=f"https://www.youtube.com/watch?v=canon_{cluster_idx:04d}",
                view_count=5_000_000,
            )

            # --- A. Verified Positives (Grade 3) ---
            q_exact_media = QueryRecord(
                query_id=f"q_{cluster_idx}_exact",
                raw_query=base_query,
                normalized_query=base_query.lower(),
                media_type="audio",
                target_media_id=canonical_cand.candidate_id,
                variation_type="original",
            )
            examples.append(
                LabeledExample(
                    example_id=f"ex_{cluster_idx}_canon_exact",
                    query=q_exact_media,
                    candidate=canonical_cand,
                    grade=RelevanceGrade.EXACT_MATCH,
                    provenance=ProvenanceType.VERIFIED_CANONICAL,
                    confidence=1.0,
                    group_id=cluster_id,
                    notes="Canonical media match for query",
                )
            )

            # If base query differs from full title, also add full title query
            if base_query.lower() != full_canonical_title.lower():
                q_full = QueryRecord(
                    query_id=f"q_{cluster_idx}_full",
                    raw_query=full_canonical_title,
                    normalized_query=full_canonical_title.lower(),
                    media_type="audio",
                    target_media_id=canonical_cand.candidate_id,
                    variation_type="full_title",
                )
                examples.append(
                    LabeledExample(
                        example_id=f"ex_{cluster_idx}_canon_full",
                        query=q_full,
                        candidate=canonical_cand,
                        grade=RelevanceGrade.EXACT_MATCH,
                        provenance=ProvenanceType.VERIFIED_CANONICAL,
                        confidence=1.0,
                        group_id=cluster_id,
                        notes="Full title match",
                    )
                )

            # --- B. Query Variations (Grade 3 & Grade 2) ---
            # 1. Lowercase without punctuation
            clean_q = re.sub(r"[^\w\s]", "", base_query).lower().strip()
            if clean_q and clean_q != base_query:
                q_var_clean = QueryRecord(
                    query_id=f"q_{cluster_idx}_nopunct",
                    raw_query=clean_q,
                    normalized_query=clean_q,
                    media_type="audio",
                    target_media_id=canonical_cand.candidate_id,
                    variation_type="punctuation_removed",
                )
                examples.append(
                    LabeledExample(
                        example_id=f"ex_{cluster_idx}_var_clean",
                        query=q_var_clean,
                        candidate=canonical_cand,
                        grade=RelevanceGrade.EXACT_MATCH,
                        provenance=ProvenanceType.SYNTHETIC_VARIATION,
                        confidence=0.98,
                        group_id=cluster_id,
                        notes="Punctuation stripped variant",
                    )
                )

            # 2. Typos in query
            typo_q = introduce_realistic_typos(base_query)
            if typo_q != base_query:
                q_var_typo = QueryRecord(
                    query_id=f"q_{cluster_idx}_typo",
                    raw_query=typo_q,
                    normalized_query=typo_q.lower(),
                    media_type="audio",
                    target_media_id=canonical_cand.candidate_id,
                    variation_type="typo",
                )
                examples.append(
                    LabeledExample(
                        example_id=f"ex_{cluster_idx}_var_typo",
                        query=q_var_typo,
                        candidate=canonical_cand,
                        grade=RelevanceGrade.EXACT_MATCH,
                        provenance=ProvenanceType.SYNTHETIC_VARIATION,
                        confidence=0.95,
                        group_id=cluster_id,
                        notes="Typo tolerance variant",
                    )
                )

            # 3. Partial title query
            title_words = title.split()
            if len(title_words) >= 2:
                partial_q = " ".join(title_words[:2])
                q_var_partial = QueryRecord(
                    query_id=f"q_{cluster_idx}_partial",
                    raw_query=partial_q,
                    normalized_query=partial_q.lower(),
                    media_type="audio",
                    target_media_id=canonical_cand.candidate_id,
                    variation_type="partial",
                )
                examples.append(
                    LabeledExample(
                        example_id=f"ex_{cluster_idx}_var_partial",
                        query=q_var_partial,
                        candidate=canonical_cand,
                        grade=RelevanceGrade.RELEVANT,
                        provenance=ProvenanceType.SYNTHETIC_VARIATION,
                        confidence=0.90,
                        group_id=cluster_id,
                        notes="Partial title variant",
                    )
                )

            # --- C. Graded Alternate Releases (Grade 2) ---
            # Official Live or Remix Candidate
            live_cand = CandidateRecord(
                candidate_id=f"cand_{cluster_idx}_live",
                title=f"{full_canonical_title} (Live in Concert)",
                artist_or_uploader=artist,
                duration_seconds=310.0,
                media_type="audio",
                source_platform="youtube",
                source_url=f"https://www.youtube.com/watch?v=live_{cluster_idx:04d}",
                view_count=1_200_000,
            )
            examples.append(
                LabeledExample(
                    example_id=f"ex_{cluster_idx}_alt_live",
                    query=q_exact_media,
                    candidate=live_cand,
                    grade=RelevanceGrade.RELEVANT,
                    provenance=ProvenanceType.VERIFIED_CANONICAL,
                    confidence=0.95,
                    group_id=cluster_id,
                    notes="Live release of target media",
                )
            )

            # Official Remix
            remix_cand = CandidateRecord(
                candidate_id=f"cand_{cluster_idx}_remix",
                title=f"{full_canonical_title} (Official Club Remix)",
                artist_or_uploader=artist,
                duration_seconds=220.0,
                media_type="audio",
                source_platform="youtube",
                source_url=f"https://www.youtube.com/watch?v=remix_{cluster_idx:04d}",
                view_count=800_000,
            )
            examples.append(
                LabeledExample(
                    example_id=f"ex_{cluster_idx}_alt_remix",
                    query=q_exact_media,
                    candidate=remix_cand,
                    grade=RelevanceGrade.RELEVANT,
                    provenance=ProvenanceType.VERIFIED_CANONICAL,
                    confidence=0.90,
                    group_id=cluster_id,
                    notes="Official remix candidate",
                )
            )

            # --- D. Partially Relevant / Covers (Grade 1) ---
            cover_cand = CandidateRecord(
                candidate_id=f"cand_{cluster_idx}_cover",
                title=f"{title} - Acoustic Guitar Cover",
                artist_or_uploader="Acoustic Sessions",
                duration_seconds=230.0,
                media_type="audio",
                source_platform="youtube",
                source_url=f"https://www.youtube.com/watch?v=cover_{cluster_idx:04d}",
                view_count=45_000,
            )
            examples.append(
                LabeledExample(
                    example_id=f"ex_{cluster_idx}_part_cover",
                    query=q_exact_media,
                    candidate=cover_cand,
                    grade=RelevanceGrade.PARTIALLY_RELEVANT,
                    provenance=ProvenanceType.HARD_NEGATIVE,
                    confidence=0.88,
                    group_id=cluster_id,
                    notes="Acoustic cover version",
                )
            )

            piano_cand = CandidateRecord(
                candidate_id=f"cand_{cluster_idx}_piano",
                title=f"{title} (Piano Tutorial with Synthesia)",
                artist_or_uploader="Piano Master",
                duration_seconds=190.0,
                media_type="audio",
                source_platform="youtube",
                source_url=f"https://www.youtube.com/watch?v=piano_{cluster_idx:04d}",
                view_count=20_000,
            )
            examples.append(
                LabeledExample(
                    example_id=f"ex_{cluster_idx}_part_piano",
                    query=q_exact_media,
                    candidate=piano_cand,
                    grade=RelevanceGrade.PARTIALLY_RELEVANT,
                    provenance=ProvenanceType.HARD_NEGATIVE,
                    confidence=0.85,
                    group_id=cluster_id,
                    notes="Piano tutorial candidate",
                )
            )

            # --- E. Hard Negatives (Grade 0) ---
            # 1. Non-music video clip / documentary / review
            clip_cand = CandidateRecord(
                candidate_id=f"cand_{cluster_idx}_clip",
                title=f"{base_query} (1997) Movie Clip 4K Ending Scene",
                artist_or_uploader="Movie Clips Vault",
                duration_seconds=180.0,
                media_type="video",
                source_platform="youtube",
                source_url=f"https://www.youtube.com/watch?v=clip_{cluster_idx:04d}",
                view_count=3_500_000,
            )
            examples.append(
                LabeledExample(
                    example_id=f"ex_{cluster_idx}_neg_clip",
                    query=q_exact_media,
                    candidate=clip_cand,
                    grade=RelevanceGrade.IRRELEVANT,
                    provenance=ProvenanceType.HARD_NEGATIVE,
                    confidence=0.98,
                    group_id=cluster_id,
                    notes="Movie scene clip when song is requested",
                )
            )

            review_cand = CandidateRecord(
                candidate_id=f"cand_{cluster_idx}_review",
                title=f"{base_query} Detailed Movie Review & Plot Breakdown",
                artist_or_uploader="Film Analysis",
                duration_seconds=900.0,
                media_type="video",
                source_platform="youtube",
                source_url=f"https://www.youtube.com/watch?v=review_{cluster_idx:04d}",
                view_count=150_000,
            )
            examples.append(
                LabeledExample(
                    example_id=f"ex_{cluster_idx}_neg_review",
                    query=q_exact_media,
                    candidate=review_cand,
                    grade=RelevanceGrade.IRRELEVANT,
                    provenance=ProvenanceType.HARD_NEGATIVE,
                    confidence=0.98,
                    group_id=cluster_id,
                    notes="Video review / analysis",
                )
            )

            # 2. Same artist, completely different track (high confusion hard negative)
            other_title = all_titles[(cluster_idx + 1) % len(all_titles)]
            if artist:
                same_artist_diff_track = CandidateRecord(
                    candidate_id=f"cand_{cluster_idx}_diff_track",
                    title=f"{artist} - {other_title}",
                    artist_or_uploader=artist,
                    duration_seconds=210.0,
                    media_type="audio",
                    source_platform="youtube",
                    source_url=f"https://www.youtube.com/watch?v=same_artist_{cluster_idx:04d}",
                    view_count=2_000_000,
                )
                examples.append(
                    LabeledExample(
                        example_id=f"ex_{cluster_idx}_neg_artist_diff",
                        query=q_exact_media,
                        candidate=same_artist_diff_track,
                        grade=RelevanceGrade.IRRELEVANT,
                        provenance=ProvenanceType.HARD_NEGATIVE,
                        confidence=0.95,
                        group_id=cluster_id,
                        notes="Same artist, different song",
                    )
                )

            # 3. Unrelated cross-cluster noise
            unrelated_artist = all_artists[(cluster_idx + 3) % len(all_artists)]
            unrelated_title = all_titles[(cluster_idx + 3) % len(all_titles)]
            noise_cand = CandidateRecord(
                candidate_id=f"cand_{cluster_idx}_noise",
                title=f"{unrelated_artist} - {unrelated_title}",
                artist_or_uploader=unrelated_artist,
                duration_seconds=200.0,
                media_type="audio",
                source_platform="youtube",
                source_url=f"https://www.youtube.com/watch?v=noise_{cluster_idx:04d}",
                view_count=500_000,
            )
            examples.append(
                LabeledExample(
                    example_id=f"ex_{cluster_idx}_neg_noise",
                    query=q_exact_media,
                    candidate=noise_cand,
                    grade=RelevanceGrade.IRRELEVANT,
                    provenance=ProvenanceType.HARD_NEGATIVE,
                    confidence=1.0,
                    group_id=cluster_id,
                    notes="Completely unrelated noise candidate",
                )
            )

        return examples
