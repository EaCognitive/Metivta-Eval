"""Shared persistence updates for evaluation lifecycle transitions."""

from __future__ import annotations

from typing import Any

from api.database.supabase_manager import DatabaseManager


def mark_evaluation_running(
    db: DatabaseManager,
    evaluation_id: str,
    *,
    progress: int,
) -> dict[str, Any] | None:
    """Persist a running-state update."""
    return db.update_evaluation(evaluation_id, status="running", progress=progress)


def mark_evaluation_completed(
    db: DatabaseManager,
    evaluation_id: str,
    scores: dict[str, float],
) -> dict[str, Any] | None:
    """Persist a completed evaluation with final scores."""
    return db.update_evaluation(
        evaluation_id,
        status="completed",
        progress=100,
        scores=scores,
        metrics=scores,
    )


def mark_evaluation_failed(
    db: DatabaseManager,
    evaluation_id: str,
    error_message: str,
) -> dict[str, Any] | None:
    """Persist a failed evaluation state."""
    return db.update_evaluation(
        evaluation_id,
        status="failed",
        progress=100,
        error_message=error_message,
    )
