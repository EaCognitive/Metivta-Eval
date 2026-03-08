"""Regression tests for the question-display CLI."""

from __future__ import annotations

import builtins
import json
from pathlib import Path

from metivta_eval.scripts import show_questions


def _write_questions(path: Path) -> None:
    """Write a minimal questions-only dataset for CLI tests."""
    payload = [
        {
            "inputs": {"question": "Where is the source?"},
            "outputs": {"answer": "Ground truth"},
        }
    ]
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_show_questions_skips_prompt_in_non_interactive_shell(
    monkeypatch,
    tmp_path: Path,
    capsys,
) -> None:
    """`show-questions` should not crash when stdin is not interactive."""
    dataset_path = tmp_path / "questions.json"
    _write_questions(dataset_path)

    monkeypatch.setattr(show_questions, "resolve_questions_only_file_path", lambda: dataset_path)
    monkeypatch.setattr(show_questions.sys, "argv", ["show_questions.py"])
    monkeypatch.setattr(show_questions.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(
        builtins,
        "input",
        lambda _: (_ for _ in ()).throw(AssertionError("input() should not be called")),
    )

    show_questions.main()

    output = capsys.readouterr().out
    assert "Non-interactive shell detected" in output
    assert "Total questions available: 1" in output


def test_show_questions_exports_template_when_flag_is_provided(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """`show-questions --export` should write a valid template without prompting."""
    dataset_path = tmp_path / "questions.json"
    output_path = tmp_path / "answers.json"
    _write_questions(dataset_path)

    monkeypatch.setattr(show_questions, "resolve_questions_only_file_path", lambda: dataset_path)
    monkeypatch.setattr(
        show_questions.sys,
        "argv",
        ["show_questions.py", "--export", str(output_path)],
    )

    show_questions.main()

    exported = json.loads(output_path.read_text(encoding="utf-8"))
    assert exported == [
        {
            "inputs": {"question": "Where is the source?"},
            "outputs": {"answer": "<<<YOUR ANSWER HERE>>>"},
        }
    ]
