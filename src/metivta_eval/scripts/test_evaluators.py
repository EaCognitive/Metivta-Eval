"""Manual evaluator smoke runner for local debugging."""

from __future__ import annotations

import argparse
from types import SimpleNamespace

from metivta_eval.evaluators import get_evaluators
from metivta_eval.evaluators.code_evaluators import METIVTA_CODE_EVALUATORS


def _build_mock_run(outputs: dict[str, str]) -> SimpleNamespace:
    """Build a minimal LangSmith-like run object."""
    return SimpleNamespace(outputs=outputs)


def _build_mock_example(
    inputs: dict[str, str],
    outputs: dict[str, str],
) -> SimpleNamespace:
    """Build a minimal example object matching the evaluator protocol."""
    return SimpleNamespace(inputs=inputs, outputs=outputs)


def main() -> None:
    """Run selected evaluators against a fixed in-memory example."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-only", action="store_true", help="Run code-based evaluators only.")
    args = parser.parse_args()

    print("🧪 Testing MetivitaEval evaluators locally...")
    mock_inputs = {"question": "What is the source for honoring parents?"}
    mock_outputs = {
        "answer": "The source is in שמות כ:יב. See https://www.sefaria.org/Exodus.20.12"
    }
    mock_run = _build_mock_run(outputs=mock_outputs)
    mock_example = _build_mock_example(inputs=mock_inputs, outputs=mock_outputs)

    evals_to_run = (
        list(METIVTA_CODE_EVALUATORS.values()) if args.local_only else get_evaluators(["all"])
    )

    for evaluator in evals_to_run:
        print(f"--- Running {evaluator.__name__} ---")
        try:
            result = evaluator(mock_run, mock_example)
            assert "key" in result
            assert "score" in result
            print(f"✅ SUCCESS: {result}")
        except (AssertionError, OSError, TypeError, ValueError, KeyError) as exc:
            print(f"❌ FAILED: {evaluator.__name__} raised an error: {exc}")

    print("\n✅ All selected evaluators ran. Check for any FAILED messages.")


if __name__ == "__main__":
    main()
