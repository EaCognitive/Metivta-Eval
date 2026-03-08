"""End-to-end style tests for MTEB evaluator behavior."""

from __future__ import annotations

from metivta_eval.evaluators.mteb_evaluators import MTEBEvaluators


def test_mteb_metrics_are_computed_for_valid_input() -> None:
    """Evaluator should produce all key metric groups with bounded values."""
    qrels = {
        "q1": {"d1": 2, "d2": 1},
        "q2": {"d2": 2, "d3": 1},
    }
    results = {
        "q1": {"d1": 0.9, "d2": 0.8, "d3": 0.1},
        "q2": {"d3": 0.85, "d2": 0.8, "d1": 0.2},
    }

    evaluator = MTEBEvaluators(k_values=[1, 10, 100])
    metrics = evaluator.evaluate_all(qrels=qrels, results=results)

    assert set(metrics.keys()) == {"ndcg", "map", "recall", "precision", "mrr"}
    assert "NDCG@10" in metrics["ndcg"]
    assert "MAP@100" in metrics["map"]
    assert "Recall@100" in metrics["recall"]
    assert "P@10" in metrics["precision"]
    assert "MRR@10" in metrics["mrr"]

    for group in metrics.values():
        for value in group.values():
            assert 0.0 <= value <= 1.0


def test_mteb_metrics_handle_missing_result_query() -> None:
    """Missing query results should degrade gracefully without raising."""
    qrels = {
        "q1": {"d1": 1},
        "q2": {"d2": 1},
    }
    results = {
        "q1": {"d1": 0.8},
    }

    evaluator = MTEBEvaluators(k_values=[10])
    metrics = evaluator.evaluate_all(qrels=qrels, results=results)

    assert metrics["ndcg"]["NDCG@10"] < 1.0
    assert metrics["map"]["MAP@10"] < 1.0
