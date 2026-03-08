"""Leaderboard router backed by persisted evaluation results."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.database.supabase_manager import db

from .auth import get_current_user

router = APIRouter()


class LeaderboardMode(str, Enum):
    """Leaderboard mode filter."""

    ALL = "all"
    DAAT = "daat"
    MTEB = "mteb"


class LeaderboardEntry(BaseModel):
    """Single leaderboard row."""

    rank: int
    system_id: UUID
    system_name: str
    system_version: str | None
    author: str
    organization: str | None
    mode: str
    overall_score: float | None
    daat_score: float | None
    ndcg_10: float | None
    map_100: float | None
    mrr_10: float | None
    dataset_name: str
    submitted_at: datetime


class LeaderboardResponse(BaseModel):
    """Leaderboard list payload."""

    mode: LeaderboardMode
    entries: list[LeaderboardEntry]
    total: int
    page: int
    page_size: int
    last_updated: datetime


class LeaderboardStatsResponse(BaseModel):
    """Leaderboard aggregate stats payload."""

    total_systems: int
    total_evaluations: int
    total_users: int
    average_daat_score: float | None
    average_ndcg_10: float | None
    top_organization: str | None
    last_evaluation: datetime | None


@router.get(
    "/",
    response_model=LeaderboardResponse,
    summary="Get leaderboard",
)
async def get_leaderboard(
    mode: LeaderboardMode = Query(LeaderboardMode.ALL),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> LeaderboardResponse:
    """Return ranked leaderboard rows."""
    entries, total = db.get_leaderboard_entries(mode=mode.value, page=page, page_size=page_size)

    parsed = [
        LeaderboardEntry(
            rank=item["rank"],
            system_id=item["system_id"],
            system_name=item["system_name"],
            system_version=item.get("system_version"),
            author=item["author"],
            organization=item.get("organization"),
            mode=item["mode"],
            overall_score=item.get("overall_score"),
            daat_score=item.get("daat_score"),
            ndcg_10=item.get("ndcg_10"),
            map_100=item.get("map_100"),
            mrr_10=item.get("mrr_10"),
            dataset_name=item["dataset_name"],
            submitted_at=item["submitted_at"],
        )
        for item in entries
    ]

    last_updated = max((entry.submitted_at for entry in parsed), default=datetime.now(UTC))

    return LeaderboardResponse(
        mode=mode,
        entries=parsed,
        total=total,
        page=page,
        page_size=page_size,
        last_updated=last_updated,
    )


@router.get(
    "/stats",
    response_model=LeaderboardStatsResponse,
    summary="Get leaderboard statistics",
)
async def get_leaderboard_stats() -> LeaderboardStatsResponse:
    """Return aggregate leaderboard stats."""
    payload = db.get_leaderboard_stats()
    return LeaderboardStatsResponse(
        total_systems=payload["total_systems"],
        total_evaluations=payload["total_evaluations"],
        total_users=payload["total_users"],
        average_daat_score=payload.get("average_daat_score"),
        average_ndcg_10=payload.get("average_ndcg_10"),
        top_organization=payload.get("top_organization"),
        last_evaluation=payload.get("last_evaluation"),
    )


@router.get(
    "/my-rankings",
    response_model=list[LeaderboardEntry],
    summary="Get my rankings",
)
async def get_my_rankings(
    current_user: Annotated[dict, Depends(get_current_user)],
) -> list[LeaderboardEntry]:
    """Return leaderboard entries owned by current user."""
    entries, _ = db.get_leaderboard_entries(mode="all", page=1, page_size=500)
    mine = [item for item in entries if item["author"] == current_user.get("name")]
    return [
        LeaderboardEntry(
            rank=item["rank"],
            system_id=item["system_id"],
            system_name=item["system_name"],
            system_version=item.get("system_version"),
            author=item["author"],
            organization=item.get("organization"),
            mode=item["mode"],
            overall_score=item.get("overall_score"),
            daat_score=item.get("daat_score"),
            ndcg_10=item.get("ndcg_10"),
            map_100=item.get("map_100"),
            mrr_10=item.get("mrr_10"),
            dataset_name=item["dataset_name"],
            submitted_at=item["submitted_at"],
        )
        for item in mine
    ]


@router.get(
    "/{system_id}",
    response_model=LeaderboardEntry,
    summary="Get system ranking",
)
async def get_system_ranking(system_id: UUID) -> LeaderboardEntry:
    """Return one leaderboard entry by system/evaluation id."""
    entries, _ = db.get_leaderboard_entries(mode="all", page=1, page_size=1000)
    for item in entries:
        if item["system_id"] == str(system_id):
            return LeaderboardEntry(
                rank=item["rank"],
                system_id=item["system_id"],
                system_name=item["system_name"],
                system_version=item.get("system_version"),
                author=item["author"],
                organization=item.get("organization"),
                mode=item["mode"],
                overall_score=item.get("overall_score"),
                daat_score=item.get("daat_score"),
                ndcg_10=item.get("ndcg_10"),
                map_100=item.get("map_100"),
                mrr_10=item.get("mrr_10"),
                dataset_name=item["dataset_name"],
                submitted_at=item["submitted_at"],
            )

    raise HTTPException(status_code=404, detail=f"System {system_id} not found on leaderboard")
