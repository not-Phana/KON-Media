"""Tests for TaskManager queue management, lifecycle state transitions, retry, and clear-finished."""

import pytest
import threading
from backend.tasks.task_manager import TaskManager


def test_task_manager_lifecycle_and_clear_finished(tmp_path):
    class MockSettings:
        def get_settings(self):
            return {"downloads_dir": str(tmp_path), "ffmpeg_path": None}

    class MockHistory:
        def append(self, item):
            pass

    tm = TaskManager(history_store=MockHistory(), settings_store=MockSettings())

    # Inject mock tasks in various states
    tm.tasks["task_active_1"] = {
        "id": "task_active_1",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Active Download 1",
        "status": "downloading",
        "percentage": 45.0,
    }
    tm.tasks["task_queued_1"] = {
        "id": "task_queued_1",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Queued Download 1",
        "status": "queued",
        "percentage": 0.0,
    }
    tm.tasks["task_done_1"] = {
        "id": "task_done_1",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Done Download 1",
        "status": "completed",
        "percentage": 100.0,
    }
    tm.tasks["task_failed_1"] = {
        "id": "task_failed_1",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Failed Download 1",
        "status": "failed",
        "percentage": 12.0,
        "error": "Network connection dropped",
    }
    tm.tasks["task_cancelled_1"] = {
        "id": "task_cancelled_1",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "title": "Cancelled Download 1",
        "status": "cancelled",
        "percentage": 50.0,
    }

    # Verify initial task count
    assert len(tm.get_active_tasks()) == 5

    # Test clear_finished_tasks
    cleared = tm.clear_finished_tasks()
    assert set(cleared) == {"task_done_1", "task_failed_1", "task_cancelled_1"}

    # Remaining tasks should only be active/queued
    remaining = tm.get_active_tasks()
    remaining_ids = {t["id"] for t in remaining}
    assert remaining_ids == {"task_active_1", "task_queued_1"}


def test_task_manager_retry(monkeypatch, tmp_path):
    class MockSettings:
        def get_settings(self):
            return {"downloads_dir": str(tmp_path), "ffmpeg_path": None}

    class MockHistory:
        def append(self, item):
            pass

    tm = TaskManager(history_store=MockHistory(), settings_store=MockSettings())

    # Cannot retry active task
    tm.tasks["active_t"] = {
        "id": "active_t",
        "url": "https://www.youtube.com/watch?v=abc",
        "title": "Active Task",
        "status": "downloading",
    }
    assert tm.retry_task("active_t") is False

    # Cannot retry non-existent task
    assert tm.retry_task("nonexistent") is False

    # Can retry failed task
    tm.tasks["failed_t"] = {
        "id": "failed_t",
        "url": "https://www.youtube.com/watch?v=abc",
        "title": "Failed Task",
        "format_id": "18",
        "media_type": "video",
        "ext": "mp4",
        "audio_bitrate": "192",
        "status": "failed",
        "percentage": 30.0,
        "error": "Some error",
    }

    # Prevent actual execution of _run_task during test
    run_called = []
    monkeypatch.setattr(tm, "_run_task", lambda tid, base, ext: run_called.append(tid))

    success = tm.retry_task("failed_t")
    assert success is True
    retried = tm.get_task("failed_t")
    assert retried["status"] == "queued"
    assert retried["percentage"] == 0.0
    assert retried["error"] is None
