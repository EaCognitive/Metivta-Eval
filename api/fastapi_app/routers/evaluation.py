"""Evaluation router with database-backed evaluation lifecycle."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID

import requests
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl

from api.database.supabase_manager import db
from api.workers.evaluation_state import (
    mark_evaluation_completed,
    mark_evaluation_failed,
    mark_evaluation_running,
)
from api.workers.evaluation_tasks import compute_submission_scores
from metivta_eval.evaluators.mteb_evaluators import MTEBEvaluators
from metivta_eval.langsmith_utils import ensure_daat_dependencies, resolve_daat_dataset_name
from metivta_eval.persistence.database import (
    EvaluationCreateRequest,
    EvaluationDescriptor,
    EvaluationIdentity,
    EvaluationLifecycle,
    EvaluationListRequest,
)

from .auth import get_current_user
from .websocket import (
    notify_evaluation_completed,
    notify_evaluation_failed,
    notify_evaluation_progress,
    notify_evaluation_started,
)

router = APIRouter()


class EvaluationMode(str, Enum):
    """Evaluation mode."""

    DAAT = "daat"
    MTEB = "mteb"


class EvaluationStatus(str, Enum):
    """Evaluation status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class EvaluationCreate(BaseModel):
    """Evaluation submission request."""

    system_name: str = Field(..., min_length=1, max_length=255)
    system_version: str | None = Field(None, max_length=50)
    endpoint_url: HttpUrl
    mode: EvaluationMode = EvaluationMode.DAAT
    dataset_name: str = Field(default="default")
    config: dict[str, Any] = Field(default_factory=dict)
    async_mode: bool = Field(default=True, description="Run evaluation asynchronously")


class EvaluationResponse(BaseModel):
    """Evaluation response."""

    id: UUID
    system_name: str
    system_version: str | None
    endpoint_url: str
    mode: EvaluationMode
    dataset_name: str
    status: EvaluationStatus
    progress: int = Field(ge=0, le=100)
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    error_message: str | None = None


class EvaluationResultsResponse(BaseModel):
    """Evaluation results response."""

    evaluation_id: UUID
    status: EvaluationStatus
    overall_score: float | None
    daat_score: float | None
    dai_score: float | None
    mla_score: float | None
    ndcg_10: float | None
    map_100: float | None
    mrr_10: float | None
    recall_100: float | None
    precision_10: float | None
    tier1_score: float | None
    tier2_score: float | None
    tier3_score: float | None
    tier4_score: float | None
    tier5_score: float | None
    metrics: dict[str, Any] = Field(default_factory=dict)
    langsmith_run_id: str | None
    trace_url: str | None
    created_at: datetime


class EvaluationListResponse(BaseModel):
    """List of evaluations response."""

    items: list[EvaluationResponse]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True, slots=True)
class EvaluationTaskRequest:
    """Persisted evaluation task payload."""

    evaluation_id: str
    user_id: str
    endpoint_url: str
    mode: str
    dataset_name: str
    system_name: str
    author: str


def _to_eval_response(payload: dict[str, Any]) -> EvaluationResponse:
    return EvaluationResponse(
        id=payload["id"],
        system_name=payload["system_name"],
        system_version=payload.get("system_version"),
        endpoint_url=payload["endpoint_url"],
        mode=EvaluationMode(payload["mode"]),
        dataset_name=payload["dataset_name"],
        status=EvaluationStatus(payload["status"]),
        progress=int(payload.get("progress", 0)),
        created_at=payload["created_at"],
        started_at=payload.get("started_at"),
        completed_at=payload.get("completed_at"),
        error_message=payload.get("error_message"),
    )


