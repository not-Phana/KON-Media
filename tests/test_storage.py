"""Unit tests for Atomic Storage, History, and Settings."""

import pytest
from backend.storage.storage import AtomicJsonStore, HistoryStore, SettingsStore


def test_atomic_json_store_save_and_load(tmp_path):
    store_file = tmp_path / "data.json"
    store = AtomicJsonStore(store_file, default_value={"key": "default"})

    # Check default when file does not exist
    assert store.load() == {"key": "default"}

    # Save data
    payload = {"status": "ok", "count": 42}
    store.save(payload)

    # Reload data
    loaded = store.load()
    assert loaded == payload
    assert store_file.exists()


def test_history_store(tmp_path):
    history = HistoryStore(state_dir=tmp_path)
    assert history.get_all() == []

    entry1 = {"id": "job1", "title": "Track 1", "status": "completed"}
    entry2 = {"id": "job2", "title": "Track 2", "status": "failed"}

    history.add_entry(entry1)
    history.add_entry(entry2)

    entries = history.get_all()
    assert len(entries) == 2
    # Newest entry should be first
    assert entries[0]["id"] == "job2"
    assert entries[1]["id"] == "job1"

    # Update entry
    history.update_entry("job2", {"status": "completed"})
    updated = history.get_all()
    assert updated[0]["status"] == "completed"

    # Remove entry
    history.remove_entry("job1")
    assert len(history.get_all()) == 1

    # Clear history
    history.clear()
    assert history.get_all() == []


def test_settings_store(tmp_path):
    settings = SettingsStore(state_dir=tmp_path)
    current = settings.get_settings()
    assert "downloads_dir" in current
    assert current["max_concurrent_downloads"] == 2

    # Update settings
    updated = settings.update_settings({"max_concurrent_downloads": 4})
    assert updated["max_concurrent_downloads"] == 4
    assert settings.get_settings()["max_concurrent_downloads"] == 4
