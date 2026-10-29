"""Local-first self-learning neural ranking model and semantic association engine.

Learns semantic associations between query terms and media entities using online
gradient updates (SGD), token embeddings, and pairwise ranking loss.
Requires zero external ML libraries, zero cloud APIs, and runs in sub-millisecond time.
"""

import math
import random
import datetime
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from backend.config import STATE_DIR
from backend.storage.storage import AtomicJsonStore
from backend.search.normalization import normalize_text

log = logging.getLogger("kon_learning_model")


def simple_tokenize(text: str) -> List[str]:
    """Tokenize normalized text into clean alphanumeric words."""
    norm = normalize_text(text)
    return [w for w in norm.split() if len(w) > 1]


class SearchLearningModel:
    """Self-learning semantic association and feature-weight ranker model."""

    def __init__(self, state_dir: Path = STATE_DIR, embedding_dim: int = 16, learning_rate: float = 0.05):
        self.state_file = state_dir / "search_model.json"
        self.store = AtomicJsonStore(self.state_file, default_value={})
        self.embedding_dim = embedding_dim
        self.learning_rate = learning_rate

        # Initialize default model weights
        self.weights: Dict[str, float] = {
            "exact_title": 0.35,
            "fuzzy_title": 0.25,
            "token_overlap": 0.15,
            "artist_match": 0.20,
            "semantic_embedding": 0.30,
            "duration_compat": 0.15,
            "version_compat": 0.25,
            "audio_affinity": 0.15,
        }
        self.bias: float = 0.0

        # Semantic association dictionary: maps (query_token, target_token) -> learned strength weight
        self.associations: Dict[str, Dict[str, float]] = {}

        # Token embeddings: word -> vector of floats
        self.embeddings: Dict[str, List[float]] = {}

        # Training history metadata
        self.metadata: Dict[str, Any] = {
            "total_updates": 0,
            "training_epochs": 0,
            "last_loss": 0.0,
            "last_trained_at": None,
            "learned_tokens_count": 0,
        }

        self.load_model()

    def _get_embedding(self, token: str) -> List[float]:
        """Retrieve or randomly initialize normalized token embedding vector."""
        if token not in self.embeddings:
            # Deterministic pseudo-random initialization based on token hash
            rnd = random.Random(token)
            vec = [rnd.uniform(-0.2, 0.2) for _ in range(self.embedding_dim)]
            norm = math.sqrt(sum(x * x for x in vec)) or 1.0
            self.embeddings[token] = [x / norm for x in vec]
        return self.embeddings[token]

    def compute_semantic_similarity(self, query: str, candidate_title: str) -> float:
        """Compute learned semantic affinity between query and candidate using token embeddings & associations."""
        q_tokens = simple_tokenize(query)
        c_tokens = simple_tokenize(candidate_title)

        if not q_tokens or not c_tokens:
            return 0.0

        # 1. Direct learned token-to-token association boost
        assoc_score = 0.0
        matched_assocs = 0
        has_negative_mismatch = False
        for qt in q_tokens:
            if qt in self.associations:
                for ct in c_tokens:
                    if ct in self.associations[qt]:
                        val = self.associations[qt][ct]
                        if val > 0:
                            assoc_score += val
                            matched_assocs += 1
                        elif val < 0:
                            assoc_score += val * 1.5
                            has_negative_mismatch = True

        # 2. Dense embedding dot product (max pool query token similarity over candidate tokens)
        max_dots = []
        for qt in q_tokens:
            q_vec = self._get_embedding(qt)
            best_dot = -1.0
            for ct in c_tokens:
                c_vec = self._get_embedding(ct)
                dot = sum(a * b for a, b in zip(q_vec, c_vec))
                if dot > best_dot:
                    best_dot = dot
            max_dots.append(best_dot)

        avg_emb_sim = sum(max_dots) / len(max_dots) if max_dots else 0.0
        emb_score = max(0.0, min(1.0, (avg_emb_sim + 1.0) / 2.0))

        if matched_assocs > 0:
            assoc_norm = min(1.0, max(0.0, assoc_score))
            combined = 0.3 * emb_score + 0.7 * assoc_norm
        elif has_negative_mismatch:
            combined = max(0.0, emb_score * 0.2 + assoc_score)
        else:
            combined = emb_score * 0.5

        return max(0.0, min(1.0, round(combined, 4)))

    def get_associated_tokens(self, query: str, top_k: int = 5) -> List[str]:
        """Return the highest-weighted learned target association tokens for a query."""
        q_tokens = simple_tokenize(query)
        if not q_tokens:
            return []

        token_weights: Dict[str, float] = {}
        for qt in q_tokens:
            if qt in self.associations:
                for ct, weight in self.associations[qt].items():
                    if weight > 0.1 and ct not in q_tokens:
                        token_weights[ct] = token_weights.get(ct, 0.0) + weight

        if not token_weights:
            return []

        sorted_tokens = sorted(token_weights.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_tokens[:top_k]]

    def predict_score(self, feature_vector: Dict[str, float], query_text: str, candidate_title: str) -> Tuple[float, float]:
        """Compute predicted candidate relevance probability using learned weights and semantic associations."""
        semantic_score = self.compute_semantic_similarity(query_text, candidate_title)

        # Weighted linear combination
        z = self.bias
        for feat, val in feature_vector.items():
            w = self.weights.get(feat, 0.1)
            z += w * val

        # Add semantic score feature
        z += self.weights.get("semantic_embedding", 0.3) * semantic_score

        # Sigmoid activation probability
        prob = 1.0 / (1.0 + math.exp(-max(-10.0, min(10.0, z))))
        return prob, semantic_score

    def train_step(self, query: str, candidate_title: str, feature_vector: Dict[str, float], label: float) -> float:
        """Perform a single online Stochastic Gradient Descent (SGD) learning update.

        label: 1.0 for positive selection (user downloaded or confirmed), 0.0 for mismatch.
        Returns the cross-entropy loss for this step.
        """
        prob, semantic_sim = self.predict_score(feature_vector, query, candidate_title)
        error = label - prob  # Gradient direction (y - y_hat)

        # 1. Update linear feature weights with L2 regularization
        l2_reg = 0.001
        for feat, val in feature_vector.items():
            grad = error * val - l2_reg * self.weights.get(feat, 0.0)
            self.weights[feat] = max(0.01, min(1.0, self.weights.get(feat, 0.1) + self.learning_rate * grad))

        # Update bias
        self.bias += self.learning_rate * error * 0.1

        # 2. Update semantic token associations
        q_tokens = simple_tokenize(query)
        c_tokens = simple_tokenize(candidate_title)
        for qt in q_tokens:
            if qt not in self.associations:
                self.associations[qt] = {}
            for ct in c_tokens:
                curr_assoc = self.associations[qt].get(ct, 0.0)
                # Reinforce positive co-occurrence or penalize mismatch with high sensitivity
                delta = (0.20 if label == 1.0 else -0.30) * max(0.2, abs(error))
                new_assoc = max(-0.8, min(1.0, curr_assoc + delta))
                self.associations[qt][ct] = round(new_assoc, 4)

        # 3. Update token embeddings (pull positive embeddings closer, push negative apart)
        for qt in q_tokens:
            q_vec = self._get_embedding(qt)
            for ct in c_tokens:
                c_vec = self._get_embedding(ct)
                for d in range(self.embedding_dim):
                    q_vec[d] += self.learning_rate * error * c_vec[d] * 0.5
                    c_vec[d] += self.learning_rate * error * q_vec[d] * 0.5

                # Re-normalize vectors to unit sphere
                q_norm = math.sqrt(sum(x * x for x in q_vec)) or 1.0
                c_norm = math.sqrt(sum(x * x for x in c_vec)) or 1.0
                self.embeddings[qt] = [x / q_norm for x in q_vec]
                self.embeddings[ct] = [x / c_norm for x in c_vec]

        # Compute cross-entropy loss: - [y log(p) + (1-y) log(1-p)]
        eps = 1e-7
        p_clipped = max(eps, min(1.0 - eps, prob))
        loss = - (label * math.log(p_clipped) + (1.0 - label) * math.log(1.0 - p_clipped))

        self.metadata["total_updates"] += 1
        return loss

    def self_train(
        self,
        feedback_entries: List[Dict[str, Any]],
        download_history: List[Dict[str, Any]],
        epochs: int = 5,
    ) -> Dict[str, Any]:
        """Autonomous self-training pass over user feedback and download history."""
        training_samples: List[Tuple[str, str, float]] = []

        # 1. Collect from search feedback
        for entry in feedback_entries:
            q = entry.get("query", "")
            target_title = entry.get("selected_title", "")
            is_mismatch = entry.get("is_mismatch", False)
            if q and target_title:
                training_samples.append((q, target_title, 0.0 if is_mismatch else 1.0))

        # 2. Collect from download history (high-confidence positive signals)
        for hist in download_history:
            title = hist.get("title", "")
            if title:
                # The title itself forms positive association pairs with artist and keywords
                tokens = simple_tokenize(title)
                if len(tokens) >= 2:
                    training_samples.append((" ".join(tokens[:2]), title, 1.0))
                    training_samples.append((title, title, 1.0))

        if not training_samples:
            return {"status": "no_data", "samples": 0, "loss": 0.0}

        total_loss = 0.0
        steps = 0

        for epoch in range(epochs):
            # Shuffle order to break correlation
            shuffled = list(training_samples)
            random.shuffle(shuffled)

            for q, target_title, label in shuffled:
                # Synthetic baseline feature vector for training
                feats = {
                    "exact_title": 1.0 if q.lower() in target_title.lower() else 0.5,
                    "fuzzy_title": 0.8 if label == 1.0 else 0.2,
                    "token_overlap": 0.7 if label == 1.0 else 0.1,
                    "artist_match": 0.9 if label == 1.0 else 0.2,
                    "duration_compat": 0.9,
                    "version_compat": 1.0 if label == 1.0 else 0.3,
                    "audio_affinity": 0.8,
                }
                loss = self.train_step(q, target_title, feats, label)
                total_loss += loss
                steps += 1

        avg_loss = total_loss / steps if steps else 0.0

        self.metadata["training_epochs"] += epochs
        self.metadata["last_loss"] = round(avg_loss, 4)
        self.metadata["last_trained_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        self.metadata["learned_tokens_count"] = len(self.embeddings)

        self.save_model()

        return {
            "status": "trained",
            "samples": len(training_samples),
            "epochs": epochs,
            "total_steps": steps,
            "average_loss": round(avg_loss, 4),
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "learned_tokens": len(self.embeddings),
            "associations_count": sum(len(v) for v in self.associations.values()),
        }

    def save_model(self) -> None:
        """Atomically persist learned model weights, embeddings, and associations to disk."""
        data = {
            "weights": self.weights,
            "bias": self.bias,
            "associations": self.associations,
            "embeddings": {k: [round(x, 4) for x in v] for k, v in self.embeddings.items()},
            "metadata": self.metadata,
        }
        self.store.save(data)

    def load_model(self) -> None:
        """Load learned model state from disk if present."""
        data = self.store.load()
        if not data or not isinstance(data, dict):
            return

        if "weights" in data and isinstance(data["weights"], dict):
            self.weights.update(data["weights"])
        if "bias" in data:
            self.bias = float(data["bias"])
        if "associations" in data and isinstance(data["associations"], dict):
            self.associations = data["associations"]
        if "embeddings" in data and isinstance(data["embeddings"], dict):
            self.embeddings = data["embeddings"]
        if "metadata" in data and isinstance(data["metadata"], dict):
            self.metadata.update(data["metadata"])

    def get_stats(self) -> Dict[str, Any]:
        """Return diagnostic health and training statistics for the learning engine."""
        return {
            "weights": {k: round(v, 4) for k, v in self.weights.items()},
            "bias": round(self.bias, 4),
            "total_updates": self.metadata.get("total_updates", 0),
            "training_epochs": self.metadata.get("training_epochs", 0),
            "last_loss": self.metadata.get("last_loss", 0.0),
            "last_trained_at": self.metadata.get("last_trained_at"),
            "learned_tokens_count": len(self.embeddings),
            "associations_count": sum(len(v) for v in self.associations.values()),
        }
