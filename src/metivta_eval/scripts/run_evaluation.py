"""Run a DAAT evaluation locally against one configured system and evaluator set."""

import sys

from dotenv import load_dotenv
from langsmith.evaluation import evaluate
from langsmith.utils import LangSmithError

from metivta_eval.evaluators import get_evaluators
from metivta_eval.langsmith_utils import resolve_daat_evaluation_data
from metivta_eval.observability.logger import get_logger
from metivta_eval.systems import get_system_function

logger = get_logger(__name__)


def main() -> None:
    """Parse CLI arguments and execute one local evaluation run."""
    load_dotenv()

    if len(sys.argv) < 3:
        print(
            "Usage: python -m metivta_eval.scripts.run_evaluation <system_name> <evaluator_names>"
        )
        sys.exit(1)

    system_name, evaluator_names = sys.argv[1], sys.argv[2].split(",")
    logger.info(
        "Starting evaluation with system=%s evaluators=%s",
        system_name,
        evaluator_names,
    )

    system_function = get_system_function(system_name)
    evaluator_funcs = get_evaluators(evaluator_names)
    try:
        dataset_name, dataset_examples = resolve_daat_evaluation_data()
    except RuntimeError as exc:
        print(f"❌ Error loading local dataset: {exc}")
        sys.exit(1)

    print("🚀 Starting MetivitaEval evaluation...")
    print(f"🎯 System: {system_name}")
    print(f"📊 Dataset: {dataset_name}")
    print(f"📦 Examples: {len(dataset_examples)}")
    print(f"⚖️ Evaluators: {', '.join(e.__name__ for e in evaluator_funcs)}")

    try:
        evaluate(
            system_function,
            data=dataset_examples,
            evaluators=evaluator_funcs,
            experiment_prefix=f"MetivitaEval - {system_name}",
            metadata={
                "system": system_name,
                "evaluators": evaluator_names,
                "dataset_name": dataset_name,
                "dataset_source": "local_json",
            },
            upload_results=False,
        )
        logger.info("Evaluation completed successfully for %s", system_name)
        print("\n✅ Evaluation complete.")
    except (LangSmithError, OSError, TypeError, ValueError, KeyError) as exc:
        logger.error("Evaluation failed: %s", exc)
        print(f"\n❌ Evaluation failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
