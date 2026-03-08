#!/usr/bin/env python3
"""Display available questions from the configured dataset for users to answer."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from metivta_eval.dataset_loader import (
    load_dataset_examples,
    load_questions_only_examples,
    resolve_questions_only_file_path,
)


def load_questions(dataset_path: Path) -> list[dict[str, Any]]:
    """Load questions from the questions-only dataset file."""
    if dataset_path.exists():
        return load_dataset_examples(str(dataset_path))
    return load_questions_only_examples()


def display_questions(questions: list[dict[str, Any]]) -> None:
    """Display questions in a readable format."""
    print("\n" + "=" * 80)
    print("METIVITAEVAL - AVAILABLE QUESTIONS TO ANSWER")
    print("=" * 80)

    for i, item in enumerate(questions, 1):
        inputs = item.get("inputs", {})
        question = inputs.get("question", "")
        print(f"\n📝 Question {i}:")
        print(f"   {question}")
        print("-" * 70)

    print(f"\n✅ Total questions available: {len(questions)}")
    print("\n💡 To submit answers, create a JSON file with this structure:")
    print(
        """
[
    {
        "inputs": {
            "question": "<copy question text here>"
        },
        "outputs": {
            "answer": "<your answer here>"
        }
    }
]
"""
    )


def export_template(questions: list[dict[str, Any]], output_path: Path) -> None:
    """Export a template JSON file for user submissions."""
    template = []
    for item in questions:
        inputs = item.get("inputs", {})
        template.append(
            {
                "inputs": {"question": inputs.get("question", "")},
                "outputs": {"answer": "<<<YOUR ANSWER HERE>>>"},
            }
        )

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(template, f, ensure_ascii=False, indent=4)

    print(f"\n✅ Template exported to: {output_path}")
    print("📝 Fill in your answers where it says '<<<YOUR ANSWER HERE>>>'")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Display the configured question set and optionally export a template.",
    )
    parser.add_argument(
        "--export",
        metavar="PATH",
        help="Write a submission template to PATH without prompting.",
    )
    return parser.parse_args()


def _prompt_for_export_path(dataset_path: Path) -> Path | None:
    """Prompt for an export path when stdin is interactive."""
    if not sys.stdin.isatty():
        print("\nℹ️  Non-interactive shell detected. Skipping template export prompt.")
        print("   Use --export <path> to write a template file.")
        return None

    response = input("\n📥 Would you like to export a template file? (y/n): ")
    if response.lower() != "y":
        return None

    output_name = input("Enter filename (default: my-answers.json): ").strip()
    if not output_name:
        output_name = "my-answers.json"
    if not output_name.endswith(".json"):
        output_name += ".json"
    return dataset_path.parent / output_name


def main() -> None:
    """Render the configured question set and optionally export a template."""
    args = parse_args()
    dataset_path = resolve_questions_only_file_path()
    questions = load_questions(dataset_path)
    display_questions(questions)
    if args.export:
        export_template(questions, Path(args.export).expanduser().resolve())
        return

    output_path = _prompt_for_export_path(dataset_path)
    if output_path is None:
        return
    export_template(questions, output_path)


if __name__ == "__main__":
    main()
