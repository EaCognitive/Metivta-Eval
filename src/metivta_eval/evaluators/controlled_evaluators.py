"""LLM-assisted evaluators that compare answers against benchmark ground truth."""

from __future__ import annotations

import logging

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

CORRECTNESS_PROMPT_TEMPLATE = """
You are a controlled evaluator.
Your task is to determine if the "AI Response" is a correct answer
to the "User Question", using the "Ground Truth" as the absolute
definition of correctness.

**User Question:** {question}
**Ground Truth Answer (This is 100% correct):** {reference}
**AI Response to Evaluate:** {answer}

**Instructions:**
1.  Does the "AI Response" contain the same core information and source as the "Ground Truth"?
2.  Wording can differ, but the meaning and cited source must match.
3.  Extra correct information is acceptable.

IMPORTANT: Return ONLY a valid JSON object of the form
{{"score": <integer 0 to 1>, "reasoning": "<string>"}}.
"""


def correctness_evaluator(run, example) -> dict:
    """Compares the AI response to the ground truth reference."""
    provide_feedback = should_provide_feedback("correctness")
    chain = build_json_chain(CORRECTNESS_PROMPT_TEMPLATE)

    question = example.inputs.get("question", "")
    reference = example.outputs.get("answer", "")
    answer = extract_answer_text(run)

    if not reference or not answer:
        response = {"key": "correctness", "score": 0.0}
        if provide_feedback:
            response["comment"] = "Missing reference or answer."
        return response

    try:
        result = chain.invoke({"question": question, "reference": reference, "answer": answer})
        score, reasoning = parse_json_score_result(
            result=result,
            should_feedback=provide_feedback,
            error_prefix="Error evaluating correctness",
        )
    except anthro_error_types() as exc:
        score, reasoning = error_score_result(
            error=exc,
            should_feedback=provide_feedback,
            error_prefix="Error evaluating correctness",
        )

    # Return with or without feedback based on config
    response = {"key": "correctness", "score": score}
    if provide_feedback and reasoning:
        response["comment"] = reasoning

    return response


METIVTA_CONTROLLED_EVALUATORS = {
    "correctness": correctness_evaluator,
}
