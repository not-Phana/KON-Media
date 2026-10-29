"""Model persistence and serialization for KON Search 1 Rei."""

import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import joblib
from kon_search.models.ranker_rei1 import KONSearch1ReiModel
from kon_search.schema import ModelMetadata

log = logging.getLogger("kon_search_persistence")


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class ModelPersistenceManager:
    """Manages saving, loading, versioning, and integrity checking of KON Search models."""

    def __init__(self, models_dir: Optional[Path] = None):
        if models_dir is None:
            # Default to workspace data directory
            models_dir = Path(__file__).resolve().parent.parent.parent / "data" / "models" / "rei1"
        self.models_dir = models_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

    def save_model(
        self,
        model: KONSearch1ReiModel,
        version_tag: str = "1.0.0",
        metadata: Optional[ModelMetadata] = None,
    ) -> Tuple[Path, Path, str]:
        """Save model estimator and metadata JSON with integrity checksum."""
        version_dir = self.models_dir / f"rei1_v{version_tag}"
        version_dir.mkdir(parents=True, exist_ok=True)

        model_file = version_dir / "kon_search_1_rei.joblib"
        metadata_file = version_dir / "metadata.json"

        # Serialize estimator
        joblib.dump(model.estimator, model_file, compress=3)
        checksum = compute_file_sha256(model_file)

        # Build metadata
        meta_dict = metadata.to_dict() if metadata else (model.metadata.to_dict() if model.metadata else {})
        meta_dict["model_artifact_sha256"] = checksum
        meta_dict["artifact_filename"] = model_file.name

        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(meta_dict, f, indent=2)

        log.info("Saved %s v%s to %s (SHA256: %s)", model.model_name, version_tag, model_file, checksum[:12])
        return model_file, metadata_file, checksum

    def load_model(self, version_tag: str = "1.0.0") -> Tuple[KONSearch1ReiModel, Dict[str, Any]]:
        """Load trained model and metadata."""
        version_dir = self.models_dir / f"rei1_v{version_tag}"
        model_file = version_dir / "kon_search_1_rei.joblib"
        metadata_file = version_dir / "metadata.json"

        if not model_file.exists():
            raise FileNotFoundError(f"Model file not found: {model_file}")

        estimator = joblib.load(model_file)
        metadata = {}
        if metadata_file.exists():
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)

        model = KONSearch1ReiModel()
        model.estimator = estimator
        model.is_trained = True
        return model, metadata
