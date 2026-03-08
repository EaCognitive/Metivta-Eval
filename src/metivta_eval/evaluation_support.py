"""Shared endpoint invocation and score aggregation helpers."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import requests


def request_answer(endpoint_url: str, question: str, *, timeout: int = 30) -> str:
    """Call an answer endpoint and return the normalized answer text."""
    response = requests.post(
        endpoint_url,
        json={"question": question},
        headers={"Content-Type": "application/json"},
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    if isinstance(payload, dict):
        return str(payload.get("answer", ""))
    return ""


def safe_answer_response(endpoint_url: str, question: str, *, timeout: int = 30) -> dict[str, str]:
    """Call an answer endpoint and convert request failures into answer payloads."""
    try:
        return {"answer": request_answer(endpoint_url, question, timeout=timeout)}
    except (requests.RequestException, TypeError, ValueError) as exc:
        return {"answer": f"Error calling submission API: {exc}"}


def build_answer_target(
    endpoint_url: str,
    *,
    timeout: int = 30,
) -> Callable[[dict[str, Any]], dict[str, str]]:
    """Build the LangSmith target function for a question-answer endpoint."""

    def target(inputs: dict[str, Any]) -> dict[str, str]:
        question = str(inputs.get("question", ""))
        return safe_answer_response(endpoint_url, question, timeout=timeout)

    return target


def extract_langsmith_scores(results: Iterable[Any]) -> dict[str, float]:
    """Aggregate numeric evaluator outputs into mean scores."""
    grouped: dict[str, list[float]] = {}
    for result in results:
        if not isinstance(result, dict):
            continue

        evaluation_results = result.get("evaluation_results")
        if not isinstance(evaluation_results, dict):
            continue

        items = evaluation_results.get("results", [])
        for item in items:
            key = getattr(item, "key", None)
            score = getattr(item, "score", None)
            if key is None or score is None:
                continue
            grouped.setdefault(str(key), []).append(float(score))

    aggregated: dict[str, float] = {}
    for key, values in grouped.items():
        if values:
            aggregated[key] = sum(values) / len(values)
    return aggregated
