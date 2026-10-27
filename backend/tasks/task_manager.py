"""Download task management and queue system for KON Media.

Handles job lifecycle, concurrency limits, real-time event broadcasting
via Server-Sent Events (SSE), cancellation, and history recording.
"""

import asyncio
import concurrent.futures
from datetime import datetime, timezone
import glob
import logging
import os
from pathlib import Path
import threading
import uuid
from typing import Any, Dict, List, Optional

from backend.config import DOWNLOADS_DIR, MAX_CONCURRENT_DOWNLOADS
from backend.engine.media_engine import (
    execute_download,
    DownloadCancelledError,
    MediaEngineError,
)
from backend.storage.file_manager import (
    sanitize_filename,
    get_unique_destination_path,
    cleanup_partial_files,
)
from backend.storage.storage import HistoryStore, SettingsStore

log = logging.getLogger("kon_task_manager")


class TaskManager:
    """Coordinates media download jobs, concurrency, SSE broadcasts, and history."""

    def __init__(self, history_store: HistoryStore, settings_store: SettingsStore):
        self.history_store = history_store
        self.settings_store = settings_store
        self.tasks: Dict[str, Dict[str, Any]] = {}
        self.abort_events: Dict[str, threading.Event] = {}
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_CONCURRENT_DOWNLOADS,
            thread_name_prefix="kon_dl_worker"
        )
        self.subscribers: List[asyncio.Queue] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self.subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        if q in self.subscribers:
            self.subscribers.remove(q)

    def broadcast(self, event_type: str, data: Any) -> None:
        """Thread-safe event broadcast to all active SSE subscribers."""
        if not self.subscribers or not self._loop:
            return

        payload = {"event": event_type, "data": data}
        for q in list(self.subscribers):
            try:
                self._loop.call_soon_threadsafe(q.put_nowait, payload)
            except Exception:
                pass

    def create_task(
        self,
        url: str,
        title: str,
        format_id: str,
        media_type: str = "video",
        ext: str = "mp4",
        audio_bitrate: str = "320k",
        thumbnail: Optional[str] = None,
        duration: Optional[int | float] = None,
    ) -> str:
        """Create and queue a new media download task."""
        task_id = uuid.uuid4().hex[:12]
        safe_base_name = sanitize_filename(title, "")
        final_ext = f".{ext.lstrip('.')}"

        task_record = {
            "id": task_id,
            "url": url,
            "title": title or "Media Download",
            "format_id": format_id,
            "media_type": media_type,
            "ext": ext,
            "audio_bitrate": audio_bitrate,
            "thumbnail": thumbnail,
            "duration": duration,
            "status": "queued",
            "percentage": 0.0,
            "speed": 0,
            "eta": None,
            "downloaded_bytes": 0,
            "total_bytes": 0,
            "file_path": None,
            "filename": None,
            "error": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": None,
        }

        self.tasks[task_id] = task_record
        self.abort_events[task_id] = threading.Event()

        self.broadcast("task_created", task_record)

        # Submit task to worker thread pool
        self.executor.submit(self._run_task, task_id, safe_base_name, final_ext)
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """Signal cancellation for an active or queued task."""
        task = self.tasks.get(task_id)
        if not task:
            return False

        if task["status"] in ("completed", "failed", "cancelled"):
            return False

        abort_event = self.abort_events.get(task_id)
        if abort_event:
            abort_event.set()

        task["status"] = "cancelled"
        task["completed_at"] = datetime.now(timezone.utc).isoformat()
        self.broadcast("task_updated", task)

        configured_dir = self.settings_store.get_settings().get("downloads_dir")
        dest_dir = Path(configured_dir) if configured_dir else DOWNLOADS_DIR
        # Clean up partial downloads
        cleanup_partial_files(task_id, dest_dir)
        return True

    def dismiss_task(self, task_id: str) -> bool:
        """Remove a completed, failed, or cancelled task from active monitor."""
        if task_id in self.tasks:
            del self.tasks[task_id]
            if task_id in self.abort_events:
                del self.abort_events[task_id]
            self.broadcast("task_dismissed", {"id": task_id})
            return True
        return False

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        return self.tasks.get(task_id)

    def get_active_tasks(self) -> List[Dict[str, Any]]:
        return list(self.tasks.values())

    def _run_task(self, task_id: str, safe_base_name: str, final_ext: str) -> None:
        task = self.tasks.get(task_id)
        abort_event = self.abort_events.get(task_id)
        if not task or (abort_event and abort_event.is_set()):
            return

        task["status"] = "downloading"
        self.broadcast("task_updated", task)

        configured_dir = self.settings_store.get_settings().get("downloads_dir")
        dest_dir = Path(configured_dir) if configured_dir else DOWNLOADS_DIR
        dest_dir.mkdir(parents=True, exist_ok=True)

        # Define temporary output path pattern using task_id prefix
        out_template = str(dest_dir / f"{task_id}.%(ext)s")

        def on_progress(p: Dict[str, Any]) -> None:
            if abort_event and abort_event.is_set():
                raise DownloadCancelledError()

            task["status"] = p.get("state", "downloading")
            task["percentage"] = p.get("percentage", 0.0)
            task["downloaded_bytes"] = p.get("downloaded_bytes", 0)
            task["total_bytes"] = p.get("total_bytes", 0)
            task["speed"] = p.get("speed", 0)
            task["eta"] = p.get("eta")
            self.broadcast("task_updated", task)

        try:
            execute_download(
                url=task["url"],
                format_selector=task["format_id"],
                media_type=task["media_type"],
                output_path_template=out_template,
                progress_callback=on_progress,
                abort_event=abort_event,
                audio_bitrate=task["audio_bitrate"],
            )

            # Locate downloaded file with task_id prefix
            matching_files = glob.glob(str(dest_dir / f"{task_id}.*"))
            # Filter out temporary leftover files
            valid_files = [
                f for f in matching_files
                if not f.endswith((".part", ".ytdl", ".temp"))
            ]

            if not valid_files:
                raise MediaEngineError("Download completed but output media file was not found.")

            source_file = Path(valid_files[0])
            actual_ext = source_file.suffix or final_ext

            # Determine unique destination filename using sanitized title
            target_filename = sanitize_filename(task["title"], actual_ext)
            final_dest = get_unique_destination_path(dest_dir, target_filename)

            # Rename with retry loop to handle transient Windows file locks
            renamed = False
            import time
            for attempt in range(5):
                try:
                    source_file.rename(final_dest)
                    renamed = True
                    break
                except PermissionError:
                    time.sleep(0.2)
            if not renamed:
                import shutil
                shutil.copy2(source_file, final_dest)
                try:
                    source_file.unlink(missing_ok=True)
                except OSError:
                    pass

            # Verification: Check file exists and size > 0
            if not final_dest.exists() or final_dest.stat().st_size == 0:
                raise MediaEngineError("Final media file verification failed (empty or missing file).")

            task["status"] = "completed"
            task["percentage"] = 100.0
            task["file_path"] = str(final_dest)
            task["filename"] = final_dest.name
            task["filesize"] = final_dest.stat().st_size
            task["completed_at"] = datetime.now(timezone.utc).isoformat()

            # Record in persistent history
            self.history_store.add_entry(dict(task))
            self.broadcast("task_completed", task)

        except DownloadCancelledError:
            task["status"] = "cancelled"
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            cleanup_partial_files(task_id, dest_dir)
            self.broadcast("task_updated", task)

        except Exception as e:
            task["status"] = "failed"
            task["error"] = str(e)
            task["completed_at"] = datetime.now(timezone.utc).isoformat()
            cleanup_partial_files(task_id, dest_dir)
            self.broadcast("task_updated", task)
