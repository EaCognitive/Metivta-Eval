"""Evaluator registry and configuration helpers for DAAT and MTEB scoring."""

from metivta_eval.config.toml_config import config

from .code_evaluators import METIVTA_CODE_EVALUATORS
from .controlled_evaluators import METIVTA_CONTROLLED_EVALUATORS
from .daat_evaluator import DAAT_EVALUATORS
from .standards_evaluators import METIVTA_STANDARDS_EVALUATORS

# Always use remote browser service (Browserless.io) for consistency
# This works both locally and on deployment platforms
from .web_validator_remote import METIVTA_WEB_VALIDATORS

ALL_EVALUATORS = {
    **METIVTA_CODE_EVALUATORS,
    **METIVTA_STANDARDS_EVALUATORS,
    **METIVTA_CONTROLLED_EVALUATORS,
    **METIVTA_WEB_VALIDATORS,
    **DAAT_EVALUATORS,
}


def get_evaluators(names: list[str]):
    """Returns a list of evaluator functions based on their names."""
    if "all" in names:
        return list(ALL_EVALUATORS.values())

    evaluators = []
    for name in names:
        if name not in ALL_EVALUATORS:
            raise ValueError(f"Unknown evaluator: {name}. Available: {list(ALL_EVALUATORS.keys())}")
        evaluators.append(ALL_EVALUATORS[name])
    return evaluators


def get_configured_daat_evaluators():
    """Return the configured evaluator profile for DAAT submissions."""
    names = list(config.evaluation.daat.evaluators)
    if not names:
        names = ["all"]
    return get_evaluators(names)
