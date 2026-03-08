"""Dataset loading helpers for DAAT and related evaluation flows."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from metivta_eval.config.config_loader import get_config_section


def resolve_dataset_asset_path(file_name: str) -> Path:
    """Resolve a dataset asset relative to the configured dataset root."""
    candidate = Path(file_name).expanduser()
    if candidate.is_absolute():
        return candidate

    dataset_config = get_config_section("dataset")
    local_path = str(dataset_config.get("local_path", "src/metivta_eval/dataset")).strip()
    dataset_root = Path(local_path)
    if not dataset_root.is_absolute():
        dataset_root = project_root() / dataset_root
    return dataset_root / candidate


def resolve_dataset_file_path(file_path: str | None = None) -> Path:
    """Resolve the dataset file path from config or an explicit override."""
    candidate = file_path or _configured_dataset_file()
    path = Path(candidate).expanduser()
    if path.is_absolute():
        return path
    return project_root() / path


def load_dataset_examples(file_path: str | None = None) -> list[dict[str, Any]]:
    """Load and normalize dataset examples from a JSON file."""
    dataset_path = resolve_dataset_file_path(file_path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset file not found at {dataset_path}")

    with dataset_path.open(encoding="utf-8") as file_obj:
        raw_data = json.load(file_obj)

    examples = _normalize_examples(raw_data)
    examples = _limit_examples(examples)
    if not examples:
        raise ValueError(f"Dataset file {dataset_path} does not contain any usable examples")
    return examples


def load_questions_only_examples() -> list[dict[str, Any]]:
    """Load a questions-only dataset view, deriving it from full examples if needed."""
    questions_only_path = resolve_questions_only_file_path()
    if questions_only_path.exists():
        return load_dataset_examples(str(questions_only_path))

    examples = load_dataset_examples()
    return [
        {
            "inputs": {"question": str(item.get("inputs", {}).get("question", ""))},
            "outputs": {"answer": ""},
        }
        for item in examples
    ]


def project_root() -> Path:
    """Return the repository root for the current package."""
    return Path(__file__).resolve().parents[2]


def _configured_dataset_file() -> str:
    """Return the configured DAAT dataset file path."""
    dataset_config = get_config_section("dataset")
    configured_file = str(dataset_config.get("local_file", "")).strip()
    if configured_file:
        return configured_file
    questions_file = _dataset_file_name("questions", "Q1-dataset.json")
    return str(resolve_dataset_asset_path(questions_file))


def resolve_questions_only_file_path() -> Path:
    """Resolve the questions-only dataset file path."""
    questions_file = _dataset_file_name("questions_only", "Q1-questions-only.json")
    return resolve_dataset_asset_path(questions_file)


def _dataset_file_name(key: str, default_name: str) -> str:
    """Return a configured dataset file name from the legacy payload."""
    dataset_config = get_config_section("dataset")
    files_config = dataset_config.get("files", {})
    if isinstance(files_config, dict):
        configured_name = str(files_config.get(key, "")).strip()
        if configured_name:
            return configured_name
    return default_name


def _normalize_examples(raw_data: Any) -> list[dict[str, Any]]:
    """Convert supported JSON payloads into LangSmith example dictionaries."""
    if isinstance(raw_data, dict) and "examples" in raw_data:
        raw_items = raw_data["examples"]
    elif isinstance(raw_data, list):
        raw_items = raw_data
    else:
        raw_items = [raw_data]

    examples: list[dict[str, Any]] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue

        if "inputs" in item and "outputs" in item:
            examples.append(item)
            continue

        question = item.get("question")
        if question is None:
            continue

        answer = item.get("answer", item.get("ground_truth", ""))
        metadata = item.get("metadata")

        example = {
            "inputs": {"question": question},
            "outputs": {"answer": answer},
        }
        if isinstance(metadata, dict):
            example["metadata"] = metadata
        examples.append(example)

    return examples


def _limit_examples(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Optionally limit the dataset size for local demo/testing flows."""
    max_examples = os.getenv("METIVTA_DATASET_MAX_EXAMPLES", "").strip()
    if not max_examples:
        return examples

    try:
        limit = int(max_examples)
    except ValueError:
        return examples

    if limit <= 0:
        return examples
    return examples[:limit]
