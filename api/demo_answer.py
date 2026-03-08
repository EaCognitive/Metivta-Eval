"""Demo answer API backed by the configured dataset."""

from __future__ import annotations

from typing import Any

from flask import Flask, request

from metivta_eval.dataset_loader import load_dataset_examples, resolve_dataset_file_path

app = Flask(__name__)


def _load_answers() -> dict[str, str]:
    """Load deterministic question-to-answer mappings from the dataset."""
    answers: dict[str, str] = {}
    for item in load_dataset_examples():
        inputs = item.get("inputs", {})
        outputs = item.get("outputs", {})
        question = str(inputs.get("question", "")).strip()
        answer_text = str(outputs.get("answer", "")).strip()
        if question:
            answers[question] = answer_text
    return answers


ANSWER_BY_QUESTION = _load_answers()


@app.get("/health")
def health() -> tuple[dict[str, Any], int]:
    """Return service liveness and dataset metadata."""
    return (
        {
            "status": "healthy",
            "questions": len(ANSWER_BY_QUESTION),
            "dataset_path": str(resolve_dataset_file_path()),
        },
        200,
    )


@app.post("/answer")
def answer() -> tuple[dict[str, str], int]:
    """Return the exact dataset answer for known questions."""
    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question", "")).strip()
    answer_text = ANSWER_BY_QUESTION.get(question)
    if answer_text is None:
        return {"answer": "[Question not in dataset]"}, 404
    return {"answer": answer_text}, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=False)
