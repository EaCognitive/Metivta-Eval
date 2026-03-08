#!/usr/bin/env python3
"""Reference retrieval API compatible with MetivtaEval MTEB endpoint."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import faiss
from flask import Flask, jsonify, request
from sentence_transformers import SentenceTransformer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

model: SentenceTransformer | None = None
index: faiss.IndexFlatIP | None = None
corpus_ids: list[str] = []


def load_corpus(corpus_file: str) -> dict[str, dict[str, str]]:
    """Load corpus from JSONL file."""
    corpus: dict[str, dict[str, str]] = {}
    with open(corpus_file, encoding="utf-8") as file_obj:
        for line in file_obj:
            doc = json.loads(line)
            corpus[str(doc["_id"])] = {
                "title": str(doc.get("title", "")),
                "text": str(doc["text"]),
            }
    logger.info("Loaded %d passages from corpus", len(corpus))
    return corpus


def build_index(
    corpus: dict[str, dict[str, str]],
    encoder: SentenceTransformer,
) -> tuple[faiss.IndexFlatIP, list[str]]:
    """Build FAISS cosine-similarity index for the corpus."""
    ids = list(corpus.keys())
    corpus_texts = [
        f"{corpus[item_id]['title']} {corpus[item_id]['text']}".strip() for item_id in ids
    ]

    logger.info("Encoding %d passages", len(corpus_texts))
    embeddings = encoder.encode(
        corpus_texts,
        batch_size=128,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    )

    embedding_size = embeddings.shape[1]
    faiss_index = faiss.IndexFlatIP(embedding_size)
    faiss_index.add(embeddings.astype("float32"))
    logger.info("Built FAISS index with %d vectors", faiss_index.ntotal)
    return faiss_index, ids


def initialize_system() -> bool:
    """Initialize model, corpus, and FAISS index."""
    global model, index, corpus_ids

    logger.info("Initializing retrieval system")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    corpus_file = Path("src/metivta_eval/dataset/mteb/corpus_template.jsonl")
    if not corpus_file.exists():
        logger.error("Corpus file not found: %s", corpus_file)
        return False

    corpus = load_corpus(str(corpus_file))
    index, corpus_ids = build_index(corpus, model)
    logger.info("Retrieval system initialized")
    return True


@app.route("/health", methods=["GET"])
def health() -> tuple[dict[str, object], int]:
    """Health endpoint."""
    return (
        {
            "status": "healthy",
            "model": "all-MiniLM-L6-v2",
            "corpus_size": len(corpus_ids),
        },
        200,
    )


@app.route("/retrieve", methods=["POST"])
def retrieve() -> tuple[object, int] | object:
    """Retrieve ranked passages for one query."""
    if model is None or index is None:
        return jsonify(
            {"error": {"code": "not_ready", "message": "system is not initialized"}}
        ), 503

    data = request.get_json()
    if not data:
        return (
            jsonify(
                {
                    "error": {
                        "code": "invalid_request",
                        "message": "Request body must be JSON",
                    }
                }
            ),
            400,
        )

    query = data.get("query")
    top_k = data.get("top_k", 100)

    if not query:
        return (
            jsonify(
                {
                    "error": {
                        "code": "invalid_query",
                        "message": "Query text is required",
                    }
                }
            ),
            400,
        )

    if not isinstance(top_k, int) or top_k <= 0:
        return (
            jsonify(
                {
                    "error": {
                        "code": "invalid_top_k",
                        "message": "top_k must be a positive integer",
                    }
                }
            ),
            400,
        )

    try:
        query_embedding = model.encode(
            [str(query)],
            convert_to_numpy=True,
            normalize_embeddings=True,
        )

        query_k = min(top_k, len(corpus_ids))
        scores, indices = index.search(query_embedding.astype("float32"), query_k)
        results = [
            {"id": corpus_ids[idx], "score": float(score)}
            for score, idx in zip(scores[0], indices[0])
            if idx < len(corpus_ids)
        ]

        logger.info("Query '%s...' -> %d results", str(query)[:50], len(results))
        return jsonify({"results": results, "model": "all-MiniLM-L6-v2"})
    except Exception as exc:
        logger.error("Error processing retrieval request: %s", exc, exc_info=True)
        return jsonify({"error": {"code": "internal_error", "message": str(exc)}}), 500


if __name__ == "__main__":
    if not initialize_system():
        raise SystemExit(1)

    logger.info("Starting Flask server on http://localhost:5001")
    app.run(host="0.0.0.0", port=5001, debug=False)
