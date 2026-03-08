"""Tests for config-driven evaluator selection."""

from __future__ import annotations

from metivta_eval.config.toml_config import config
from metivta_eval.evaluators import get_configured_daat_evaluators


def test_get_configured_daat_evaluators_honors_config(monkeypatch) -> None:
    """Configured DAAT evaluator profiles should be selectable from config."""
    monkeypatch.setattr(config.evaluation.daat, "evaluators", ["response_length"])

    evaluators = get_configured_daat_evaluators()

    assert [fn.__name__ for fn in evaluators] == ["response_length_evaluator"]
