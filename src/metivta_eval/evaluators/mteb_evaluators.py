"""
MTEB-Style Retrieval Evaluators

Implements standard MTEB/BEIR metrics for retrieval evaluation:
- nDCG@k (Normalized Discounted Cumulative Gain)
- MAP@k (Mean Average Precision)
- MRR@k (Mean Reciprocal Rank)
- Recall@k
- Precision@k

These evaluators work alongside existing DAAT evaluators.
"""

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class MTEBEvaluators:
    """
    Collection of MTEB-standard retrieval metrics

    All metrics follow BEIR/MTEB conventions:
    - Scores normalized to 0-1 range
    - Higher scores = better performance
    - Results aggregated across all queries (mean)
    """

    def __init__(self, k_values: list[int] | None = None):
        """
        Initialize evaluators with cutoff values

        Args:
            k_values: List of k values for metrics (default: [1, 3, 5, 10, 100, 1000])
        """
        self.k_values = k_values or [1, 3, 5, 10, 100, 1000]
        logger.info("Initialized MTEB evaluators with k=%s", self.k_values)

    def evaluate_all(
        self, qrels: dict[str, dict[str, int]], results: dict[str, dict[str, float]]
    ) -> dict[str, dict[str, float]]:
        """
        Compute all MTEB metrics

        Args:
            qrels: Ground truth relevance {query_id: {doc_id: score}}
            results: Retrieval results {query_id: {doc_id: similarity_score}}

        Returns:
            {
                "ndcg": {"NDCG@1": 0.5, "NDCG@10": 0.7, ...},
                "map": {"MAP@10": 0.6, ...},
                "recall": {"Recall@100": 0.8, ...},
                "precision": {"P@10": 0.7, ...},
                "mrr": {"MRR@10": 0.65, ...}
            }
        """
        logger.info("Computing all MTEB metrics...")

        return {
            "ndcg": self.compute_ndcg_all(qrels, results),
            "map": self.compute_map_all(qrels, results),
            "recall": self.compute_recall_all(qrels, results),
            "precision": self.compute_precision_all(qrels, results),
            "mrr": self.compute_mrr_all(qrels, results),
        }

    def compute_ndcg_all(
        self, qrels: dict[str, dict[str, int]], results: dict[str, dict[str, float]]
    ) -> dict[str, float]:
        """
        Compute nDCG@k for all k values

        nDCG (Normalized Discounted Cumulative Gain):
        - Measures ranking quality with position-based discounting
        - Works with graded relevance (0, 1, 2, 3)
        - Normalized by ideal ranking

        Returns:
            {"NDCG@1": 0.5, "NDCG@3": 0.6, "NDCG@10": 0.7, ...}
        """
        ndcg_scores = {}

        for k in self.k_values:
            scores = []

            for query_id in qrels:
                if query_id not in results:
                    scores.append(0.0)
                    continue

                # Get top-k results sorted by score
                sorted_results = sorted(
                    results[query_id].items(), key=lambda x: x[1], reverse=True
                )[:k]

                # Compute DCG@k
                dcg = 0.0
                for rank, (doc_id, _) in enumerate(sorted_results, 1):
                    relevance = qrels[query_id].get(doc_id, 0)
                    dcg += relevance / np.log2(rank + 1)

                # Compute IDCG@k (ideal DCG with perfect ranking)
                ideal_relevances = sorted(qrels[query_id].values(), reverse=True)[:k]
                idcg = sum(rel / np.log2(rank + 1) for rank, rel in enumerate(ideal_relevances, 1))

                # Normalize
                ndcg = dcg / idcg if idcg > 0 else 0.0
                scores.append(ndcg)

            ndcg_scores[f"NDCG@{k}"] = float(np.mean(scores)) if scores else 0.0

        return ndcg_scores

    def compute_map_all(
        self, qrels: dict[str, dict[str, int]], results: dict[str, dict[str, float]]
    ) -> dict[str, float]:
        """
        Compute MAP@k (Mean Average Precision) for all k values

        MAP:
        - Measures precision at each relevant document position
        - Binary relevance (relevant if score > 0)
        - Rewards placing relevant documents higher

        Returns:
            {"MAP@10": 0.6, "MAP@100": 0.65, ...}
        """
        map_scores = {}

        for k in self.k_values:
            scores = []

            for query_id in qrels:
                if query_id not in results:
                    scores.append(0.0)
                    continue

                # Get top-k results sorted by score
                sorted_results = sorted(
                    results[query_id].items(), key=lambda x: x[1], reverse=True
                )[:k]

                # Count relevant documents
                num_relevant = sum(1 for rel in qrels[query_id].values() if rel > 0)

                if num_relevant == 0:
                    scores.append(0.0)
                    continue

                # Compute Average Precision
                num_relevant_found = 0
                precision_sum = 0.0

                for rank, (doc_id, _) in enumerate(sorted_results, 1):
                    if qrels[query_id].get(doc_id, 0) > 0:  # Relevant
                        num_relevant_found += 1
                        precision_at_rank = num_relevant_found / rank
                        precision_sum += precision_at_rank

                ap = precision_sum / min(num_relevant, k) if num_relevant > 0 else 0.0
                scores.append(ap)

            map_scores[f"MAP@{k}"] = float(np.mean(scores)) if scores else 0.0

        return map_scores

    def compute_recall_all(
        self, qrels: dict[str, dict[str, int]], results: dict[str, dict[str, float]]
    ) -> dict[str, float]:
        """
        Compute Recall@k for all k values

        Recall@k:
        - Fraction of relevant documents found in top-k
        - Binary relevance (relevant if score > 0)
        - Not rank-aware (order doesn't matter)

        Returns:
            {"Recall@1": 0.2, "Recall@10": 0.5, "Recall@100": 0.8, ...}
        """
        recall_scores = {}

        for k in self.k_values:
            scores = []

            for query_id in qrels:
                if query_id not in results:
                    scores.append(0.0)
                    continue

                # Get top-k results
                sorted_results = sorted(
                    results[query_id].items(), key=lambda x: x[1], reverse=True
                )[:k]

                retrieved_ids = {doc_id for doc_id, _ in sorted_results}

                # Count relevant documents in qrels
                relevant_ids = {doc_id for doc_id, rel in qrels[query_id].items() if rel > 0}

                if len(relevant_ids) == 0:
                    scores.append(0.0)
                    continue

                # Compute recall
                relevant_found = len(retrieved_ids & relevant_ids)
                recall = relevant_found / len(relevant_ids)
                scores.append(recall)

            recall_scores[f"Recall@{k}"] = float(np.mean(scores)) if scores else 0.0

        return recall_scores

    def compute_precision_all(
        self, qrels: dict[str, dict[str, int]], results: dict[str, dict[str, float]]
    ) -> dict[str, float]:
        """
        Compute Precision@k for all k values

        Precision@k:
        - Fraction of retrieved documents that are relevant
        - Binary relevance (relevant if score > 0)
        - Not rank-aware (order doesn't matter)

        Returns:
            {"P@1": 0.8, "P@10": 0.7, "P@100": 0.5, ...}
        """
        precision_scores = {}

        for k in self.k_values:
            scores = []

            for query_id in qrels:
                if query_id not in results:
                    scores.append(0.0)
                    continue

                # Get top-k results
                sorted_results = sorted(
                    results[query_id].items(), key=lambda x: x[1], reverse=True
                )[:k]

                if len(sorted_results) == 0:
                    scores.append(0.0)
                    continue

                # Count relevant in top-k
                num_relevant = sum(
                    1 for doc_id, _ in sorted_results if qrels[query_id].get(doc_id, 0) > 0
                )

                precision = num_relevant / len(sorted_results)
                scores.append(precision)

            precision_scores[f"P@{k}"] = float(np.mean(scores)) if scores else 0.0

        return precision_scores

    def compute_mrr_all(
        self, qrels: dict[str, dict[str, int]], results: dict[str, dict[str, float]]
    ) -> dict[str, float]:
        """
        Compute MRR@k (Mean Reciprocal Rank) for all k values

        MRR:
        - Measures position of FIRST relevant document
        - Binary relevance (relevant if score > 0)
        - Good for question answering (user only needs one answer)

        Returns:
            {"MRR@1": 0.5, "MRR@10": 0.65, "MRR@100": 0.7, ...}
        """
        mrr_scores = {}

        for k in self.k_values:
            scores = []

            for query_id in qrels:
                if query_id not in results:
                    scores.append(0.0)
                    continue

                # Get top-k results sorted by score
                sorted_results = sorted(
                    results[query_id].items(), key=lambda x: x[1], reverse=True
                )[:k]

                # Find rank of first relevant document
                for rank, (doc_id, _) in enumerate(sorted_results, 1):
                    if qrels[query_id].get(doc_id, 0) > 0:  # Relevant
                        scores.append(1.0 / rank)
                        break
                else:
                    # No relevant document found in top-k
                    scores.append(0.0)

            mrr_scores[f"MRR@{k}"] = float(np.mean(scores)) if scores else 0.0

        return mrr_scores

    def format_for_display(self, metrics: dict[str, dict[str, float]]) -> str:
        """
        Format metrics for console display

        Returns formatted string with all metrics
        """
        lines = []
        lines.append("\n" + "=" * 60)
        lines.append("MTEB Retrieval Evaluation Results")
        lines.append("=" * 60)

        # Primary metric (MTEB standard)
        lines.append("\n📊 Primary Metric (MTEB Standard):")
        lines.append(f"   nDCG@10: {metrics['ndcg']['NDCG@10']:.4f}")

        # All metrics
        for metric_type in ["ndcg", "map", "mrr", "recall", "precision"]:
            lines.append(f"\n{metric_type.upper()}:")
            for name, value in sorted(metrics[metric_type].items()):
                lines.append(f"   {name}: {value:.4f}")

        lines.append("=" * 60 + "\n")

        return "\n".join(lines)


