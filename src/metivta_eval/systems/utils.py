"""Utility functions for system implementations."""

from metivta_eval.config.config_loader import load_config
from metivta_eval.observability.logger import get_logger

logger = get_logger(__name__)


def check_dev_mode(inputs: dict, kwargs: dict) -> dict | None:
    """
    Check if dev_mode is enabled and return ground truth if available.

    Args:
        inputs: The input dictionary with the question
        kwargs: Additional keyword arguments that may contain the example

    Returns:
        Dict with the answer if in dev_mode and ground truth is available,
        None otherwise (indicating the system should proceed normally)
    """
    config = load_config()
    if not config.get("dev_mode", False):
        return None

    # In dev mode, try to return the ground truth
    example = kwargs.get("example")
    if example and hasattr(example, "outputs") and example.outputs:
        answer = example.outputs.get("answer", "")
        question = inputs.get("question", "")[:50]  # First 50 chars for logging
        logger.info(f"DEV MODE: Returning ground truth for question: {question}...")
        return {"answer": answer}

    # No ground truth available
    logger.warning("DEV MODE: No ground truth available, proceeding normally")
    return None
