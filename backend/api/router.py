"""REST and Server-Sent Events (SSE) API router for KON Media."""

import asyncio
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse, FileResponse
from pydantic import BaseModel, Field

from backend.config import DOWNLOADS_DIR
from backend.engine.media_engine import (
    extract_media_info,
    get_engine_health,
    find_spotify_match,
    fetch_spotify_oembed,
    validate_stream_pairing,
    validate_stream_pair,
    MediaEngineError,
)
from backend.engine.ffmpeg_manager import validate_ffmpeg_path
from backend.security.url_guard import (
    validate_media_url,
    SecurityValidationError,
    detect_spotify_source,
)
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


class ValidatePairingRequest(BaseModel):
    video_stream: Optional[Dict[str, Any]] = None
    audio_stream: Optional[Dict[str, Any]] = None


class DownloadRequest(BaseModel):
    url: str = Field(..., description="Media URL to download")
    title: Optional[str] = Field("Media Download", description="Media Title")
    format_id: Optional[str] = Field("bestvideo+bestaudio/best", description="yt-dlp format selector")
    media_type: Optional[str] = Field("video", description="'video' or 'audio'")
    ext: Optional[str] = Field("mp4", description="Expected file extension")
    audio_bitrate: Optional[str] = Field("320k", description="Audio quality bitrate")
    thumbnail: Optional[str] = Field(None, description="Media thumbnail URL")
    duration: Optional[int | float] = Field(None, description="Media duration in seconds")
    video_format_id: Optional[str] = Field(None, description="Selected video stream format_id for merging")
    audio_format_id: Optional[str] = Field(None, description="Selected audio stream format_id for merging")
    merge_streams: Optional[bool] = Field(False, description="Whether to merge separate video and audio streams")
    merge_output_format: Optional[str] = Field(None, description="Target merged container ('mp4', 'webm', 'mkv')")
    is_merge_operation: Optional[bool] = Field(False, description="Whether this task is a custom stream pair merge")


class StreamPairValidationRequest(BaseModel):
    video_stream: Optional[Dict[str, Any]] = None
    audio_stream: Optional[Dict[str, Any]] = None


class OpenFolderRequest(BaseModel):
    file_path: str = Field(..., description="Absolute path of the file to open in explorer")


class OpenExternalUrlRequest(BaseModel):
    url: str = Field(..., description="External URL to open in default browser")


class SpotifyMatchRequest(BaseModel):
    url: str = Field(..., description="Spotify URL")
    title: Optional[str] = Field(None, description="Optional track title to search")


class SettingsUpdateRequest(BaseModel):
    downloads_dir: Optional[str] = None
    max_concurrent_downloads: Optional[int] = None
    default_media_type: Optional[str] = None
    ffmpeg_path: Optional[str] = None


class ValidateFFmpegRequest(BaseModel):
    ffmpeg_path: Optional[str] = None


class SearchFeedbackRequest(BaseModel):
    query: str
    selected_id: str
    selected_title: str
    selected_url: str
    is_mismatch: Optional[bool] = False
    reason: Optional[str] = None
    provider: Optional[str] = "youtube"


class TrainModelRequest(BaseModel):
    epochs: Optional[int] = 5


class LearnDocRequest(BaseModel):
    content: str = Field(..., description="Raw text, markdown notes, or Google Doc/Drive URL")
    is_url: Optional[bool] = None
    epochs: Optional[int] = 5


@router.get("/health")
async def health_check():
    """System health check and dependency detection."""
    configured_ffmpeg = settings_store.get_settings().get("ffmpeg_path")
    engine_status = get_engine_health(custom_ffmpeg_path=configured_ffmpeg)
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

    # 2. Extract media info asynchronously using configured FFmpeg location
    try:
        configured_ffmpeg = settings_store.get_settings().get("ffmpeg_path")
        info = await asyncio.to_thread(extract_media_info, validated_url, None, configured_ffmpeg)
        return info
    except MediaEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


@router.post("/validate-pairing")
async def validate_pairing_endpoint(req: ValidatePairingRequest):
    """Validate compatibility between a selected video stream and audio stream."""
    configured_ffmpeg = settings_store.get_settings().get("ffmpeg_path")
    ffmpeg_status = validate_ffmpeg_path(configured_ffmpeg)
    return validate_stream_pairing(
        video_stream=req.video_stream,
        audio_stream=req.audio_stream,
        ffmpeg_available=ffmpeg_status["available"],
    )


