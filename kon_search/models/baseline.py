"""Lexical Baseline Ranker using TF-IDF and N-gram Cosine Similarity."""

import time
from typing import Any, Dict, List, Tuple
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from kon_search.schema import CandidateRecord, QueryRecord


class LexicalBaselineRanker:
    """Baseline ranker using word and subword character n-gram TF-IDF cosine similarity."""

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            analyzer="char_wb",
            ngram_range=(2, 4),
            min_df=1,
            sublinear_tf=True,
        )
        self.is_fitted = False

    def fit(self, corpus_texts: List[str]) -> "LexicalBaselineRanker":
        """Fit TF-IDF vocabulary on query and candidate title corpus."""
        if not corpus_texts:
            corpus_texts = ["empty"]
        self.vectorizer.fit(corpus_texts)
        self.is_fitted = True
        return self

    def score_candidates(
        self, query: QueryRecord, candidates: List[CandidateRecord]
    ) -> List[Tuple[CandidateRecord, float]]:
        """Score each candidate against the query using TF-IDF cosine similarity."""
        if not candidates:
            return []

        if not self.is_fitted:
            # Online fit on current query + candidates
            texts = [query.raw_query] + [c.title for c in candidates]
            self.fit(texts)

        q_vec = self.vectorizer.transform([query.raw_query])
        cand_texts = [f"{c.title} {c.artist_or_uploader}".strip() for c in candidates]
        c_vecs = self.vectorizer.transform(cand_texts)

        similarities = cosine_similarity(q_vec, c_vecs)[0]

        scored = list(zip(candidates, similarities.tolist()))
        # Sort descending by similarity score
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored
