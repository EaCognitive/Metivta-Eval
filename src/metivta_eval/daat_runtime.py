"""DAAT dataset resolution and optional LangSmith runtime helpers."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from langsmith import Client, schemas

from metivta_eval.config.config_loader import get_config_section
from metivta_eval.config.toml_config import config
from metivta_eval.dataset_loader import load_dataset_examples, resolve_dataset_file_path

_CACHE_TTL_SECONDS = 30.0
_STATUS_CACHE: dict[str, tuple[float, DaatDependencyStatus]] = {}
_STATUS_CACHE_LOCK = Lock()


@dataclass(frozen=True, slots=True)
class DaatDependencyStatus:
    """Current DAAT dataset readiness information."""

    ready: bool
    dataset_name: str
    message: str
    dataset_path: str | None = None
    example_count: int = 0
    langsmith_enabled: bool = False


def resolve_daat_dataset_name(dataset_name: str = "default") -> str:
    """Resolve the logical dataset name used for DAAT reporting."""
    if dataset_name != "default":
        return dataset_name

    dataset_config = get_config_section("dataset")
    resolved_name = str(dataset_config.get("name", "Metivta-Eval")).strip()
    if resolved_name:
        return resolved_name
    return "Metivta-Eval"


def clear_daat_dependency_cache() -> None:
    """Clear cached dependency state."""
    with _STATUS_CACHE_LOCK:
        _STATUS_CACHE.clear()


def get_daat_dependency_status(
    dataset_name: str = "default",
    *,
    force_refresh: bool = False,
) -> DaatDependencyStatus:
    """Return readiness information for DAAT evaluation."""
    resolved_name = resolve_daat_dataset_name(dataset_name)
    if not config.evaluation.daat.enabled:
        return DaatDependencyStatus(
            ready=True,
            dataset_name=resolved_name,
            message="DAAT evaluation is disabled in configuration.",
        )

    if not force_refresh:
        cached = _get_cached_status(resolved_name)
        if cached is not None:
            return cached

    status = _check_dataset_status(resolved_name)
    with _STATUS_CACHE_LOCK:
        _STATUS_CACHE[resolved_name] = (time.monotonic(), status)
    return status


def ensure_daat_dependencies(
    dataset_name: str = "default",
    *,
    force_refresh: bool = False,
) -> str:
    """Ensure the configured DAAT dataset can be loaded."""
    status = get_daat_dependency_status(dataset_name, force_refresh=force_refresh)
    if status.ready:
        return status.dataset_name
    raise RuntimeError(status.message)


def resolve_daat_evaluation_data(
    dataset_name: str = "default",
) -> tuple[str, list[schemas.Example]]:
    """Return the logical dataset name and local examples for DAAT evaluation."""
    status = get_daat_dependency_status(dataset_name, force_refresh=True)
    if not status.ready:
        raise RuntimeError(status.message)
    dataset_path = Path(status.dataset_path or resolve_dataset_file_path())
    raw_examples = load_dataset_examples(str(dataset_path))
    return status.dataset_name, _to_langsmith_examples(
        dataset_name=status.dataset_name,
        dataset_path=dataset_path,
        raw_examples=raw_examples,
    )


def langsmith_client() -> Client | None:
    """Build a LangSmith client when an API key is configured."""
    api_key = _langsmith_api_key()
    if not api_key:
        return None
    return Client(api_key=api_key)


def langsmith_upload_enabled() -> bool:
    """Return whether a LangSmith API key is configured."""
    return bool(_langsmith_api_key())


def _get_cached_status(dataset_name: str) -> DaatDependencyStatus | None:
    """Return a cached status when it is still fresh enough."""
    with _STATUS_CACHE_LOCK:
        cached = _STATUS_CACHE.get(dataset_name)

    if cached is None:
        return None

    cached_at, status = cached
    if time.monotonic() - cached_at <= _CACHE_TTL_SECONDS:
        return status
    return None


def _check_dataset_status(dataset_name: str) -> DaatDependencyStatus:
    """Check whether the local DAAT dataset file is available and valid."""
    dataset_path = resolve_dataset_file_path()
    try:
        examples = load_dataset_examples(str(dataset_path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return DaatDependencyStatus(
            ready=False,
            dataset_name=dataset_name,
            message=f"DAAT evaluation is unavailable because {exc}",
            dataset_path=str(dataset_path),
        )

    telemetry_message = (
        "Local DAAT evaluation is ready; a LangSmith API key is configured for optional sync."
        if langsmith_upload_enabled()
        else "Local DAAT evaluation is ready without LangSmith."
    )
    message = f"Loaded {len(examples)} DAAT examples from {dataset_path}. {telemetry_message}"
    return DaatDependencyStatus(
        ready=True,
        dataset_name=dataset_name,
        message=message,
        dataset_path=str(dataset_path),
        example_count=len(examples),
        langsmith_enabled=langsmith_upload_enabled(),
    )


def _to_langsmith_examples(
    dataset_name: str,
    dataset_path: Path,
    raw_examples: list[dict[str, Any]],
) -> list[schemas.Example]:
    """Convert JSON examples into LangSmith schema objects for local evaluation."""
    dataset_id = uuid5(NAMESPACE_URL, f"{dataset_name}:{dataset_path}")
    modified_at = _dataset_timestamp(dataset_path)
    examples: list[schemas.Example] = []

    for index, item in enumerate(raw_examples):
        inputs = item.get("inputs", {})
        outputs = item.get("outputs", {})
        metadata = item.get("metadata")
        question = str(inputs.get("question", ""))
        example_id = uuid5(NAMESPACE_URL, f"{dataset_id}:{index}:{question}")
        examples.append(
            schemas.Example(
                id=example_id,
                dataset_id=dataset_id,
                inputs=inputs,
                outputs=outputs,
                metadata=metadata if isinstance(metadata, dict) else None,
                created_at=modified_at,
                modified_at=modified_at,
            )
        )

    return examples


def _dataset_timestamp(dataset_path: Path) -> datetime:
    """Return a stable timestamp to attach to local DAAT examples."""
    try:
        stat = dataset_path.stat()
    except OSError:
        return datetime.now(UTC)
    return datetime.fromtimestamp(stat.st_mtime, tz=UTC)


def _langsmith_api_key() -> str:
    """Return the LangSmith API key from config or environment."""
    configured_key = config.models.langsmith.api_key.get_secret_value().strip()
    if configured_key:
        return configured_key

    for env_key in ("LANGSMITH_API_KEY", "LANGCHAIN_API_KEY"):
        env_value = os.getenv(env_key, "").strip()
        if env_value:
            return env_value

    return ""
