"""Ground-truth target used for deterministic local harness validation."""


def ground_truth_target(_inputs: dict, **kwargs) -> dict:
    """Returns the exact expected answer from the dataset example.

    DEPRECATED: Use unified_target with evaluation.target='ground_truth' instead.
    This is kept for backwards compatibility only.
    """
    example = kwargs.get("example")
    if not example or not example.outputs:
        return {"answer": "Error: Ground truth example not found."}
    return {"answer": example.outputs.get("answer", "")}
