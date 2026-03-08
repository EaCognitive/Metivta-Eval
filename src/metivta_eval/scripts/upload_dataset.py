"""Upload the configured dataset to LangSmith."""

from __future__ import annotations

import argparse
from typing import Any

from dotenv import load_dotenv
from langsmith import Client
from langsmith.utils import LangSmithNotFoundError

from metivta_eval.config.config_loader import get_config_section
from metivta_eval.dataset_loader import load_dataset_examples, resolve_dataset_file_path
from metivta_eval.observability.logger import get_logger

logger = get_logger(__name__)


def load_dataset(file_path: str | None = None) -> list[dict[str, Any]]:
    """Load dataset from JSON file."""
    dataset_path = resolve_dataset_file_path(file_path)
    logger.info("Loading dataset from: %s", dataset_path)
    return load_dataset_examples(str(dataset_path))


def ensure_dataset_exists(dataset_name: str, client: Client) -> str:
    """Ensure dataset exists in LangSmith, create or update as needed."""
    try:
        # Check if dataset exists
        existing = client.read_dataset(dataset_name=dataset_name)
        logger.info("Found existing dataset: %s (ID: %s)", dataset_name, existing.id)

        # Delete existing examples to refresh
        logger.info("Clearing existing examples...")
        examples = list(client.list_examples(dataset_id=existing.id))
        for example in examples:
            client.delete_example(example.id)

        return str(existing.id)

    except LangSmithNotFoundError:
        # Create new dataset
        logger.info("Creating new dataset: %s", dataset_name)
        dataset = client.create_dataset(
            dataset_name=dataset_name,
            description=(
                "Metivta Eval - The Open Torah evaluation dataset with Torah scholarship Q&A pairs"
            ),
        )
        return str(dataset.id)


def upload_to_langsmith(
    file_path: str | None = None,
    dataset_name: str | None = None,
    use_holdback: bool = False,
) -> str:
    """Upload dataset to LangSmith."""
    load_dotenv()

    client = Client()

    # Get dataset name from config if not provided
    if dataset_name is None:
        dataset_config = get_config_section("dataset")
        dataset_name = dataset_config["holdback_name" if use_holdback else "name"]

    logger.info("Uploading to LangSmith dataset: %s", dataset_name)

    # Load the dataset
    examples = load_dataset(file_path)
    logger.info("Loaded %d examples", len(examples))

    # Ensure dataset exists
    dataset_id = ensure_dataset_exists(dataset_name, client)

    # Prepare data for bulk upload
    inputs_list = []
    outputs_list = []
    metadata_list = []

    for i, example in enumerate(examples):
        # Handle inputs
        if "inputs" in example:
            inputs = example["inputs"]
        elif "question" in example:
            inputs = {"question": example["question"]}
        else:
            logger.warning("Example %d has no valid input format, skipping", i)
            continue

        # Handle outputs
        if "outputs" in example:
            outputs = example["outputs"]
        elif "answer" in example:
            outputs = {"answer": example["answer"]}
        elif "ground_truth" in example:
            outputs = {"answer": example["ground_truth"]}
        else:
            outputs = {"answer": ""}  # Empty answer if none provided

        inputs_list.append(inputs)
        outputs_list.append(outputs)

        # Add metadata if available
        metadata = example.get("metadata", {})
        if "id" in example:
            metadata["original_id"] = example["id"]
        metadata_list.append(metadata)

    # Upload examples in bulk
    if inputs_list:
        logger.info("Uploading %d examples...", len(inputs_list))
        client.create_examples(
            inputs=inputs_list, outputs=outputs_list, metadata=metadata_list, dataset_id=dataset_id
        )
        logger.info("Successfully uploaded %d examples to %s", len(inputs_list), dataset_name)
    else:
        logger.warning("No valid examples to upload")

    return dataset_id


def main() -> None:
    """Main function for uploading dataset."""
    parser = argparse.ArgumentParser(description="Upload dataset to LangSmith")
    parser.add_argument("--file", help="Path to dataset JSON file (default: from config)")
    parser.add_argument("--dataset-name", help="LangSmith dataset name (default: from config)")
    parser.add_argument("--holdback", action="store_true", help="Upload as holdback dataset")

    args = parser.parse_args()

    print("📤 Uploading dataset to LangSmith...")

    try:
        dataset_id = upload_to_langsmith(
            file_path=args.file, dataset_name=args.dataset_name, use_holdback=args.holdback
        )
        print(f"✅ Upload complete! Dataset ID: {dataset_id}")

    except (
        LangSmithNotFoundError,
        OSError,
        TypeError,
        ValueError,
    ) as exc:
        print(f"❌ Upload failed: {exc}")
        raise


if __name__ == "__main__":
    main()
