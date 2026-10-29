"""In-memory mock Google Drive adapter for automated testing and CI.

Implements identical method signatures to GoogleDriveClient:
- ensure_rei1_hierarchy()
- upload_file()
- download_file()
- list_files()
Computes real SHA-256 checksums, validates folder hierarchy, and simulates errors.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from kon_search.gdrive.config import (
    DRIVE_ROOT_FOLDER_NAME,
    MODEL_FAMILY_FOLDER_NAME,
    REMOTE_SUBDIRECTORIES,
)

log = logging.getLogger("kon_search_gdrive_mock")


def compute_file_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class MockGoogleDriveAdapter:
    """Mock storage simulating Google Drive in-memory with real checksumming."""

    def __init__(self, simulate_network_failure: bool = False, fail_on_attempt: int = 0):
        self.simulate_network_failure = simulate_network_failure
        self.fail_on_attempt = fail_on_attempt
        self.attempt_count = 0
        self.files_storage: Dict[str, Dict[str, Any]] = {}  # file_id -> metadata & bytes
        self.folders_storage: Dict[str, str] = {}  # path -> folder_id
        self._next_id = 1

    def ensure_rei1_hierarchy(self) -> Dict[str, str]:
        """Simulate creating the KON Search Data/Rei 1 folder layout."""
        hierarchy = {}
        hierarchy["root"] = "mock_folder_root"
        hierarchy["model_root"] = "mock_folder_rei1"
        for subdir in REMOTE_SUBDIRECTORIES:
            hierarchy[subdir] = f"mock_folder_{subdir}"
        self.folders_storage = hierarchy
        return hierarchy

    def upload_file(
        self,
        local_path: Path,
        remote_subfolder: str = "datasets",
        description: str = "",
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Simulate resumable chunked upload with checksum calculation."""
        self.attempt_count += 1
        if self.simulate_network_failure and self.attempt_count == self.fail_on_attempt:
            raise ConnectionResetError("Simulated network drop during chunk upload.")

        if not local_path.exists():
            raise FileNotFoundError(f"Local file does not exist: {local_path}")

        local_sha256 = compute_file_sha256(local_path)
        file_name = local_path.name
        file_size = local_path.stat().st_size

        # Deduplication check
        for fid, item in self.files_storage.items():
            if item["name"] == file_name and item["subfolder"] == remote_subfolder:
                if item["sha256"] == local_sha256:
                    return {
                        "file_id": fid,
                        "name": file_name,
                        "sha256": local_sha256,
                        "size_bytes": file_size,
                        "subfolder": remote_subfolder,
                        "status": "cached",
                    }

        with open(local_path, "rb") as f:
            content_bytes = f.read()

        file_id = f"mock_file_{self._next_id:04d}"
        self._next_id += 1

        self.files_storage[file_id] = {
            "id": file_id,
            "name": file_name,
            "subfolder": remote_subfolder,
            "sha256": local_sha256,
            "size": file_size,
            "content": content_bytes,
            "description": description,
        }

        return {
            "file_id": file_id,
            "name": file_name,
            "sha256": local_sha256,
            "size_bytes": file_size,
            "subfolder": remote_subfolder,
            "status": "uploaded",
        }

    def download_file(self, file_id: str, destination_path: Path) -> bool:
        """Simulate downloading file and verifying sha256."""
        if file_id not in self.files_storage:
            raise FileNotFoundError(f"File {file_id} not found in mock drive.")

        item = self.files_storage[file_id]
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        with open(destination_path, "wb") as f:
            f.write(item["content"])

        actual_sha256 = compute_file_sha256(destination_path)
        if actual_sha256 != item["sha256"]:
            destination_path.unlink(missing_ok=True)
            raise ValueError("Checksum verification failed.")

        return True

    def list_files(self, remote_subfolder: str = "datasets") -> List[Dict[str, Any]]:
        """List files stored in subfolder."""
        results = []
        for fid, item in self.files_storage.items():
            if item["subfolder"] == remote_subfolder:
                results.append({
                    "id": item["id"],
                    "name": item["name"],
                    "size": item["size"],
                    "appProperties": {"sha256": item["sha256"]},
                })
        return results
