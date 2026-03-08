"""
System targets for evaluation.

The unified_target is the recommended approach - it uses config.toml to determine
which target to use (endpoint, ground_truth, anthropic, or mock).

Legacy targets (anthropic_sonnet, ground_truth) are kept for backwards compatibility.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .anthropic import anthropic_sonnet_target
from .ground_truth import ground_truth_target
from .unified_target import unified_target

SystemFunction = Callable[..., dict[str, Any]]

SYSTEM_FUNCTIONS: dict[str, SystemFunction] = {
    # Recommended: Unified target that reads from config
    "unified": unified_target,
    # Legacy targets (deprecated - use unified instead)
    "ground_truth": ground_truth_target,
    "anthropic_sonnet": anthropic_sonnet_target,
}


def get_system_function(name: str) -> SystemFunction:
    """Returns a system function by name."""
    if name not in SYSTEM_FUNCTIONS:
        raise ValueError(f"Unknown system: {name}. Available: {list(SYSTEM_FUNCTIONS.keys())}")
    return SYSTEM_FUNCTIONS[name]
