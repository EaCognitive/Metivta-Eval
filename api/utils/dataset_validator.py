"""Dataset validator to ensure only questions from the configured dataset are evaluated."""

from __future__ import annotations

from metivta_eval.dataset_loader import load_dataset_examples, resolve_dataset_file_path


class DatasetValidator:
    """Validate submissions against the configured DAAT dataset."""

    def __init__(self):
        """Load the configured dataset questions on initialization."""
        self.dataset_path = resolve_dataset_file_path()
        self.dataset = load_dataset_examples(str(self.dataset_path))

        self.valid_questions = {qa["inputs"]["question"] for qa in self.dataset}
        self.question_answer_map = {
            qa["inputs"]["question"]: qa["outputs"]["answer"] for qa in self.dataset
        }

    def is_valid_question(self, question: str) -> bool:
        """Check if a question is in the configured dataset."""
        return question in self.valid_questions

    def get_answer(self, question: str) -> str | None:
        """Get the ground-truth answer for a question."""
        return self.question_answer_map.get(question)

    def validate_submission(self, endpoint_url: str) -> dict:
        """Validate that an endpoint only answers configured dataset questions."""
        import requests

        errors: list[str] = []
        valid_count = 0
        sample_questions = list(self.valid_questions)[:3]

        for question in sample_questions:
            try:
                response = requests.post(
                    endpoint_url,
                    json={"question": question},
                    headers={"Content-Type": "application/json"},
                    timeout=30,
                )

                if response.status_code == 200:
                    valid_count += 1
                else:
                    errors.append(f"Failed on question: {question[:50]}...")

            except Exception as e:
                errors.append(f"Error testing endpoint: {str(e)}")
                break

        invalid_question = "What is 2 + 2?"
        try:
            response = requests.post(
                endpoint_url,
                json={"question": invalid_question},
                headers={"Content-Type": "application/json"},
                timeout=30,
            )

            # Endpoint should reject or indicate invalid question
            if response.status_code == 200:
                answer = response.json().get("answer", "")
                if answer and "not in dataset" not in answer.lower():
                    errors.append("Endpoint accepts questions not in dataset")

        except Exception:
            pass  # This is fine, endpoint might reject invalid questions

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "valid_responses": valid_count,
            "dataset_size": len(self.valid_questions),
        }

    def get_dataset_info(self) -> dict:
        """Get information about the configured dataset."""
        return {
            "total_questions": len(self.valid_questions),
            "dataset_path": str(self.dataset_path),
            "sample_questions": list(self.valid_questions)[:3],
        }


_validator = None


def get_validator() -> DatasetValidator:
    """Get the singleton validator instance."""
    global _validator
    if _validator is None:
        _validator = DatasetValidator()
    return _validator
