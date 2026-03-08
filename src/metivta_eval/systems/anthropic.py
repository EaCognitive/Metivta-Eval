"""Anthropic-backed target for legacy compatibility and local experimentation."""

from metivta_eval.llm_support import (
    anthro_error_types,
    ensure_anthropic_environment,
    generate_torah_answer,
)

ensure_anthropic_environment()


def anthropic_sonnet_target(inputs: dict, **_kwargs) -> dict:
    """Torah Q&A system using Claude Sonnet.

    DEPRECATED: Use unified_target with evaluation.target='anthropic' instead.
    This is kept for backwards compatibility only.
    """
    try:
        answer = generate_torah_answer(inputs["question"])
        return {"answer": answer}
    except anthro_error_types() as exc:
        return {"answer": f"Error calling Anthropic API: {exc}"}