@router.post("/download")
async def start_download(req: DownloadRequest):
    """Queue a media download task."""
    try:
        validated_url = validate_media_url(req.url)
    except SecurityValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Reject Spotify URLs (protected DRM music streams)
    spotify_match = detect_spotify_source(validated_url)
    if spotify_match:
        raise HTTPException(
            status_code=400,
            detail=(
                "Spotify music streams are protected by Digital Rights Management (DRM) "
                "and cannot be exported as MP3 files. To listen offline, use the official "
                "Spotify desktop or mobile application."
            ),
        )

    format_selector = req.format_id or "bestvideo+bestaudio/best"
    target_ext = req.ext or "mp4"
    media_type = req.media_type or "video"

    if (req.merge_streams or req.is_merge_operation) and req.video_format_id and req.audio_format_id:
        format_selector = f"{req.video_format_id}+{req.audio_format_id}"
        target_ext = req.merge_output_format or req.ext or "mp4"
        media_type = "video"
    elif req.video_format_id and req.audio_format_id:
        format_selector = f"{req.video_format_id}+{req.audio_format_id}"
        target_ext = req.merge_output_format or req.ext or "mp4"
        media_type = "video"
    elif req.merge_streams and req.video_format_id:
        format_selector = str(req.video_format_id)
        if req.merge_output_format:
            target_ext = req.merge_output_format

    task_id = task_manager.create_task(
        url=validated_url,
        title=req.title or "Media Download",
        format_id=format_selector,
        media_type=media_type,
        ext=target_ext,
        audio_bitrate=req.audio_bitrate or "320k",
        thumbnail=req.thumbnail,
        duration=req.duration,
        merge_output_format=req.merge_output_format,
    )

    return {"task_id": task_id, "status": "queued"}


@router.post("/streams/validate-pair")
async def validate_streams_endpoint(req: StreamPairValidationRequest):
    """Validate compatibility and container choice for pairing two streams."""
    return validate_stream_pair(req.video_stream, req.audio_stream)


@router.post("/spotify/match")
async def match_spotify_track(req: SpotifyMatchRequest):
    """Find an authorized public media source match (such as YouTube) for a Spotify track."""
    try:
        validated_url = validate_media_url(req.url)
    except SecurityValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    spotify_match = detect_spotify_source(validated_url)
    if not spotify_match:
        raise HTTPException(status_code=400, detail="The provided URL is not a recognized Spotify source.")

    query = req.title
    thumbnail = None
    if not query:
        oembed = await asyncio.to_thread(fetch_spotify_oembed, spotify_match["canonical_url"])
        query = oembed.get("title") or spotify_match.get("title")
        thumbnail = oembed.get("thumbnail")

    if not query or query in ("Spotify Track", "Spotify Content"):
        raise HTTPException(
            status_code=400,
            detail="Could not determine track title from Spotify URL to find an audio match."
        )

    try:
        configured_ffmpeg = settings_store.get_settings().get("ffmpeg_path")
        matched_info = await asyncio.to_thread(
            find_spotify_match,
            query=query,
            original_url=spotify_match["canonical_url"],
            original_title=query,
            original_thumbnail=thumbnail,
            ffmpeg_location=configured_ffmpeg,
        )
        return matched_info
    except MediaEngineError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error matching Spotify track: {e}")


@router.post("/open-url")
async def open_external_url(req: OpenExternalUrlRequest):
    """Safely open an authorized external service URL (such as Spotify) in the system browser."""
    try:
        validated_url = validate_media_url(req.url)
    except SecurityValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    spotify_match = detect_spotify_source(validated_url)
    if not spotify_match:
        raise HTTPException(
            status_code=400,
            detail="Only recognized external service URLs (such as Spotify) can be opened through this action."
        )

    try:
        import webbrowser
        opened = await asyncio.to_thread(webbrowser.open, validated_url)
        return {"status": "opened", "url": validated_url, "success": opened}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to open URL in browser: {e}")


