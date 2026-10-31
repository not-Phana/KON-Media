"""Background Learning Scheduler for KON Search 1.2 Rei and Rei Flash.

Key principles:
1. Low System Impact: Runs periodically without blocking music playback or active searches.
2. Resource Awareness: Micro-throttles to prevent CPU spikes on Windows 11 desktop.
3. Smart Activation: Triggers candidate training only when sufficient new interaction signals
   have been collected (default >= 5 new signals), preventing useless loops.
4. User Controls: Supports manual Start, Pause, Resume, and Disable.
"""

import asyncio
import datetime
import logging
import time
from typing import Any, Dict, Optional

from backend.search.learning.autonomous_pipeline import get_autonomous_pipeline
from backend.search.learning.data_collector import get_learning_data_collector
from backend.search.learning.model_manager import get_model_version_manager

log = logging.getLogger("kon_learning_scheduler")


class LearningScheduler:
    """Autonomous scheduler controlling background training and evaluation passes."""

    def __init__(
        self,
        check_interval_seconds: float = 60.0,
        min_new_signals: int = 5,
        pipeline: Optional[Any] = None,
        collector: Optional[Any] = None,
        model_manager: Optional[Any] = None,
    ):
        self.check_interval = check_interval_seconds
        self.min_new_signals = min_new_signals
        self.pipeline = pipeline or get_autonomous_pipeline()
        self.collector = collector or get_learning_data_collector()
        self.model_manager = model_manager or get_model_version_manager()

        self._task: Optional[asyncio.Task] = None
        self._is_running: bool = False
        self._is_paused: bool = False
        self._status: str = "idle"  # "idle" | "collecting" | "training" | "evaluating" | "promoting" | "paused" | "failed"
        self._last_processed_event_count: int = 0
        self._last_run_time: Optional[str] = None
        self._total_cycles_completed: int = 0

    @property
    def status(self) -> str:
        if self._is_paused:
            return "paused"
        return self._status

    @property
    def is_running(self) -> bool:
        return self._is_running

    def start(self) -> Dict[str, Any]:
        """Start the background scheduler task."""
        if self._is_running:
            return {"status": "already_running", "scheduler_status": self.status}

        self._is_running = True
        self._is_paused = False
        self._status = "idle"
        loop = asyncio.get_event_loop()
        self._task = loop.create_task(self._scheduler_loop())
        log.info("Autonomous learning scheduler started.")
        return {"status": "started", "scheduler_status": self.status}

    def pause(self) -> Dict[str, Any]:
        """Pause automated scheduling."""
        self._is_paused = True
        self._status = "paused"
        log.info("Autonomous learning scheduler paused.")
        return {"status": "paused", "scheduler_status": self.status, "is_running": self._is_running, "is_paused": self._is_paused}

    def resume(self) -> Dict[str, Any]:
        """Resume automated scheduling."""
        self._is_paused = False
        self._status = "idle"
        log.info("Autonomous learning scheduler resumed.")
        return {"status": "resumed", "scheduler_status": self.status, "is_running": self._is_running, "is_paused": self._is_paused}

    def stop(self) -> Dict[str, Any]:
        """Stop automated scheduling."""
        self._is_running = False
        self._is_paused = False
        self._status = "stopped"
        if self._task and not self._task.done():
            self._task.cancel()
        log.info("Autonomous learning scheduler stopped.")
        return {"status": "stopped", "scheduler_status": self.status}

    async def trigger_cycle_now(self, force: bool = True) -> Dict[str, Any]:
        """Manually trigger an immediate training and evaluation cycle."""
        if self._status in ("training", "evaluating", "promoting"):
            return {"status": "busy", "scheduler_status": self._status}

        self._status = "training"
        try:
            # Run in worker thread to prevent blocking asyncio event loop
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, self.pipeline.run_training_cycle, 3, force)
            self._last_run_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self._total_cycles_completed += 1
            self._last_processed_event_count = len(self.collector.get_all())
            self._status = "idle" if not self._is_paused else "paused"
            return result
        except Exception as e:
            self._status = "failed"
            log.error("Manual training cycle failed: %s", e)
            return {"status": "error", "error": str(e)}

    async def _scheduler_loop(self):
        """Main periodic check loop."""
        log.info("Scheduler loop initialized.")
        while self._is_running:
            try:
                await asyncio.sleep(self.check_interval)
                if not self._is_running or self._is_paused:
                    continue

                total_events = len(self.collector.get_all())
                new_events = total_events - self._last_processed_event_count

                # Only train when sufficient new signals are collected
                if new_events >= self.min_new_signals:
                    self._status = "training"
                    log.info("Scheduler triggered training: %d new signals detected.", new_events)
                    loop = asyncio.get_running_loop()
                    res = await loop.run_in_executor(None, self.pipeline.run_training_cycle, 3, False)
                    self._last_run_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    self._total_cycles_completed += 1
                    self._last_processed_event_count = total_events
                    self._status = "idle"

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._status = "failed"
                log.warning("Scheduler loop encountered error (%s); resuming in 10s...", e)
                await asyncio.sleep(10.0)
                self._status = "idle"

    def get_telemetry(self) -> Dict[str, Any]:
        """Return comprehensive telemetry of the learning system."""
        manifest = self.model_manager.get_manifest()
        active_version = manifest.get("active_version", "v1.2.0")
        active_meta = manifest.get("versions", {}).get(active_version, {})
        last_run = self.pipeline.get_last_run_result()
        stats = self.collector.get_stats()

        return {
            "status": self.status,
            "is_running": self._is_running,
            "is_paused": self._is_paused,
            "active_model_version": active_version,
            "previous_model_version": manifest.get("previous_version"),
            "can_rollback": bool(manifest.get("previous_version")),
            "total_cycles_completed": self._total_cycles_completed,
            "last_cycle_at": self._last_run_time,
            "collector_stats": stats,
            "model_metadata": active_meta,
            "versions_history": list(manifest.get("versions", {}).values()),
            "last_training_result": last_run,
        }


# Singleton instance
_shared_scheduler: Optional[LearningScheduler] = None


def get_learning_scheduler() -> LearningScheduler:
    global _shared_scheduler
    if _shared_scheduler is None:
        _shared_scheduler = LearningScheduler()
    return _shared_scheduler
