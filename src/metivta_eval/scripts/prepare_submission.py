#!/usr/bin/env python3
"""Prepare a user submission for evaluation."""

from __future__ import annotations

import json
import os
import sys
from typing import Any


def validate_submission(submission: list[dict[str, Any]]) -> tuple[bool, str]:
    """Validate that submission has correct format."""
    if not isinstance(submission, list):
        return False, "Submission must be a JSON array"

    for i, item in enumerate(submission):
        item_error = _validate_submission_item(item, index=i)
        if item_error:
            return False, item_error

    return True, "Valid submission"


def _validate_submission_item(item: dict[str, Any], *, index: int) -> str | None:
    """Validate one answer payload."""
    inputs = item.get("inputs")
    outputs = item.get("outputs")
    checks = (
        (isinstance(inputs, dict), f"Item {index + 1} missing 'inputs' field"),
        (isinstance(outputs, dict), f"Item {index + 1} missing 'outputs' field"),
        (
            isinstance(inputs, dict) and "question" in inputs,
            f"Item {index + 1} missing 'question' in inputs",
        ),
        (
            isinstance(outputs, dict) and "answer" in outputs,
            f"Item {index + 1} missing 'answer' in outputs",
        ),
    )
    for condition, message in checks:
        if not condition:
            return message

    validated_outputs = outputs if isinstance(outputs, dict) else {}
    answer = str(validated_outputs["answer"])
    if "<<<" in answer or ">>>" in answer or "[ENTER YOUR ANSWER" in answer:
        return f"Item {index + 1} still has placeholder text in answer"
    if not answer.strip():
        return f"Item {index + 1} has empty answer"
    return None


def prepare_for_langsmith(submission_path: str, dataset_name: str) -> dict:
    """Prepare submission for upload to LangSmith."""
    with open(submission_path, encoding="utf-8") as f:
        submission = json.load(f)

    valid, message = validate_submission(submission)
    if not valid:
        raise ValueError(f"Invalid submission: {message}")

    # Format for LangSmith
    return {
        "dataset_name": dataset_name,
        "description": "User-submitted answers for MetivitaEval",
        "examples": submission,
    }


def main() -> None:
    """Main function to prepare submission."""
    if len(sys.argv) < 2:
        print("Usage: python prepare_submission.py <submission_file.json> [dataset_name]")
        sys.exit(1)

    submission_file = sys.argv[1]
    dataset_name = sys.argv[2] if len(sys.argv) > 2 else "user-submission"

    if not os.path.exists(submission_file):
        print(f"Error: File not found: {submission_file}")
        sys.exit(1)

    try:
        # Validate submission
        with open(submission_file, encoding="utf-8") as f:
            submission = json.load(f)

        valid, message = validate_submission(submission)
        if not valid:
            print(f"❌ {message}")
            sys.exit(1)

        print(f"✅ Valid submission with {len(submission)} answers")

        # Show summary
        print("\n📊 Submission Summary:")
        for i, item in enumerate(submission, 1):
            question = (
                item["inputs"]["question"][:50] + "..."
                if len(item["inputs"]["question"]) > 50
                else item["inputs"]["question"]
            )
            answer_len = len(item["outputs"]["answer"])
            print(f"  {i}. Q: {question}")
            print(f"     A: {answer_len} characters")

        print("\n✅ Ready for evaluation!")
        print(f"📚 Dataset label: {dataset_name}")
        print("\n🚀 To evaluate, run:")
        print(f"   make evaluate SYSTEM=user_submission DATASET={submission_file}")

    except json.JSONDecodeError as exc:
        print(f"❌ Invalid JSON: {exc}")
        sys.exit(1)
    except (OSError, TypeError, ValueError, KeyError) as exc:
        print(f"❌ Error: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
