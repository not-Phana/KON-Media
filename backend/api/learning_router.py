"""API Router for KON Search 1.2 Autonomous Learning System."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

from backend.search.learning.data_collector import get_learning_data_collector
from backend.search.learning.model_manager import get_model_version_manager
from backend.search.learning.scheduler import get_learning_scheduler
from backend.search.learning.autonomous_pipeline import get_autonomous_pipeline

router = APIRouter(prefix="/api/learning", tags=["Autonomous Learning"])


class InteractionEventRequest(BaseModel):
    query: str
    candidate_id: str
    candidate_title: str
    event_type: str = Field(..., description="select | preview | listen | favorite | download | skip | reformulation | mismatch")
    candidate_url: Optional[str] = None
    listen_duration: Optional[float] = None
    track_duration: Optional[float] = None
    position_rank: Optional[int] = None
    engine_mode: str = "rei"
    reason: Optional[str] = None


class ToggleCollectorRequest(BaseModel):
    enabled: bool


@router.get("/telemetry")
async def get_telemetry():
    """Retrieve live autonomous learning telemetry, active model, and metrics."""
    scheduler = get_learning_scheduler()
    return scheduler.get_telemetry()


@router.post("/event")
async def record_interaction_event(payload: InteractionEventRequest):
    """Record a user search interaction signal (positive or negative)."""
    collector = get_learning_data_collector()
    entry = collector.record_event(
        query=payload.query,
        candidate_id=payload.candidate_id,
        candidate_title=payload.candidate_title,
        event_type=payload.event_type,
        candidate_url=payload.candidate_url,
        listen_duration=payload.listen_duration,
        track_duration=payload.track_duration,
        position_rank=payload.position_rank,
        engine_mode=payload.engine_mode,
        reason=payload.reason,
    )
    return {"status": "ok", "recorded": entry is not None, "entry": entry}


@router.post("/train-now")
async def trigger_training():
    """Trigger an immediate autonomous training, evaluation, and promotion cycle."""
    scheduler = get_learning_scheduler()
    res = await scheduler.trigger_cycle_now(force=True)
    return res


@router.post("/scheduler/pause")
async def pause_scheduler():
    """Pause automatic background training."""
    scheduler = get_learning_scheduler()
    return scheduler.pause()


@router.post("/scheduler/resume")
async def resume_scheduler():
    """Resume automatic background training."""
    scheduler = get_learning_scheduler()
    return scheduler.resume()


@router.post("/rollback")
async def rollback_model():
    """Roll back to previous production model version."""
    manager = get_model_version_manager()
    restored = manager.rollback()
    if not restored:
        raise HTTPException(status_code=400, detail="Cannot roll back: no previous version available in repository.")
    return {
        "status": "rolled_back",
        "restored_version": restored,
        "active_version": manager.get_active_version(),
    }


@router.post("/collector/toggle")
async def toggle_collector(payload: ToggleCollectorRequest):
    """Enable or disable learning data collection."""
    collector = get_learning_data_collector()
    new_state = collector.set_enabled(payload.enabled)
    return {"status": "ok", "is_enabled": new_state}


@router.post("/collector/clear")
async def clear_collected_data():
    """Clear all collected interaction signals."""
    collector = get_learning_data_collector()
    collector.clear()
    return {"status": "cleared"}


@router.get("/collector/export")
async def export_collected_data():
    """Export all collected interaction signals for inspection or backup."""
    collector = get_learning_data_collector()
    return collector.export_data()
