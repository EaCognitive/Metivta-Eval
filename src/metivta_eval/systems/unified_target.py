"""Unified target system that routes based on configuration."""

from __future__ import annotations

from dotenv import load_dotenv

from metivta_eval.config.config_loader import load_config
from metivta_eval.dataset_loader import load_dataset_examples, resolve_dataset_file_path
from metivta_eval.evaluation_support import safe_answer_response
from metivta_eval.llm_support import (
    anthro_error_types,
    ensure_anthropic_environment,
    generate_torah_answer,
)
from metivta_eval.observability.logger import get_logger

logger = get_logger(__name__)

# Load environment variables
load_dotenv(override=True)
ensure_anthropic_environment()


def unified_target(inputs: dict, **_kwargs) -> dict:
    """Unified target that routes based on configuration."""
    config = load_config()
    eval_config = config.get("evaluation", {})
    target_type = eval_config.get("target", "endpoint")

    logger.info(f"Using target type: {target_type}")

    if target_type == "ground_truth":
        return ground_truth_target(inputs)
    if target_type == "anthropic":
        return anthropic_target(inputs)
    if target_type == "endpoint":
        endpoint_url = eval_config.get("endpoint_url")
        if not endpoint_url:
            return {"answer": "Error: No endpoint_url configured"}
        return endpoint_target(inputs, endpoint_url)
    if target_type == "mock":
        return mock_target(inputs)
    return {"answer": f"Error: Unknown target type: {target_type}"}


def ground_truth_target(inputs: dict) -> dict:
    """Return ground truth from dataset (100% accuracy testing)."""
    dataset_path = resolve_dataset_file_path()

    try:
        dataset = load_dataset_examples(str(dataset_path))
        question = inputs.get("question", "")
        for item in dataset:
            if item["inputs"]["question"] == question:
                answer = item["outputs"]["answer"]
                logger.info("Ground truth target: Returning dataset answer")
                return {"answer": answer}

        logger.warning("Ground truth: Question not found in dataset")
        return {"answer": "[Question not found in dataset]"}

    except (OSError, TypeError, ValueError, KeyError) as exc:
        logger.error("Ground truth error: %s", exc)
        return {"answer": f"[Error loading dataset: {exc}]"}


def anthropic_target(inputs: dict) -> dict:
    """Call Claude API to generate answers."""
    try:
        answer = generate_torah_answer(inputs["question"])
        logger.info("Anthropic target: Generated answer via Claude API")
        return {"answer": answer}
    except anthro_error_types() as exc:
        logger.error("Anthropic API error: %s", exc)
        return {"answer": f"Error calling Anthropic API: {exc}"}


def endpoint_target(inputs: dict, endpoint_url: str) -> dict:
    """Call a user's API endpoint."""
    response = safe_answer_response(endpoint_url, str(inputs["question"]), timeout=30)
    if response["answer"].startswith("Error calling submission API:"):
        logger.error("Endpoint error for %s: %s", endpoint_url, response["answer"])
        return {"answer": response["answer"].replace("submission API", "endpoint", 1)}
    logger.info("Endpoint target: Called %s", endpoint_url)
    return response


def mock_target(inputs: dict) -> dict:
    """Return mock responses for testing."""
    # Simple mock that returns a standard response
    question = inputs.get("question", "")
    logger.info("Mock target: Returning mock response")
    return {
        "answer": (
            f"Mock answer for: {question[:50]}... This is a test response "
            "with Hebrew text משה רבינו and a URL https://example.com/torah"
        )
    }
