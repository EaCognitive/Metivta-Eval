"""Shared evaluator helpers."""

from typing import Any

from metivta_eval.config.config_loader import get_config_section

POSSIBLE_ANSWER_KEYS = ("answer", "output", "result", "text")


def extract_answer_text(run: Any) -> str:
    """Robustly extracts the answer string from a run's outputs."""
    outputs = getattr(run, "outputs", None) or {}
    for key in POSSIBLE_ANSWER_KEYS:
        if key in outputs:
            val = outputs[key]
            return val if isinstance(val, str) else str(val)
    # Fallback to any string-like value in the outputs
    for val in outputs.values():
        if isinstance(val, str):
            return val
    return ""


def should_provide_feedback(evaluator_name: str) -> bool:
    """Return whether the named evaluator should emit feedback text."""
    evaluator_config = get_config_section("evaluators")
    enable_feedback = evaluator_config.get("enable_llm_feedback", True)
    feedback_evaluators = evaluator_config.get("feedback_evaluators", [])
    return enable_feedback and evaluator_name in feedback_evaluators


def parse_json_score_result(
    *,
    result: Any,
    should_feedback: bool,
    error_prefix: str,
) -> tuple[float, str | None]:
    """Normalize an LLM JSON result into score and optional reasoning."""
    if not isinstance(result, dict):
        return error_score_result(
            error=TypeError(f"Unexpected result payload: {type(result).__name__}"),
            should_feedback=should_feedback,
            error_prefix=error_prefix,
        )
    score = float(result.get("score", 0.0))
    reasoning = result.get("reasoning", "No reasoning provided.") if should_feedback else None
    return score, reasoning


def error_score_result(
    *,
    error: BaseException,
    should_feedback: bool,
    error_prefix: str,
) -> tuple[float, str | None]:
    """Convert evaluator failures into a zero-score payload."""
    reasoning = f"{error_prefix}: {error}" if should_feedback else None
    return 0.0, reasoning
