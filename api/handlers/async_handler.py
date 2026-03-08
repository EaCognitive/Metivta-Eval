"""Celery-backed async handler for legacy Flask submission routes."""

from __future__ import annotations

from typing import Any

from api.database.supabase_manager import DatabaseManager


def get_task_status(task_id: str) -> dict[str, Any] | None:
    """Get current task status from the canonical evaluation store."""
    db = DatabaseManager()
    evaluation = db.get_evaluation(task_id)
    if evaluation is None:
        return None

    state_map = {
        "pending": "PENDING",
        "running": "PROGRESS",
        "completed": "SUCCESS",
        "failed": "FAILURE",
        "cancelled": "FAILURE",
    }
    state = state_map.get(evaluation["status"], "PENDING")
    response: dict[str, Any] = {
        "state": state,
        "status": evaluation["status"].replace("_", " ").title(),
        "progress": int(evaluation.get("progress", 0)),
    }

    if state == "SUCCESS":
        scores = evaluation.get("scores", {})
        response["result"] = {
            "submission_id": evaluation["id"],
            "scores": scores,
            "evaluators_run": list(scores.keys()),
            "message": f"Successfully evaluated with {len(scores)} evaluators",
        }

    if state == "FAILURE" and evaluation.get("error_message"):
        response["error"] = evaluation["error_message"]

    return response


def submit_evaluation(
    submission_data: dict[str, Any],
    api_key_id: str,
    evaluation_id: str,
    dataset_name: str,
) -> str:
    """Submit evaluation for async processing via Celery."""
    try:
        from api.workers.celery_app import evaluate_submission_task

        task = evaluate_submission_task.apply_async(
            kwargs={
                "evaluation_id": evaluation_id,
                "submission_data": submission_data,
                "api_key_id": api_key_id,
                "dataset_name": dataset_name,
            },
            task_id=evaluation_id,
        )
    except Exception as exc:
        raise RuntimeError("Async evaluation backend is unavailable.") from exc
    return str(task.id)