def _score_value(scores: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in scores:
            return scores[key]
    return None


def _load_mteb_templates() -> tuple[dict[str, str], dict[str, dict[str, int]]]:
    dataset_dir = Path(__file__).resolve().parents[3] / "src" / "metivta_eval" / "dataset" / "mteb"
    queries_path = dataset_dir / "queries_template.jsonl"
    qrels_path = dataset_dir / "qrels_template.tsv"

    queries: dict[str, str] = {}
    with queries_path.open(encoding="utf-8") as file_obj:
        for line in file_obj:
            row = json.loads(line)
            queries[row["_id"]] = row["text"]

    qrels: dict[str, dict[str, int]] = {}
    with qrels_path.open(encoding="utf-8") as file_obj:
        next(file_obj)
        for line in file_obj:
            query_id, doc_id, score = line.strip().split("\t")
            qrels.setdefault(query_id, {})[doc_id] = int(score)

    return queries, qrels


def _run_mteb_evaluation(endpoint_url: str) -> dict[str, float]:
    queries, qrels = _load_mteb_templates()
    results: dict[str, dict[str, float]] = {}

    for query_id, query_text in queries.items():
        response = requests.post(
            endpoint_url,
            json={"query": query_text, "top_k": 100},
            headers={"Content-Type": "application/json"},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()

        if isinstance(payload, dict) and "results" in payload:
            values = {
                str(item["id"]): float(item["score"])
                for item in payload["results"]
                if "id" in item and "score" in item
            }
        elif isinstance(payload, dict):
            values = {str(key): float(value) for key, value in payload.items()}
        else:
            values = {}

        results[query_id] = values

    evaluator = MTEBEvaluators(k_values=[10, 100])
    metrics = evaluator.evaluate_all(qrels=qrels, results=results)
    return {
        "ndcg_10": float(metrics["ndcg"].get("NDCG@10", 0.0)),
        "map_100": float(metrics["map"].get("MAP@100", 0.0)),
        "mrr_10": float(metrics["mrr"].get("MRR@10", 0.0)),
        "recall_100": float(metrics["recall"].get("Recall@100", 0.0)),
        "precision_10": float(metrics["precision"].get("P@10", 0.0)),
    }


def _validate_daat_dataset_name(dataset_name: str) -> None:
    """Reject unsupported DAAT dataset aliases before job creation."""
    configured_dataset_name = resolve_daat_dataset_name()
    if dataset_name in {"default", configured_dataset_name}:
        return

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=(
            f"Unsupported DAAT dataset_name '{dataset_name}'. Supported values: "
            f"'default' or '{configured_dataset_name}'."
        ),
    )


@router.post(
    "/",
    response_model=EvaluationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit a new evaluation",
)
async def submit_evaluation(
    evaluation: EvaluationCreate,
    background_tasks: BackgroundTasks,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> EvaluationResponse:
    """Submit a new evaluation job."""
    stored_dataset_name = evaluation.dataset_name
    if evaluation.mode == EvaluationMode.DAAT:
        _validate_daat_dataset_name(evaluation.dataset_name)
        try:
            stored_dataset_name = ensure_daat_dependencies(
                evaluation.dataset_name,
                force_refresh=True,
            )
        except RuntimeError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(exc),
            ) from exc

    initial_status = EvaluationStatus.PENDING if evaluation.async_mode else EvaluationStatus.RUNNING

    stored = db.create_evaluation(
        EvaluationCreateRequest(
            identity=EvaluationIdentity(
                user_id=current_user["id"],
                api_key_id=current_user.get("api_key_id"),
            ),
            descriptor=EvaluationDescriptor(
                system_name=evaluation.system_name,
                system_version=evaluation.system_version,
                author=current_user.get("name", evaluation.system_name),
                endpoint_url=str(evaluation.endpoint_url),
                mode=evaluation.mode.value,
                dataset_name=stored_dataset_name,
            ),
            lifecycle=EvaluationLifecycle(status=initial_status.value, progress=0),
        )
    )

    if evaluation.async_mode:
        task_request = EvaluationTaskRequest(
            evaluation_id=stored["id"],
            user_id=current_user["id"],
            endpoint_url=str(evaluation.endpoint_url),
            mode=evaluation.mode.value,
            dataset_name=stored_dataset_name,
            system_name=evaluation.system_name,
            author=current_user.get("name", evaluation.system_name),
        )
        background_tasks.add_task(
            run_evaluation_task,
            task_request=task_request,
        )
        return _to_eval_response(stored)

    await run_evaluation_task(
        EvaluationTaskRequest(
            evaluation_id=stored["id"],
            user_id=current_user["id"],
            endpoint_url=str(evaluation.endpoint_url),
            mode=evaluation.mode.value,
            dataset_name=stored_dataset_name,
            system_name=evaluation.system_name,
            author=current_user.get("name", evaluation.system_name),
        )
    )
    final = db.get_evaluation(stored["id"], current_user["id"])
    if final is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Evaluation persisted but could not be reloaded",
        )
    return _to_eval_response(final)


