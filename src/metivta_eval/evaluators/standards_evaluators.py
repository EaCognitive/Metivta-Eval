"""LLM-assisted evaluators that score responses against the benchmark rubric."""

from __future__ import annotations

import json
import logging
from functools import lru_cache

from metivta_eval.config.config_loader import get_config_section
from metivta_eval.dataset_loader import resolve_dataset_asset_path
from metivta_eval.llm_support import (
    anthro_error_types,
    build_json_chain,
    ensure_anthropic_environment,
)

from .utils import (
    error_score_result,
    extract_answer_text,
    parse_json_score_result,
    should_provide_feedback,
)

logger = logging.getLogger(__name__)
ensure_anthropic_environment(logger)


@lru_cache(maxsize=1)
def _load_evaluation_standards() -> dict:
    """Load the configured scholarly format rubric."""
    dataset_config = get_config_section("dataset")
    files_config = dataset_config.get("files", {})
    rubric_name = "format_rubric.json"
    if isinstance(files_config, dict):
        configured_name = str(files_config.get("format_rubric", "")).strip()
        if configured_name:
            rubric_name = configured_name

    rubric_path = resolve_dataset_asset_path(rubric_name)
    with rubric_path.open(encoding="utf-8") as file_obj:
        return json.load(file_obj)


STANDARDS_PROMPT_TEMPLATE = """
You are a meticulous evaluator for Torah scholarship.
Compare the given response against our pre-defined standards and examples.
Be objective and base your score solely on these standards.

**Our Standards and Examples:**
1.  **Perfect Example (Score 1.0):**
    *Description:* {perfect_desc}
    *Response:* {perfect_resp}
2.  **Minimal but Correct Example (Score 0.6):**
    *Description:* {minimal_desc}
    *Response:* {minimal_resp}

**Scoring Rubric:**
{rubric}

---
**EVALUATION TASK**
**User Question:** {question}
**AI Response to Evaluate:** {answer}

---
**Instructions:**
1.  Compare the "AI Response to Evaluate" to the examples and rubric.
2.  Assign a score based on the rubric.
3.  Provide a brief justification for your score.

IMPORTANT: Return ONLY a valid JSON object of the form
{{"score": <float>, "reasoning": "<string>"}}.
Do not include any extra text before or after the JSON.
"""


def scholarly_format_evaluator(run, example) -> dict:
    """Evaluates the response format against the defined scholarly standards."""
    evaluation_standards = _load_evaluation_standards()
    provide_feedback = should_provide_feedback("scholarly_format")

    # Format the rubric as text to avoid template variable conflicts
    rubric_text = "\n".join(
        [
            f"  {score}: {description}"
            for score, description in evaluation_standards["scoring_rubric"].items()
        ]
    )

    # Create the formatted prompt with standards but keep placeholders for question/answer
    formatted_template = (
        STANDARDS_PROMPT_TEMPLATE.replace(
            "{perfect_desc}", evaluation_standards["perfect_example"]["description"]
        )
        .replace("{perfect_resp}", evaluation_standards["perfect_example"]["response"])
        .replace(
            "{minimal_desc}",
            evaluation_standards["minimal_but_correct_example"]["description"],
        )
        .replace(
            "{minimal_resp}",
            evaluation_standards["minimal_but_correct_example"]["response"],
        )
        .replace("{rubric}", rubric_text)
    )

    chain = build_json_chain(formatted_template)

    question = example.inputs.get("question", "")
    answer = extract_answer_text(run)
    if not answer:
        return {
            "key": "scholarly_format",
            "score": 0.0,
            "comment": "No answer provided." if provide_feedback else None,
        }

    try:
        result = chain.invoke({"question": question, "answer": answer})
        score, reasoning = parse_json_score_result(
            result=result,
            should_feedback=provide_feedback,
            error_prefix="Error evaluating format",
        )
    except anthro_error_types() as exc:
        score, reasoning = error_score_result(
            error=exc,
            should_feedback=provide_feedback,
            error_prefix="Error evaluating format",
        )

    # Return with or without feedback based on config
    response = {"key": "scholarly_format", "score": score}
    if provide_feedback and reasoning:
        response["comment"] = reasoning

    return response


METIVTA_STANDARDS_EVALUATORS = {
    "scholarly_format": scholarly_format_evaluator,
}