@router.get("/search/suggestions")
async def search_suggestions_endpoint(
    q: str,
    response: Response,
    limit: int = 6,
    media_type: Optional[str] = "all",
    engine_mode: Optional[str] = Query("rei", alias="engine_mode"),
    model: Optional[str] = None,
):
    """Smart autocomplete and intelligent song discovery from genuine evidence."""
    clean_q = q.strip()
    selected_mode = (model or engine_mode or "rei").lower()
    is_flash = "flash" in selected_mode
    mode_name = "flash" if is_flash else "rei"
    model_label = "KON Search 1.2 Rei Flash" if is_flash else "KON Search 1.2 Rei"

    if not clean_q:
        return {
            "query": "",
            "suggestions": [],
            "count": 0,
            "product": model_label,
            "model": model_label,
            "engine": model_label,
            "engine_mode": mode_name,
        }

    clamped_limit = min(max(limit, 1), 12)
    from backend.search.suggestions import get_shared_suggestion_engine

    engine = get_shared_suggestion_engine()
    response.headers["X-KON-Search-Engine"] = model_label

    suggestions = await asyncio.to_thread(
        engine.get_suggestions,
        query=clean_q,
        limit=clamped_limit,
        media_type=media_type or "all",
        engine_mode=mode_name,
    )

    return {
        "query": clean_q,
        "suggestions": suggestions,
        "count": len(suggestions),
        "product": model_label,
        "model": model_label,
        "engine": model_label,
        "engine_mode": mode_name,
    }


@router.delete("/search/suggestions/history")
async def clear_suggestion_history_endpoint():
    """Clear local suggestion memory and query refinements."""
    from backend.search.adaptive_suggestions import get_shared_adaptive_store
    store = get_shared_adaptive_store()
    return store.clear_history()


@router.get("/search/suggestions/history")
async def get_suggestion_history_endpoint():
    """Get statistics and summary of local adaptive suggestion history."""
    from backend.search.adaptive_suggestions import get_shared_adaptive_store
    store = get_shared_adaptive_store()
    return store.get_stats()


@router.get("/search")
async def search_media_endpoint(
    q: str,
    response: Response,
    limit: int = 20,
    media_type: Optional[str] = "all",
    provider: Optional[str] = None,
    engine_mode: Optional[str] = Query("rei", alias="engine_mode"),
    model: Optional[str] = None,
):
    """Search for media across supported public providers and return ranked results."""
    from backend.search.engine import SearchEngine
    clean_q = q.strip()
    if not clean_q:
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")

    selected_mode = (model or engine_mode or "rei").lower()
    is_flash = "flash" in selected_mode
    mode_name = "flash" if is_flash else "rei"
    model_label = "KON Search 1.2 Rei Flash" if is_flash else "KON Search 1.2 Rei"

    clamped_limit = min(max(limit, 1), 50)
    configured_ffmpeg = settings_store.get_settings().get("ffmpeg_path")
    from backend.search.engine import SearchEngine
    engine = SearchEngine()
    active_engine = engine.get_active_engine()
    response.headers["X-KON-Search-Engine"] = active_engine
    response.headers["X-KON-Search-Model"] = model_label

    results = await asyncio.to_thread(
        engine.search,
        query=clean_q,
        limit=clamped_limit,
        media_type=media_type or "all",
        preferred_provider=provider,
        ffmpeg_path=configured_ffmpeg,
        engine_mode=mode_name,
    )
    agg_status = getattr(engine.aggregator, "last_status", {})
    return {
        "query": clean_q,
        "media_type": media_type or "all",
        "count": len(results),
        "engine": active_engine,
        "product": model_label,
        "model": model_label,
        "engine_mode": mode_name,
        "status": "complete" if agg_status.get("is_complete", True) else "partial",
        "providers_completed": agg_status.get("completed", []),
        "providers_timed_out": agg_status.get("timed_out", []),
        "providers_failed": agg_status.get("failed", []),
        "results": results,
    }


