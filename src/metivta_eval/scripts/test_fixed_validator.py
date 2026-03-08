#!/usr/bin/env python3
"""Test the fixed web validator with Hebrew content and Sefaria URLs."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from dotenv import load_dotenv
from langsmith.schemas import Example, Run

from metivta_eval.evaluators.web_validator_remote import web_validation_evaluator

# Load environment variables
load_dotenv()


def _answer_text(run: Run) -> str:
    """Return the answer string from a LangSmith run."""
    outputs = run.outputs if isinstance(run.outputs, dict) else {}
    return str(outputs.get("answer", ""))


def test_hebrew_url_validation():
    """Test validation with a real Hebrew Torah answer."""

    # Simulate a run with a Torah answer containing Hebrew text and Sefaria URL
    test_run = Run(
        id=str(uuid.uuid4()),
        trace_id=str(uuid.uuid4()),
        name="test-run",
        start_time=datetime.now(UTC),
        run_type="chain",
        inputs={"question": "What does Hillel say about the Torah?"},
        outputs={
            "answer": """The Talmud in Shabbat 31a discusses Hillel's famous response
            to the convert
            who wanted to learn the entire Torah while standing on one foot. Hillel told him: 
            "דעלך סני לחברך לא תעביד" - "That which is hateful to you, do not do to your fellow." 
            This is the entire Torah, and the rest is commentary. Go and learn it.
            Source: https://www.sefaria.org/Shabbat.31a?lang=bi"""
        },
    )

    test_example = Example(
        id=str(uuid.uuid4()),
        inputs={"question": "What does Hillel say about the Torah?"},
        outputs={"answer": "Ground truth answer"},
    )

    print("🧪 Testing Fixed Web Validator\n")
    print("📝 Test Answer:")
    print(_answer_text(test_run))
    print("\n" + "=" * 50 + "\n")

    # Run the validator
    result = web_validation_evaluator(test_run, test_example)

    print("✅ Validation Result:")
    print(f"  Score: {result['score']}")
    print(f"  Comment: {result['comment']}")

    # Test with multiple URLs
    test_run_2 = Run(
        id=str(uuid.uuid4()),
        trace_id=str(uuid.uuid4()),
        name="test-run-2",
        start_time=datetime.now(UTC),
        run_type="chain",
        inputs={"question": "Multiple sources question"},
        outputs={
            "answer": """According to the Mishnah in Pirkei Avot,
            הִלֵּל אוֹמֵר, הֱוֵי מִתַּלְמִידָיו שֶׁל אַהֲרֹן
            Sources: 
            https://www.sefaria.org/Pirkei_Avot.1.12
            https://www.sefaria.org/Shabbat.31a
            https://www.chabad.org/library/article_cdo/aid/2165/jewish/Chapter-One.htm"""
        },
    )

    print("\n" + "=" * 50 + "\n")
    print("📝 Test with Multiple URLs:")
    print(_answer_text(test_run_2))
    print("\n")

    result_2 = web_validation_evaluator(test_run_2, test_example)

    print("✅ Validation Result:")
    print(f"  Score: {result_2['score']}")
    print(f"  Comment: {result_2['comment']}")

    # Test with no URLs
    test_run_3 = Run(
        id=str(uuid.uuid4()),
        trace_id=str(uuid.uuid4()),
        name="test-run-3",
        start_time=datetime.now(UTC),
        run_type="chain",
        inputs={"question": "No URL question"},
        outputs={"answer": "This answer has no URLs but contains Hebrew: שַׁבָּת שָׁלוֹם"},
    )

    print("\n" + "=" * 50 + "\n")
    print("📝 Test with No URLs:")
    print(_answer_text(test_run_3))
    print("\n")

    result_3 = web_validation_evaluator(test_run_3, test_example)

    print("✅ Validation Result:")
    print(f"  Score: {result_3['score']}")
    print(f"  Comment: {result_3['comment']}")

    print("\n" + "=" * 50 + "\n")
    print("🎉 All tests completed!")


if __name__ == "__main__":
    test_hebrew_url_validation()
