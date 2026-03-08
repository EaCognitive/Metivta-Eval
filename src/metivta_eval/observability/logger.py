"""
Structured logging for MetivitaEval.

Uses structlog for JSON-formatted, context-rich logging.
"""

from __future__ import annotations

import logging
import sys
from datetime import UTC, datetime
from functools import lru_cache
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

from ..config.toml_config import config


def _add_timestamp(_logger: WrappedLogger, _method_name: str, event_dict: EventDict) -> EventDict:
    """Add ISO timestamp to log events."""
    event_dict["timestamp"] = datetime.now(UTC).isoformat()
    return event_dict


def _add_service_info(
    _logger: WrappedLogger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """Add service metadata to log events."""
    event_dict["service"] = "metivta-eval"
    event_dict["version"] = config.meta.version
    return event_dict


def configure_logging() -> None:
    """
    Configure structured logging for the application.

    Reads configuration from config.toml and sets up:
    - JSON formatting for production
    - Console formatting for development
    - File output with rotation
    """
    log_config = config.observability.logging
    level = getattr(logging, log_config.level.upper(), logging.INFO)

    # Shared processors
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.PositionalArgumentsFormatter(),
        _add_timestamp,
        _add_service_info,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    # Format-specific processors
    if log_config.format == "json":
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard logging
    handlers: list[logging.Handler] = []

    # Console handler
    if log_config.output in ("stdout", "both"):
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        handlers.append(console_handler)

    # File handler with rotation
    if log_config.output in ("file", "both"):
        log_path = Path(log_config.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            filename=str(log_path),
            maxBytes=log_config.max_size_mb * 1024 * 1024,
            backupCount=log_config.max_backups,
        )
        file_handler.setLevel(level)
        handlers.append(file_handler)

    # Configure root logger
    logging.basicConfig(
        level=level,
        handlers=handlers,
        force=True,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


@lru_cache(maxsize=128)
def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables for all subsequent log calls in this context.

    Args:
        **kwargs: Key-value pairs to bind
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()


def log_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    *,
    request_context: dict[str, str | None] | None = None,
) -> None:
    """
    Log an HTTP request.

    Args:
        method: HTTP method
        path: Request path
        status_code: Response status code
        duration_ms: Request duration in milliseconds
        request_context: Optional request metadata such as request_id and user_id
    """
    logger = get_logger("http")
    context = request_context or {}
    logger.info(
        "http.request",
        method=method,
        path=path,
        status=status_code,
        duration_ms=round(duration_ms, 2),
        request_id=context.get("request_id"),
        user_id=context.get("user_id"),
    )


def log_evaluation_started(
    evaluation_id: str,
    mode: str,
    dataset: str,
    user_id: str | None = None,
) -> None:
    """
    Log evaluation start.

    Args:
        evaluation_id: Unique evaluation ID
        mode: Evaluation mode (daat/mteb)
        dataset: Dataset name
        user_id: Optional user ID
    """
    logger = get_logger("evaluation")
    logger.info(
        "evaluation.started",
        evaluation_id=evaluation_id,
        mode=mode,
        dataset=dataset,
        user_id=user_id,
    )


def log_evaluation_progress(
    evaluation_id: str,
    progress: int,
    metrics: dict[str, float] | None = None,
) -> None:
    """
    Log evaluation progress.

    Args:
        evaluation_id: Unique evaluation ID
        progress: Progress percentage (0-100)
        metrics: Optional current metrics
    """
    logger = get_logger("evaluation")
    logger.info(
        "evaluation.progress",
        evaluation_id=evaluation_id,
        progress=progress,
        metrics=metrics or {},
    )


def log_evaluation_completed(
    evaluation_id: str,
    duration_seconds: float,
    overall_score: float,
    metrics: dict[str, float] | None = None,
) -> None:
    """
    Log evaluation completion.

    Args:
        evaluation_id: Unique evaluation ID
        duration_seconds: Total duration in seconds
        overall_score: Final overall score
        metrics: Optional detailed metrics
    """
    logger = get_logger("evaluation")
    logger.info(
        "evaluation.completed",
        evaluation_id=evaluation_id,
        duration_seconds=round(duration_seconds, 2),
        overall_score=round(overall_score, 4),
        metrics=metrics or {},
    )


def log_evaluation_failed(
    evaluation_id: str,
    error: str,
    error_type: str | None = None,
) -> None:
    """
    Log evaluation failure.

    Args:
        evaluation_id: Unique evaluation ID
        error: Error message
        error_type: Optional error type/class
    """
    logger = get_logger("evaluation")
    logger.error(
        "evaluation.failed",
        evaluation_id=evaluation_id,
        error=error,
        error_type=error_type,
    )


def log_api_key_event(
    event: str,
    user_id: str,
    key_id: str | None = None,
    key_name: str | None = None,
) -> None:
    """
    Log API key management events.

    Args:
        event: Event type (created, revoked, used)
        user_id: User ID
        key_id: Optional key ID
        key_name: Optional key name
    """
    logger = get_logger("security")
    logger.info(
        f"api_key.{event}",
        user_id=user_id,
        key_id=key_id,
        key_name=key_name,
    )


def log_auth_event(
    event: str,
    user_id: str | None = None,
    email: str | None = None,
    success: bool = True,
    reason: str | None = None,
) -> None:
    """
    Log authentication events.

    Args:
        event: Event type (login, logout, register, token_refresh)
        user_id: Optional user ID
        email: Optional email
        success: Whether the event was successful
        reason: Optional failure reason
    """
    logger = get_logger("security")
    log_func = logger.info if success else logger.warning
    log_func(
        f"auth.{event}",
        user_id=user_id,
        email=email,
        success=success,
        reason=reason,
    )