@router.get("/search/live")
async def search_live_endpoint(
    request: Request,
    response: Response,
    q: str,
    limit: int = 20,
    media_type: Optional[str] = "all",
    provider: Optional[str] = None,
    engine_mode: Optional[str] = Query("rei", alias="engine_mode"),
    model: Optional[str] = None,
):
    """Server-Sent Events (SSE) live search streaming real-time status and incremental candidates."""
    clean_q = q.strip()
    if not clean_q:
        raise HTTPException(status_code=400, detail="Search query cannot be empty.")

    selected_mode = (model or engine_mode or "rei").lower()
    is_flash = "flash" in selected_mode
    mode_name = "flash" if is_flash else "rei"
    model_label = "KON Search 1.2 Rei Flash" if is_flash else "KON Search 1.2 Rei"

    clamped_limit = min(max(limit, 1), 50)
    configured_ffmpeg = settings_store.get_settings().get("ffmpeg_path")
    from backend.search.engine import SearchEngine
    engine = SearchEngine()

    async def event_generator():
        try:
            async for event in engine.search_live_stream(
                query=clean_q,
                limit=clamped_limit,
                media_type=media_type or "all",
                preferred_provider=provider,
                ffmpeg_path=configured_ffmpeg,
                engine_mode=mode_name,
            ):
                if await request.is_disconnected():
                    break
                payload = json.dumps(event, ensure_ascii=False)
                yield f"data: {payload}\n\n"
        except asyncio.CancelledError:
            pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-KON-Search-Engine": model_label,
        },
    )


@router.post("/search/feedback")
async def search_feedback_endpoint(req: SearchFeedbackRequest):
    """Record user result confirmation or reported mismatch for continuous learning."""
    from backend.search.engine import SearchEngine
    engine = SearchEngine()
    entry = engine.record_feedback(
        query=req.query,
        selected_id=req.selected_id,
        selected_title=req.selected_title,
        selected_url=req.selected_url,
        is_mismatch=req.is_mismatch or False,
        reason=req.reason,
        provider=req.provider or "youtube",
    )
    try:
        from backend.search.learning.data_collector import get_learning_data_collector
        collector = get_learning_data_collector()
        collector.record_event(
            query=req.query,
            candidate_id=req.selected_id,
            candidate_title=req.selected_title,
            candidate_url=req.selected_url,
            event_type="mismatch" if req.is_mismatch else "select",
            reason=req.reason,
        )
    except Exception:
        pass
    return {"status": "recorded", "entry": entry}


@router.post("/search/train")
async def train_search_model_endpoint(req: Optional[TrainModelRequest] = None):
    """Trigger an autonomous batch learning pass over feedback history and downloaded media."""
    from backend.search.engine import SearchEngine
    engine = SearchEngine()
    epochs = req.epochs if req and req.epochs else 5
    downloads = history_store.get_all()
    metrics = await asyncio.to_thread(engine.self_train, download_history=downloads, epochs=epochs)
    return metrics


@router.get("/search/model-stats")
async def search_model_stats_endpoint():
    """Retrieve diagnostic health, learned vocabulary size, and loss stats for the learning ranker."""
    from backend.search.engine import SearchEngine
    engine = SearchEngine()
    stats = engine.learning_model.get_stats()
    try:
        from backend.search.continuous_trainer import get_continuous_trainer
        trainer = get_continuous_trainer()
        stats["continuous_training"] = trainer.get_telemetry()
    except Exception:
        pass
    return stats


@router.post("/search/train/continuous/start")
async def start_continuous_training_endpoint():
    """Start or resume perpetual, non-stop autonomous model training in the background."""
    from backend.search.continuous_trainer import get_continuous_trainer
    trainer = get_continuous_trainer()
    return trainer.start()


@router.post("/search/train/continuous/stop")
async def stop_continuous_training_endpoint():
    """Pause or stop perpetual, non-stop autonomous model training."""
    from backend.search.continuous_trainer import get_continuous_trainer
    trainer = get_continuous_trainer()
    return trainer.stop()


@router.get("/search/train/continuous/status")
async def continuous_training_status_endpoint():
    """Retrieve real-time non-stop training telemetry, epochs, loss curve, and throughput."""
    from backend.search.continuous_trainer import get_continuous_trainer
    trainer = get_continuous_trainer()
    return trainer.get_telemetry()


@router.post("/search/learn-doc")
async def learn_from_doc_endpoint(req: LearnDocRequest):
    """Ingest structured knowledge from a Google Doc, Drive file, or raw text note to train the ranker."""
    from backend.search.doc_learner import DocumentLearner
    clean_content = req.content.strip()
    if not clean_content:
        raise HTTPException(status_code=400, detail="Document content or URL cannot be empty.")

    epochs = req.epochs if req.epochs and req.epochs > 0 else 5
    learner = DocumentLearner()

    is_url = req.is_url
    if is_url is None:
        is_url = (
            clean_content.startswith("http://")
            or clean_content.startswith("https://")
            or "docs.google.com" in clean_content
            or "drive.google.com" in clean_content
        )

    try:
        if is_url:
            res = await asyncio.to_thread(learner.learn_from_google_doc, url_or_id=clean_content, epochs=epochs)
        else:
            res = await asyncio.to_thread(learner.learn_from_text, text_content=clean_content, epochs=epochs, source_name="Custom Notes")
        return res
    except PermissionError as pe:
        raise HTTPException(status_code=403, detail=str(pe))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to learn from document: {str(e)}")