# Legacy evaluator functions (for compatibility with existing system)


def _to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _extract_metric_from_run(run: Any, *keys: str) -> float | None:
    metric_sources: list[dict[str, Any]] = []

    if hasattr(run, "outputs") and isinstance(run.outputs, dict):
        metric_sources.append(run.outputs)
    if isinstance(run, dict):
        metric_sources.append(run)
        nested_outputs = run.get("outputs")
        if isinstance(nested_outputs, dict):
            metric_sources.append(nested_outputs)

    expanded_sources: list[dict[str, Any]] = []
    for source in metric_sources:
        expanded_sources.append(source)
        for source_key in ("metrics", "scores", "evaluation_results"):
            nested = source.get(source_key)
            if isinstance(nested, dict):
                expanded_sources.append(nested)

    for source in expanded_sources:
        for key in keys:
            value = source.get(key)
            metric = _to_float(value)
            if metric is not None:
                return metric
    return None


def ndcg_at_10_evaluator(run, example):
    """
    Legacy evaluator wrapper for nDCG@10
    Compatible with existing LangSmith evaluation system
    """
    del example
    score = _extract_metric_from_run(run, "ndcg_10", "NDCG@10")
    return {
        "key": "ndcg_10",
        "score": score if score is not None else 0.0,
        "comment": "nDCG@10 (MTEB primary metric)",
    }


def map_at_100_evaluator(run, example):
    """Legacy evaluator wrapper for MAP@100"""
    del example
    score = _extract_metric_from_run(run, "map_100", "MAP@100")
    return {"key": "map_100", "score": score if score is not None else 0.0, "comment": "MAP@100"}


def recall_at_100_evaluator(run, example):
    """Legacy evaluator wrapper for Recall@100"""
    del example
    score = _extract_metric_from_run(run, "recall_100", "Recall@100")
    return {
        "key": "recall_100",
        "score": score if score is not None else 0.0,
        "comment": "Recall@100",
    }


def mrr_at_10_evaluator(run, example):
    """Legacy evaluator wrapper for MRR@10"""
    del example
    score = _extract_metric_from_run(run, "mrr_10", "MRR@10")
    return {"key": "mrr_10", "score": score if score is not None else 0.0, "comment": "MRR@10"}


# Export evaluators for use in evaluation system
MTEB_EVALUATORS = {
    "ndcg_10": ndcg_at_10_evaluator,
    "map_100": map_at_100_evaluator,
    "recall_100": recall_at_100_evaluator,
    "mrr_10": mrr_at_10_evaluator,
}
