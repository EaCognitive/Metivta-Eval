"""Manual MTEB evaluator runner for local debugging.

This script is intentionally not discovered by pytest. It is for manual checks.
"""

from __future__ import annotations

from metivta_eval.evaluators.mteb_evaluators import MTEBEvaluators


def main() -> None:
    """Run the local MTEB evaluator against a tiny in-memory retrieval example."""
    qrels = {
        "q1": {"d1": 2, "d2": 1},
        "q2": {"d2": 2, "d3": 1},
    }
    results = {
        "q1": {"d1": 0.92, "d2": 0.87, "d3": 0.2},
        "q2": {"d2": 0.91, "d3": 0.84, "d1": 0.1},
    }

    evaluator = MTEBEvaluators(k_values=[1, 10, 100])
    metrics = evaluator.evaluate_all(qrels=qrels, results=results)
    print(evaluator.format_for_display(metrics))


if __name__ == "__main__":
    main()
