"""Compatibility config loader backed by `config.toml`.

Legacy modules in this repository still import `config_loader`. This adapter
keeps those call sites stable while making TOML the single source of truth.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

from .toml_config import load_config as load_toml_config


def _legacy_payload() -> dict[str, Any]:
    cfg = load_toml_config()
    payload = cfg.model_dump()

    payload.setdefault("project", {})
    payload["project"]["name"] = "Metivta Eval - The Open Torah"

    payload.setdefault("models", {})
    payload["models"].setdefault("claude", payload["models"].get("primary"))

    payload.setdefault("api", {})
    payload["api"].setdefault("host", cfg.server.host)
    payload["api"].setdefault("port", cfg.server.port)
    payload["api"].setdefault("secret_key", cfg.security.secret_key.get_secret_value())
    payload["api"].setdefault("data_file", "api/leaderboard_data.json")

    payload.setdefault("dataset", {})
    questions_file = payload["dataset"].get("files", {}).get("questions", "Q1-dataset.json")
    payload["dataset"]["local_file"] = str(Path(cfg.dataset.local_path) / questions_file)
    payload["dataset"].setdefault("holdback_name", cfg.dataset.name)

    payload.setdefault("evaluators", {})
    payload["evaluators"].setdefault("enable_llm_feedback", True)
    payload["evaluators"].setdefault(
        "feedback_evaluators",
        [
            "hebrew_presence",
            "url_format",
            "response_length",
            "scholarly_format",
            "correctness",
            "web_validation",
            "daat_score",
        ],
    )
    payload["evaluators"].setdefault(
        "daat_config",
        {
            "enabled_evaluators": list(cfg.evaluation.daat.evaluators),
            "composite_weights": {
                "dai": float(cfg.evaluation.daat.weights.dai),
                "mla": float(cfg.evaluation.daat.weights.mla),
            },
        },
    )

    return payload


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Load legacy configuration dictionary from canonical TOML config."""
    return _legacy_payload()


def get_model(model_type: str = "primary") -> str:
    """Get configured model name from compatibility payload."""
    return str(load_config()["models"][model_type])


def get_config_section(section_name: str) -> dict[str, Any]:
    """Get one top-level section from compatibility payload."""
    section = load_config().get(section_name, {})
    if isinstance(section, dict):
        return section
    return {}
