"""
Observability package for MetivitaEval.

Provides structured logging, tracing, and metrics.
"""

from .logger import (
    configure_logging,
    get_logger,
    log_evaluation_completed,
    log_evaluation_failed,
    log_evaluation_progress,
    log_evaluation_started,
    log_request,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "log_evaluation_started",
    "log_evaluation_progress",
    "log_evaluation_completed",
    "log_evaluation_failed",
    "log_request",
]
