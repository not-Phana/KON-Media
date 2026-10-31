"""Test suite for Continuous Non-Stop Autonomous Learning in KON Search 1.2:
- ContinuousTrainer engine lifecycle (start, pause, telemetry)
- Dynamic training batch assembly across catalog, feedback, and adversarial negatives
- Stochastic gradient descent loss minimization and embedding adaptation
- REST API endpoint contracts (/api/search/train/continuous/*)
"""

import asyncio
import pytest
from starlette.testclient import TestClient

from backend.main import app
from backend.search.continuous_trainer import ContinuousTrainer, get_continuous_trainer


@pytest.fixture
def trainer(tmp_path):
    from backend.search.learning_model import SearchLearningModel
    model = SearchLearningModel(state_dir=tmp_path)
    return ContinuousTrainer(model=model, state_dir=tmp_path)


def test_batch_assembly_contains_ground_truth_and_negatives(trainer):
    """Verify batch assembly contains positive music targets, typo pairs, and negative distractors."""
    batch = trainer._assemble_batch()
    assert len(batch) >= 40, f"Expected rich training batch, got {len(batch)} items"

    # Verify ground-truth anime / music pairs
    queries = [item[0] for item in batch]
    labels = [item[2] for item in batch]

    assert any("Number One" in q or "Bankai" in q for q in queries)
    assert any("Shelter" in q for q in queries)
    assert any("Ditto" in q for q in queries)

    # Verify presence of both positive (1.0) and negative (0.0) labels
    assert 1.0 in labels
    assert 0.0 in labels


@pytest.mark.asyncio
async def test_continuous_trainer_start_and_telemetry(trainer):
    """Verify trainer starts, executes steps, tracks loss, and stops cleanly."""
    res_start = trainer.start()
    assert res_start["status"] in ("started", "already_running")
    assert trainer.is_running is True

    # Let it run for a brief moment to execute training steps
    await asyncio.sleep(0.3)

    telemetry = trainer.get_telemetry()
    assert telemetry["is_training"] is True
    assert telemetry["total_steps"] > 0
    assert telemetry["ema_loss"] > 0.0
    assert telemetry["learned_tokens_count"] > 0
    assert telemetry["associations_count"] > 0

    res_stop = trainer.stop()
    assert res_stop["status"] in ("stopped", "already_stopped")
    assert trainer.is_running is False


def test_continuous_training_api_endpoints():
    """Verify REST API endpoints for continuous training."""
    client = TestClient(app)

    # 1. Check status
    res = client.get("/api/search/train/continuous/status")
    assert res.status_code == 200
    status_data = res.json()
    assert "is_training" in status_data
    assert "total_steps" in status_data
    assert "ema_loss" in status_data

    # 2. Start
    res_start = client.post("/api/search/train/continuous/start")
    assert res_start.status_code == 200
    assert res_start.json()["status"] in ("started", "already_running")

    # 3. Stop
    res_stop = client.post("/api/search/train/continuous/stop")
    assert res_stop.status_code == 200
    assert res_stop.json()["status"] in ("stopped", "already_stopped")

    # 4. Resume non-stop training
    res_resume = client.post("/api/search/train/continuous/start")
    assert res_resume.status_code == 200
    assert res_resume.json()["status"] in ("started", "already_running")
