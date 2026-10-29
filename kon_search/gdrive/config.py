"""Configuration and security paths for Google Drive storage adapter."""

from pathlib import Path
from typing import List

# Narrowest OAuth Scope: only access files created or opened by this app
DRIVE_SCOPES: List[str] = ["https://www.googleapis.com/auth/drive.file"]

# Root folder layout on Google Drive
DRIVE_ROOT_FOLDER_NAME: str = "KON Search Data"
MODEL_FAMILY_FOLDER_NAME: str = "Rei 1"

REMOTE_SUBDIRECTORIES: List[str] = [
    "raw",
    "validated",
    "datasets",
    "manifests",
    "evaluation",
    "checkpoints",
    "release-candidates",
]

# Local directory for credentials (excluded in .gitignore)
DEFAULT_CREDENTIALS_DIR = Path(__file__).resolve().parent.parent.parent / ".gdrive_credentials"
CLIENT_SECRETS_FILE = DEFAULT_CREDENTIALS_DIR / "credentials.json"
TOKEN_STORAGE_FILE = DEFAULT_CREDENTIALS_DIR / "token.json"
