"""Deterministic evaluator primitives for DAAT submissions."""

import re

from metivta_eval.config.config_loader import get_config_section

from .utils import extract_answer_text

_HEBREW_RE = re.compile(r"[\u0590-\u05FF]")
_URL_RE = re.compile(r"https?://[^\s)]+")


def hebrew_presence_evaluator(run, _example) -> dict:
    """Scores based on the presence and ratio of Hebrew text."""

    # Check if LLM feedback is enabled
    evaluator_config = get_config_section("evaluators")
    enable_feedback = evaluator_config.get("enable_llm_feedback", True)
    feedback_evaluators = evaluator_config.get("feedback_evaluators", [])

    # Check if this evaluator should provide feedback
    should_provide_feedback = enable_feedback and "hebrew_presence" in feedback_evaluators

    answer = extract_answer_text(run)
    if not answer:
        response = {"key": "hebrew_presence", "score": 0.0}
        if should_provide_feedback:
            response["comment"] = "No answer provided."
        return response

    hebrew_chars = _HEBREW_RE.findall(answer)
    total_chars = len(answer)
    ratio = len(hebrew_chars) / max(total_chars, 1)
    score = min(1.0, ratio * 5.0)  # ~20% Hebrew content gets a full score

    response = {"key": "hebrew_presence", "score": round(score, 3)}

    if should_provide_feedback:
        hebrew_count = len(hebrew_chars)
        percentage = ratio * 100
        if score >= 1.0:
            comment = (
                f"Excellent Hebrew content: {hebrew_count} Hebrew characters "
                f"({percentage:.1f}% of response)"
            )
        elif score > 0.5:
            comment = (
                f"Good Hebrew presence: {hebrew_count} Hebrew characters "
                f"({percentage:.1f}% of response)"
            )
        elif score > 0:
            comment = (
                f"Some Hebrew present: {hebrew_count} Hebrew characters "
                f"({percentage:.1f}% of response)"
            )
        else:
            comment = "No Hebrew characters found in response"
        response["comment"] = comment

    return response


def url_format_evaluator(run, _example) -> dict:
    """Scores based on the presence of a valid URL format."""
    answer = extract_answer_text(run)
    has_url = bool(_URL_RE.search(answer))
    return {"key": "url_format", "score": 1.0 if has_url else 0.0}


def response_length_evaluator(run, _example) -> dict:
    """Scores 1 if the response is non-trivial, 0 otherwise."""
    answer = extract_answer_text(run)
    score = 1.0 if answer and len(answer.strip()) >= 20 else 0.0
    return {"key": "response_length", "score": score}


METIVTA_CODE_EVALUATORS = {
    "hebrew_presence": hebrew_presence_evaluator,
    "url_format": url_format_evaluator,
    "response_length": response_length_evaluator,
}
