"""Health and readiness router."""

from __future__ import annotations

import asyncio
import socket
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from api.database.supabase_manager import db
from metivta_eval.config.toml_config import config
from metivta_eval.langsmith_utils import DaatDependencyStatus, get_daat_dependency_status

router = APIRouter()

_DATABASE_CHECK_TIMEOUT_SECONDS = 0.75
_REDIS_SOCKET_TIMEOUT_SECONDS = 0.25
_REDIS_CHECK_TIMEOUT_SECONDS = 0.5
_DAAT_CHECK_TIMEOUT_SECONDS = 1.0


class HealthStatus(BaseModel):
    """Health check response payload."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    timestamp: str
    checks: dict[str, bool] = Field(default_factory=dict)


class ReadinessStatus(BaseModel):
    """Readiness response payload."""

    ready: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    details: dict[str, str] = Field(default_factory=dict)


@router.get(
    "/health",
    response_model=HealthStatus,
    status_code=status.HTTP_200_OK,
    summary="Health check",
)
async def health_check() -> HealthStatus:
    """Return basic service health."""
    return HealthStatus(
        status="healthy",
        version=config.meta.version,
        timestamp=datetime.now(UTC).isoformat(),
        checks={"api": True},
    )


def _check_database() -> bool:
    """Check DB connectivity."""
    try:
        with db.repo.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except (OSError, SQLAlchemyError):
        return False


def _check_redis() -> bool:
    """Check Redis connectivity if configured."""
    if config.cache.provider != "redis":
        return True

    redis_cfg = config.cache.redis
    try:
        with socket.create_connection(
            (redis_cfg.host, redis_cfg.port),
            timeout=_REDIS_SOCKET_TIMEOUT_SECONDS,
        ):
            return True
    except OSError:
        return False


async def _run_check_with_timeout(check, timeout_seconds: float) -> bool:
    """Run one readiness check in a thread and fail fast on timeout."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(check),
            timeout=timeout_seconds,
        )
    except TimeoutError:
        return False


async def _get_daat_status() -> DaatDependencyStatus:
    """Fetch DAAT status with a bounded timeout for readiness responsiveness."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(get_daat_dependency_status, force_refresh=True),
            timeout=_DAAT_CHECK_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        return DaatDependencyStatus(
            ready=False,
            dataset_name="unknown",
            message="DAAT dependency check timed out.",
        )


@router.get(
    "/ready",
    response_model=ReadinessStatus,
    status_code=status.HTTP_200_OK,
    summary="Readiness check",
)
async def readiness_check() -> ReadinessStatus:
    """Check if dependencies are reachable."""
    database_check, redis_check, daat_status = await asyncio.gather(
        _run_check_with_timeout(_check_database, _DATABASE_CHECK_TIMEOUT_SECONDS),
        _run_check_with_timeout(_check_redis, _REDIS_CHECK_TIMEOUT_SECONDS),
        _get_daat_status(),
    )
    checks = {
        "api": True,
        "database": database_check,
        "redis": redis_check,
        "daat_dataset": daat_status.ready,
    }

    return ReadinessStatus(
        ready=all(checks.values()),
        checks=checks,
        details={"daat_dataset": daat_status.message},
    )


@router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="Root endpoint",
)
async def root() -> dict[str, str]:
    """Return minimal API root metadata."""
    return {
        "name": "MetivtaEval API",
        "version": config.meta.version,
        "docs": "/api/v2/docs",
    }