@router.get("/search/gdrive-status")
async def gdrive_status_endpoint():
    """Check whether Google Drive CLI is installed and authenticated."""
    import shutil
    import subprocess
    has_gdrive = shutil.which("gdrive") is not None
    has_gdocs = shutil.which("gdocs") is not None
    authenticated = False
    details = ""
    if has_gdrive:
        try:
            res = subprocess.run(["gdrive", "readonly", "quota"], capture_output=True, text=True, timeout=5, check=False)
            if res.returncode == 0:
                authenticated = True
                details = res.stdout.strip()
        except Exception:
            pass
    return {
        "gdrive_installed": has_gdrive,
        "gdocs_installed": has_gdocs,
        "authenticated": authenticated,
        "details": details,
    }


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


@router.post("/tasks/{task_id}/retry")
async def retry_download_task(task_id: str):
    """Retry a failed or cancelled task."""
    success = task_manager.retry_task(task_id)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Task could not be retried. Only failed or cancelled tasks can be retried."
        )
    return {"task_id": task_id, "status": "queued"}


@router.post("/tasks/clear-finished")
async def clear_finished_tasks():
    """Dismiss all completed, failed, or cancelled tasks from the active monitor."""
    cleared_ids = task_manager.clear_finished_tasks()
    return {"cleared_ids": cleared_ids, "count": len(cleared_ids)}


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


@router.post("/settings/validate-ffmpeg")
async def validate_custom_ffmpeg(req: ValidateFFmpegRequest):
    """Test and validate an FFmpeg path without saving it."""
    return validate_ffmpeg_path(req.ffmpeg_path)


@router.post("/open-folder")
async def open_download_file(req: OpenFolderRequest):
    """Safely open Windows File Explorer with the downloaded file or downloads directory."""
    raw_path = (req.file_path or "").strip()
    configured_dir = Path(settings_store.get_settings().get("downloads_dir", str(DOWNLOADS_DIR)))
    target = Path(raw_path) if raw_path else configured_dir
    success = open_in_file_explorer(target, allowed_root=configured_dir)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Could not open file in Explorer. Path may be invalid or outside downloads directory."
        )
    return {
        "status": "opened",
        "path": str(target.resolve()),
        "directory": str(configured_dir.resolve()),
    }


@router.get("/downloads/{filename:path}")
async def download_file_to_browser(filename: str):
    """Serve a downloaded media file directly to the browser for saving."""
    configured_dir = Path(settings_store.get_settings().get("downloads_dir", str(DOWNLOADS_DIR)))
    target = (configured_dir / filename).resolve()
    if not target.is_relative_to(configured_dir.resolve()):
        raise HTTPException(status_code=403, detail="Access denied.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk.")

    return FileResponse(
        path=str(target),
        filename=target.name,
        media_type="application/octet-stream",
    )


@router.get("/stream/{filename:path}")
async def stream_media_file(filename: str):
    """Stream a downloaded media file directly for in-browser playback."""
    import mimetypes
    configured_dir = Path(settings_store.get_settings().get("downloads_dir", str(DOWNLOADS_DIR)))
    target = (configured_dir / filename).resolve()
    if not target.is_relative_to(configured_dir.resolve()):
        raise HTTPException(status_code=403, detail="Access denied.")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="File not found on disk.")

    mime, _ = mimetypes.guess_type(str(target))
    return FileResponse(
        path=str(target),
        media_type=mime or "video/mp4",
    )


@router.get("/audio/resolve")
async def resolve_audio_endpoint(
    url: str = Query(..., description="Media or song URL to resolve for playback"),
    title: Optional[str] = Query(None, description="Song title"),
    id: Optional[str] = Query(None, description="Candidate ID"),
):
    """Resolve an audio stream for preview playback before downloading."""
    from backend.engine.audio_service import resolve_audio_stream

    configured_dir = Path(settings_store.get_settings().get("downloads_dir", str(DOWNLOADS_DIR)))
    result = await resolve_audio_stream(
        url=url,
        title=title,
        candidate_id=id,
        downloads_dir=configured_dir,
        history_store=history_store,
    )
    return result


