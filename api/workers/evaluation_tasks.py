"""Shared evaluation execution for legacy Flask submission flows."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from langsmith.evaluation import evaluate

from metivta_eval.config.config_loader import get_config_section
from metivta_eval.evaluation_support import build_answer_target, extract_langsmith_scores
from metivta_eval.evaluators import get_configured_daat_evaluators
from metivta_eval.langsmith_utils import resolve_daat_evaluation_data

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int], None]


def compute_submission_scores(
    submission_data: dict[str, Any],
    dataset_name: str,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, float]:
    """Run DAAT evaluators against a submitted endpoint and aggregate scores."""
    if progress_callback is not None:
        progress_callback("Loading evaluators...", 10)

    all_evaluators = get_configured_daat_evaluators()
    logger.info("Loading %d evaluators for evaluation", len(all_evaluators))

    if progress_callback is not None:
        progress_callback("Running evaluations...", 20)

    project_name = get_config_section("project")["name"]
    resolved_dataset_name, dataset_examples = resolve_daat_evaluation_data(dataset_name)
    logger.info(
        "Starting evaluation with dataset: %s (%d examples)",
        resolved_dataset_name,
        len(dataset_examples),
    )
    results = list(
        evaluate(
            build_answer_target(submission_data["endpoint_url"]),
            data=dataset_examples,
            evaluators=all_evaluators,
            experiment_prefix=f"{project_name} - {submission_data['system_name']}",
            metadata={
                "author": submission_data["author"],
                "system": submission_data["system_name"],
                "dataset_name": resolved_dataset_name,
                "dataset_source": "local_json",
            },
            max_concurrency=3,
            upload_results=False,
        )
    )
    logger.info("Evaluation completed, processing results")

    if progress_callback is not None:
        progress_callback("Processing results...", 80)

    scores = extract_langsmith_scores(results)
    logger.info("Evaluation complete. Scores: %s", scores)
    return scores
