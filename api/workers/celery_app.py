"""Celery application for background workers."""

from __future__ import annotations

from typing import Any

from celery import Celery

from api.database.supabase_manager import DatabaseManager
from api.workers.evaluation_state import (
    mark_evaluation_completed,
    mark_evaluation_failed,
    mark_evaluation_running,
)
from api.workers.evaluation_tasks import compute_submission_scores
from metivta_eval.config.toml_config import config

celery_app = Celery(
    "metivta_eval",
    broker=config.worker.broker,
    backend=config.worker.result_backend,
)

celery_app.conf.update(
    task_acks_late=config.worker.task_acks_late,
    task_reject_on_worker_lost=config.worker.task_reject_on_worker_lost,
    worker_prefetch_multiplier=config.worker.prefetch_multiplier,
)


@celery_app.task(name="metivta.worker.healthcheck")
def healthcheck() -> str:
    """Simple task used for worker liveness checks."""
    return "ok"


@celery_app.task(bind=True, name="metivta.worker.evaluate_submission")
def evaluate_submission_task(
    self,
    evaluation_id: str,
    submission_data: dict[str, Any],
    api_key_id: str,
    dataset_name: str,
) -> dict[str, Any]:
    """Execute one legacy Flask submission asynchronously."""
    del api_key_id
    db = DatabaseManager()
    mark_evaluation_running(db, evaluation_id, progress=5)

    def update_progress(message: str, progress: int) -> None:
        self.update_state(state="PROGRESS", meta={"status": message, "progress": progress})
        mark_evaluation_running(db, evaluation_id, progress=progress)

    try:
        scores = compute_submission_scores(
            submission_data=submission_data,
            dataset_name=dataset_name,
            progress_callback=update_progress,
        )
        mark_evaluation_completed(db, evaluation_id, scores)
        return {
            "submission_id": evaluation_id,
            "scores": scores,
            "evaluators_run": list(scores.keys()),
            "message": f"Successfully evaluated with {len(scores)} evaluators",
        }
    except (OSError, TypeError, ValueError, KeyError) as exc:
        mark_evaluation_failed(db, evaluation_id, str(exc))
        raise RuntimeError(f"Evaluation failed: {exc}") from exc