@router.get("/audio/stream")
async def stream_audio_proxy_endpoint(
    url: str = Query(..., description="Direct upstream audio stream URL"),
    request: Request = None,
):
    """Proxy remote audio stream with byte-range HTTP 206 and HLS-to-MP3 transcoding support."""
    from urllib.parse import unquote
    import httpx

    target_url = unquote(url).strip()
    if not target_url.startswith("http://") and not target_url.startswith("https://"):
        raise HTTPException(status_code=400, detail="Invalid audio stream URL scheme")

    # If the stream is an HLS m3u8 playlist (e.g. SoundCloud), transcode to progressive MP3 on the fly
    is_hls = ".m3u8" in target_url or "m3u8_native" in target_url
    if is_hls:
        from backend.engine.ffmpeg_manager import validate_ffmpeg_path
        ffmpeg_status = validate_ffmpeg_path()
        if ffmpeg_status["available"]:
            ffmpeg_bin = ffmpeg_status["path"]
            cmd = [
                ffmpeg_bin,
                "-loglevel", "error",
                "-reconnect", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "5",
                "-i", target_url,
                "-vn",
                "-f", "mp3",
                "-c:a", "libmp3lame",
                "-b:a", "128k",
                "pipe:1",
            ]
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )

            async def hls_mp3_iterator():
                try:
                    while True:
                        chunk = await proc.stdout.read(65536)
                        if not chunk:
                            break
                        yield chunk
                finally:
                    try:
                        proc.kill()
                        await proc.wait()
                    except Exception:
                        pass

            return StreamingResponse(
                hls_mp3_iterator(),
                status_code=200,
                headers={
                    "Content-Type": "audio/mpeg",
                    "Accept-Ranges": "none",
                    "Cache-Control": "no-cache",
                },
                media_type="audio/mpeg",
            )

    range_header = request.headers.get("range") if request else None
    upstream_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "*/*",
    }
    if range_header:
        upstream_headers["Range"] = range_header

    try:
        client = httpx.AsyncClient(follow_redirects=True, timeout=25.0)
        req = client.build_request("GET", target_url, headers=upstream_headers)
        upstream_res = await client.send(req, stream=True)
    except Exception as e:
        log.error(f"Failed to connect to upstream audio stream: {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to audio source: {str(e)}")

    status_code = upstream_res.status_code

    # Normalize MIME type: map video/mp4 container to audio/mp4 for HTML5 audio element
    raw_content_type = (upstream_res.headers.get("content-type") or "audio/mp4").lower()
    if "video/mp4" in raw_content_type:
        clean_content_type = "audio/mp4"
    elif "video/webm" in raw_content_type:
        clean_content_type = "audio/webm"
    elif "application/x-mpegurl" in raw_content_type or "vnd.apple.mpegurl" in raw_content_type:
        clean_content_type = "audio/mpeg"
    else:
        clean_content_type = raw_content_type

    response_headers = {
        "Content-Type": clean_content_type,
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=3600",
    }
    if "content-range" in upstream_res.headers:
        response_headers["Content-Range"] = upstream_res.headers["content-range"]
    if "content-length" in upstream_res.headers:
        response_headers["Content-Length"] = upstream_res.headers["content-length"]

    async def content_iterator():
        try:
            async for chunk in upstream_res.aiter_bytes(chunk_size=65536):
                yield chunk
        finally:
            await upstream_res.aclose()
            await client.aclose()

    return StreamingResponse(
        content_iterator(),
        status_code=status_code,
        headers=response_headers,
        media_type=response_headers["Content-Type"],
    )



@router.get("/lyrics")
async def get_lyrics_endpoint(
    title: str = Query(..., description="Track or song title"),
    artist: Optional[str] = Query(None, description="Artist name"),
    duration: Optional[float] = Query(None, description="Track duration in seconds"),
    file_path: Optional[str] = Query(None, description="Local audio file path if available"),
):
    """Retrieve synchronized or plain lyrics for a track, with local caching and LRCLIB integration."""
    from backend.lyrics.lyrics_service import get_lyrics_service
    service = get_lyrics_service()
    return await service.get_lyrics(
        raw_title=title,
        raw_artist=artist,
        duration=duration,
        file_path=file_path,
    )
