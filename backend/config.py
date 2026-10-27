"""Configuration for KON Media.

Ensures all application paths, caches, downloads, and state are strictly
contained within Drive E:.
"""

import os
from pathlib import Path

# Base application directory on Drive E:
BASE_DIR = Path(__file__).resolve().parent.parent

# Storage and runtime directories
DOWNLOADS_DIR = BASE_DIR / "downloads"
STATE_DIR = BASE_DIR / "app_state"
CACHE_DIR = BASE_DIR / ".cache"
TEMP_DIR = CACHE_DIR / "tmp"
FRONTEND_DIST_DIR = BASE_DIR / "frontend" / "dist"

# Network & Server configuration
HOST = os.environ.get("KON_HOST", "127.0.0.1")  # Strict loopback binding
PORT = int(os.environ.get("KON_PORT", "8899"))
MAX_CONCURRENT_DOWNLOADS = int(os.environ.get("KON_MAX_CONCURRENT", "2"))

# Ensure local directories exist
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)
STATE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR.mkdir(parents=True, exist_ok=True)
