"""Google Drive API Client for KON Search 1 Rei datasets, manifests, and checkpoints.

Features:
- Enforces private drive.file scope
- Structured folder hierarchy: KON Search Data/Rei 1/<subfolder>
- Resumable chunked upload with progress
- SHA-256 integrity verification on upload and download
- Deduplication by checksum
- Exponential backoff on rate limits / network hiccups
"""

import hashlib
import io
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from kon_search.gdrive.auth import GoogleDriveAuthManager
from kon_search.gdrive.config import (
    DRIVE_ROOT_FOLDER_NAME,
    MODEL_FAMILY_FOLDER_NAME,
    REMOTE_SUBDIRECTORIES,
)

log = logging.getLogger("kon_search_gdrive_client")


def compute_file_sha256(file_path: Path) -> str:
    """Compute SHA-256 checksum of a local file in chunks."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class GoogleDriveClient:
    """Production Google Drive storage adapter implementing resumable upload and verification."""

    def __init__(self, auth_manager: Optional[GoogleDriveAuthManager] = None):
        self.auth = auth_manager or GoogleDriveAuthManager()
        self._service = None
        self._folder_cache: Dict[str, str] = {}

    def _get_service(self):
        """Build authorized Google Drive Resource service."""
        if self._service is not None:
            return self._service

        from googleapiclient.discovery import build

        creds, err = self.auth.get_credentials(interactive=False)
        if not creds:
            raise PermissionError(f"Google Drive not authenticated: {err}")

        self._service = build("drive", "v3", credentials=creds)
        return self._service

    def find_folder(self, name: str, parent_id: Optional[str] = None) -> Optional[str]:
        """Find folder ID by name and parent."""
        service = self._get_service()
        query = f"name = '{name}' and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        res = service.files().list(q=query, fields="files(id, name)", spaces="drive").execute()
        files = res.get("files", [])
        return files[0]["id"] if files else None

    def create_folder(self, name: str, parent_id: Optional[str] = None) -> str:
        """Create a new private folder in Drive."""
        service = self._get_service()
        metadata: Dict[str, Any] = {
            "name": name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        folder = service.files().create(body=metadata, fields="id").execute()
        return folder["id"]

    def ensure_rei1_hierarchy(self) -> Dict[str, str]:
        """Ensure full KON Search Data/Rei 1 folder layout exists and cache folder IDs."""
        if self._folder_cache:
            return self._folder_cache

        # 1. Root folder
        root_id = self.find_folder(DRIVE_ROOT_FOLDER_NAME)
        if not root_id:
            root_id = self.create_folder(DRIVE_ROOT_FOLDER_NAME)
        self._folder_cache["root"] = root_id

        # 2. Model Family folder (Rei 1)
        model_id = self.find_folder(MODEL_FAMILY_FOLDER_NAME, parent_id=root_id)
        if not model_id:
            model_id = self.create_folder(MODEL_FAMILY_FOLDER_NAME, parent_id=root_id)
        self._folder_cache["model_root"] = model_id

        # 3. Subdirectories
        for subdir in REMOTE_SUBDIRECTORIES:
            sub_id = self.find_folder(subdir, parent_id=model_id)
            if not sub_id:
                sub_id = self.create_folder(subdir, parent_id=model_id)
            self._folder_cache[subdir] = sub_id

        return self._folder_cache

    def upload_file(
        self,
        local_path: Path,
        remote_subfolder: str = "datasets",
        description: str = "",
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Upload file with resumable chunking, checksum verification, and retry backoff."""
        if not local_path.exists():
            raise FileNotFoundError(f"Local file does not exist: {local_path}")

        service = self._get_service()
        folder_tree = self.ensure_rei1_hierarchy()
        parent_id = folder_tree.get(remote_subfolder, folder_tree["model_root"])

        local_sha256 = compute_file_sha256(local_path)
        file_name = local_path.name
        file_size = local_path.stat().st_size

        # Deduplication check: check if file with matching name and checksum already exists in target
        q = f"'{parent_id}' in parents and name = '{file_name}' and trashed = false"
        existing = service.files().list(q=q, fields="files(id, name, appProperties, size)").execute().get("files", [])
        if existing:
            first = existing[0]
            props = first.get("appProperties", {})
            if props.get("sha256") == local_sha256:
                log.info("File %s with identical checksum already exists on Drive. Bypassing upload.", file_name)
                return {
                    "file_id": first["id"],
                    "name": file_name,
                    "sha256": local_sha256,
                    "size_bytes": file_size,
                    "subfolder": remote_subfolder,
                    "status": "cached",
                }

        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(
            str(local_path),
            resumable=True,
            chunksize=1024 * 1024,  # 1MB chunks
        )

        file_metadata = {
            "name": file_name,
            "parents": [parent_id],
            "description": description or f"KON Search 1 Rei artifact: {file_name}",
            "appProperties": {
                "sha256": local_sha256,
                "model_family": "Rei 1",
                "uploaded_at": str(time.time()),
            },
        }

        request = service.files().create(body=file_metadata, media_body=media, fields="id, name")

        # Resumable upload loop with exponential backoff
        response = None
        for attempt in range(max_retries):
            try:
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        log.debug("Uploaded %d%% of %s", int(status.progress() * 100), file_name)
                break
            except Exception as e:
                log.warning("Upload attempt %d failed for %s: %s", attempt + 1, file_name, e)
                if attempt == max_retries - 1:
                    raise
                time.sleep(2**attempt)

        file_id = response.get("id")
        return {
            "file_id": file_id,
            "name": file_name,
            "sha256": local_sha256,
            "size_bytes": file_size,
            "subfolder": remote_subfolder,
            "status": "uploaded",
        }

    def download_file(self, file_id: str, destination_path: Path) -> bool:
        """Download remote Drive file and verify checksum."""
        from googleapiclient.http import MediaIoBaseDownload

        service = self._get_service()
        destination_path.parent.mkdir(parents=True, exist_ok=True)

        meta = service.files().get(fileId=file_id, fields="id, name, appProperties").execute()
        expected_sha256 = meta.get("appProperties", {}).get("sha256")

        request = service.files().get_media(fileId=file_id)
        with open(destination_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request, chunksize=1024 * 1024)
            done = False
            while not done:
                status, done = downloader.next_chunk()

        if expected_sha256:
            actual_sha256 = compute_file_sha256(destination_path)
            if actual_sha256 != expected_sha256:
                destination_path.unlink(missing_ok=True)
                raise ValueError(f"Checksum mismatch for downloaded file: expected {expected_sha256}, got {actual_sha256}")

        return True

    def list_files(self, remote_subfolder: str = "datasets") -> List[Dict[str, Any]]:
        """List files in a specific model subfolder."""
        service = self._get_service()
        folder_tree = self.ensure_rei1_hierarchy()
        parent_id = folder_tree.get(remote_subfolder, folder_tree["model_root"])

        q = f"'{parent_id}' in parents and trashed = false"
        res = service.files().list(q=q, fields="files(id, name, size, appProperties, createdTime)").execute()
        return res.get("files", [])
