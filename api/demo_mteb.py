"""Minimal deterministic retrieval API for hosted MTEB end-to-end checks."""

from __future__ import annotations

from flask import Flask

app = Flask(__name__)


@app.get("/health")
def health() -> tuple[dict[str, str], int]:
    """Return liveness for hosted test harness checks."""
    return {"status": "healthy"}, 200


@app.post("/search")
def search() -> tuple[dict[str, list[dict[str, float | str]]], int]:
    """Return deterministic retrieval candidates for any query payload."""
    return {
        "results": [
            {"id": "doc-1", "score": 1.0},
            {"id": "doc-2", "score": 0.5},
            {"id": "doc-3", "score": 0.25},
        ]
    }, 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5002, debug=False)
