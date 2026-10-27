"""Atomic JSON persistence for KON Media.

Provides robust, zero-database local state storage (history.json, settings.json)
guaranteed against file corruption using temp-write and atomic replace.
"""

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List
from backend.config import STATE_DIR, DOWNLOADS_DIR

log = logging.getLogger("kon_storage")


class AtomicJsonStore:
    """Atomic JSON file store backed by write-and-rename semantics."""

    def __init__(self, file_path: Path, default_value: Any = None):
        self.file_path = file_path
        self.default_value = default_value if default_value is not None else {}

    def load(self) -> Any:
        """Load data from disk safely."""
        if not self.file_path.exists():
            return self.default_value

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            log.warning("Could not read %s, using defaults: %s", self.file_path, e)
            return self.default_value

    def save(self, data: Any) -> None:
        """Atomically write data to disk."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        dir_name = self.file_path.parent

        # Create temporary file in same directory to ensure same filesystem volume
        fd, temp_path = tempfile.mkstemp(dir=dir_name, prefix="tmp_kon_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace on Windows
            os.replace(temp_path, self.file_path)
        except Exception:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass
            raise


class HistoryStore:
    """Manages persistent record of completed and attempted media downloads."""

    def __init__(self, state_dir: Path = STATE_DIR):
        self.store = AtomicJsonStore(state_dir / "history.json", default_value=[])

    def get_all(self) -> List[Dict[str, Any]]:
        return self.store.load()

    def add_entry(self, entry: Dict[str, Any]) -> None:
        entries = self.get_all()
        # Prepend so newest is first
        entries.insert(0, entry)
        # Cap history to 500 items
        if len(entries) > 500:
            entries = entries[:500]
        self.store.save(entries)

    def update_entry(self, task_id: str, updates: Dict[str, Any]) -> None:
        entries = self.get_all()
        for item in entries:
            if item.get("id") == task_id:
                item.update(updates)
                break
        self.store.save(entries)

    def remove_entry(self, task_id: str) -> None:
        entries = [e for e in self.get_all() if e.get("id") != task_id]
        self.store.save(entries)

    def clear(self) -> None:
        self.store.save([])


class SettingsStore:
    """Manages persistent user settings."""

    def __init__(self, state_dir: Path = STATE_DIR):
        default_settings = {
            "downloads_dir": str(DOWNLOADS_DIR),
            "max_concurrent_downloads": 2,
            "default_media_type": "video",
            "ffmpeg_path": "",
        }
        self.store = AtomicJsonStore(state_dir / "settings.json", default_value=default_settings)

    def get_settings(self) -> Dict[str, Any]:
        return self.store.load()

    def update_settings(self, updates: Dict[str, Any]) -> Dict[str, Any]:
        current = self.get_settings()
        current.update(updates)
        self.store.save(current)
        return current