@router.get(
    "/",
    response_model=EvaluationListResponse,
    summary="List evaluations",
)
async def list_evaluations(
    current_user: Annotated[dict, Depends(get_current_user)],
    status_filter: EvaluationStatus | None = Query(None, alias="status"),
    mode_filter: EvaluationMode | None = Query(None, alias="mode"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> EvaluationListResponse:
    """List evaluations for current user."""
    items, total = db.list_evaluations(
        EvaluationListRequest(
            user_id=current_user["id"],
            status_filter=status_filter.value if status_filter else None,
            mode_filter=mode_filter.value if mode_filter else None,
            page=page,
            page_size=page_size,
        )
    )
    return EvaluationListResponse(
        items=[_to_eval_response(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{evaluation_id}",
    response_model=EvaluationResponse,
    summary="Get evaluation status",
)
async def get_evaluation(
    evaluation_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> EvaluationResponse:
    """Get one evaluation status."""
    item = db.get_evaluation(str(evaluation_id), current_user["id"])
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation {evaluation_id} not found",
        )
    return _to_eval_response(item)


@router.get(
    "/{evaluation_id}/results",
    response_model=EvaluationResultsResponse,
    summary="Get evaluation results",
)
async def get_evaluation_results(
    evaluation_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> EvaluationResultsResponse:
    """Get detailed results for one evaluation."""
    item = db.get_evaluation(str(evaluation_id), current_user["id"])
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Results for evaluation {evaluation_id} not found",
        )

    scores = item.get("scores", {})
    overall = scores.get("overall_score")
    if overall is None:
        numeric_values = [
            float(value) for value in scores.values() if isinstance(value, (int, float))
        ]
        overall = sum(numeric_values) / len(numeric_values) if numeric_values else None

    return EvaluationResultsResponse(
        evaluation_id=evaluation_id,
        status=EvaluationStatus(item["status"]),
        overall_score=float(overall) if overall is not None else None,
        daat_score=scores.get("daat_score"),
        dai_score=scores.get("dai_score"),
        mla_score=scores.get("mla_score"),
        ndcg_10=_score_value(scores, "ndcg_10", "NDCG@10"),
        map_100=_score_value(scores, "map_100", "MAP@100"),
        mrr_10=_score_value(scores, "mrr_10", "MRR@10"),
        recall_100=_score_value(scores, "recall_100", "Recall@100"),
        precision_10=_score_value(scores, "precision_10", "P@10"),
        tier1_score=scores.get("tier1_score"),
        tier2_score=scores.get("tier2_score"),
        tier3_score=scores.get("tier3_score"),
        tier4_score=scores.get("tier4_score"),
        tier5_score=scores.get("tier5_score"),
        metrics=item.get("metrics", {}),
        langsmith_run_id=item.get("langsmith_run_id"),
        trace_url=item.get("trace_url"),
        created_at=item["created_at"],
    )


@router.post(
    "/{evaluation_id}/cancel",
    response_model=EvaluationResponse,
    summary="Cancel a running evaluation",
)
async def cancel_evaluation(
    evaluation_id: UUID,
    current_user: Annotated[dict, Depends(get_current_user)],
) -> EvaluationResponse:
    """Cancel one evaluation."""
    cancelled = db.cancel_evaluation(str(evaluation_id), current_user["id"])
    if cancelled is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation {evaluation_id} not found or not cancellable",
        )
    return _to_eval_response(cancelled)


async def run_evaluation_task(task_request: EvaluationTaskRequest) -> None:
    """Execute a persisted evaluation run."""
    mark_evaluation_running(db, task_request.evaluation_id, progress=5)
    await notify_evaluation_started(UUID(task_request.evaluation_id), task_request.user_id)

    try:
        db.update_evaluation(task_request.evaluation_id, progress=20)
        await notify_evaluation_progress(UUID(task_request.evaluation_id), task_request.user_id, 20)

        if task_request.mode == EvaluationMode.DAAT.value:
            scores = await asyncio.to_thread(
                compute_submission_scores,
                {
                    "author": task_request.author,
                    "system_name": task_request.system_name,
                    "endpoint_url": task_request.endpoint_url,
                },
                task_request.dataset_name,
            )
        else:
            scores = await asyncio.to_thread(
                _run_mteb_evaluation,
                endpoint_url=task_request.endpoint_url,
            )

        updated = mark_evaluation_completed(db, task_request.evaluation_id, scores)
        if updated is not None:
            await notify_evaluation_completed(
                UUID(task_request.evaluation_id),
                task_request.user_id,
                updated.get("scores", {}),
            )
            await notify_evaluation_progress(
                UUID(task_request.evaluation_id),
                task_request.user_id,
                100,
                updated.get("scores", {}),
            )
        return
    except (requests.RequestException, OSError, TypeError, ValueError, KeyError) as exc:
        mark_evaluation_failed(db, task_request.evaluation_id, str(exc))
        await notify_evaluation_failed(
            UUID(task_request.evaluation_id),
            task_request.user_id,
            str(exc),
        )
