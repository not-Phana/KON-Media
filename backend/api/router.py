"""REST and Server-Sent Events (SSE) API router for KON Media."""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.config import DOWNLOADS_DIR
from backend.engine.media_engine import (
    extract_media_info,
    get_engine_health,
    MediaEngineError,
)
from backend.security.url_guard import validate_media_url, SecurityValidationError
from backend.storage.file_manager import open_in_file_explorer
from backend.storage.storage import HistoryStore, SettingsStore
from backend.tasks.task_manager import TaskManager

log = logging.getLogger("kon_api")

router = APIRouter(prefix="/api")

# Singletons initialized on startup
history_store = HistoryStore()
settings_store = SettingsStore()
task_manager = TaskManager(history_store, settings_store)


# Request Models
class AnalyzeRequest(BaseModel):
    url: str = Field(..., description="Media URL to analyze")


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Media URL to download")
    title: Optional[str] = Field("Media Download", description="Media Title")
    format_id: Optional[str] = Field("bestvideo+bestaudio/best", description="yt-dlp format selector")
    media_type: Optional[str] = Field("video", description="'video' or 'audio'")
    ext: Optional[str] = Field("mp4", description="Expected file extension")
    audio_bitrate: Optional[str] = Field("320k", description="Audio quality bitrate")
    thumbnail: Optional[str] = Field(None, description="Media thumbnail URL")
    duration: Optional[int | float] = Field(None, description="Media duration in seconds")


class OpenFolderRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path of the file to open in explorer")


class SettingsUpdateRequest(BaseModel):
    downloads_dir: Optional[str] = None
    max_concurrent_downloads: Optional[int] = None
    default_media_type: Optional[str] = None


@router.get("/health")
async def health_check():
    """System health check and dependency detection."""
    engine_status = get_engine_health()
    disk_usage = shutil.disk_usage(DOWNLOADS_DIR)

    return {
        "status": "healthy",
        "service": "KON Media",
        "engine": engine_status,
        "downloads_dir": str(DOWNLOADS_DIR),
        "disk_free_gb": round(disk_usage.free / (1024 ** 3), 2),
        "disk_total_gb": round(disk_usage.total / (1024 ** 3), 2),
    }


@router.post("/analyze")
async def analyze_url(req: AnalyzeRequest):
    """Validate and analyze media URL, returning metadata and available formats."""
    # 1. URL Security and SSRF validation
    try:
        validated_url = validate_media_url(req.url)
    except SecurityValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Extract media info asynchronously
    try:
        info = await asyncio.to_thread(extract_media_info, validated_url)
        return info
    except MediaEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.post("/download")
async def start_download(req: DownloadRequest):
    """Queue a media download task."""
    try:
        validated_url = validate_media_url(req.url)
    except SecurityValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    task_id = task_manager.create_task(
        url=validated_url,
        title=req.title or "Media Download",
        format_id=req.format_id or "bestvideo+bestaudio/best",
        media_type=req.media_type or "video",
        ext=req.ext or "mp4",
        audio_bitrate=req.audio_bitrate or "320k",
        thumbnail=req.thumbnail,
        duration=req.duration,
    )

    return {"task_id": task_id, "status": "queued"}


@router.get("/tasks")
async def list_tasks():
    """List all currently active or recent tasks."""
    return task_manager.get_active_tasks()


@router.post("/tasks/{task_id}/cancel")
async def cancel_download_task(task_id: str):
    """Cancel an ongoing or queued download task."""
    success = task_manager.cancel_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found or already finished.")
    return {"task_id": task_id, "status": "cancelled"}


@router.post("/tasks/{task_id}/dismiss")
async def dismiss_download_task(task_id: str):
    """Dismiss a finished, failed, or cancelled task from active monitor."""
    success = task_manager.dismiss_task(task_id)
    if not success:
        raise HTTPException(status_code=404, detail="Task not found in active monitor.")
    return {"task_id": task_id, "status": "dismissed"}


@router.get("/events")
async def sse_event_stream(request: Request):
    """Server-Sent Events endpoint streaming real-time download progress."""
    queue = task_manager.subscribe()

    async def event_generator():
        try:
            # Yield initial connection confirmation
            yield f"event: connected\ndata: {json.dumps({'message': 'Connected to KON Media event stream'})}\n\n"
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"event: {payload['event']}\ndata: {json.dumps(payload['data'])}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive heartbeat
                    yield ": heartbeat\n\n"
        finally:
            task_manager.unsubscribe(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history")
async def get_download_history():
    """Retrieve persistent download history."""
    return history_store.get_all()


@router.delete("/history")
async def clear_download_history():
    """Clear all download history."""
    history_store.clear()
    return {"status": "cleared"}


@router.delete("/history/{task_id}")
async def remove_history_item(task_id: str):
    """Remove a single item from history."""
    history_store.remove_entry(task_id)
    return {"status": "deleted", "id": task_id}


@router.get("/settings")
async def get_settings():
    """Retrieve current settings."""
    return settings_store.get_settings()


@router.post("/settings")
async def update_settings(req: SettingsUpdateRequest):
    """Update settings."""
    updates = req.model_dump(exclude_unset=True)
    updated = settings_store.update_settings(updates)
    return updated


@router.post("/open-folder")
async def open_download_file(req: OpenFolderRequest):
    """Safely open Windows File Explorer with the downloaded file highlighted."""
    p = Path(req.file_path)
    configured_dir = Path(settings_store.get_settings().get("downloads_dir", str(DOWNLOADS_DIR)))
    success = open_in_file_explorer(p, allowed_root=configured_dir)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not open file in Explorer. Path may be invalid or outside downloads directory."
        )
    return {"status": "opened"}
