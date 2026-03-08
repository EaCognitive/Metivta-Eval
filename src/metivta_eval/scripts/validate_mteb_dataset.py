#!/usr/bin/env python3
"""Validate corpus, queries, and qrels files for a local MTEB-style dataset."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
END = "\033[0m"
MAX_ERROR_PREVIEW = 10
VALID_QREL_SCORES = {0, 1, 2, 3}


@dataclass(frozen=True, slots=True)
class JsonlValidationResult:
    """Validation result for one JSONL collection."""

    valid: bool
    item_ids: set[str]
    errors: list[str] = field(default_factory=list)
    duplicate_ids: list[str] = field(default_factory=list)


@dataclass(slots=True)
class QrelsStats:
    """Mutable qrels statistics gathered while validating the file."""

    total_annotations: int = 0
    invalid_scores: list[int] = field(default_factory=list)
    annotations_per_query: Counter[str] = field(default_factory=Counter)
    score_distribution: Counter[int] = field(default_factory=Counter)


@dataclass(slots=True)
class QrelsMissingRefs:
    """Missing qrels references grouped by type."""

    query_ids: set[str] = field(default_factory=set)
    corpus_ids: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class QrelsValidationResult:
    """Validation result and stats for a qrels TSV file."""

    valid: bool
    errors: list[str] = field(default_factory=list)
    stats: QrelsStats = field(default_factory=QrelsStats)
    missing_refs: QrelsMissingRefs = field(default_factory=QrelsMissingRefs)


@dataclass(slots=True)
class JsonlValidationState:
    """Mutable JSONL validation state."""

    item_ids: set[str] = field(default_factory=set)
    duplicate_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class QrelsReferenceSet:
    """Valid IDs that qrels rows are allowed to reference."""

    query_ids: set[str]
    corpus_ids: set[str]


@dataclass(slots=True)
class QrelsValidationState:
    """Mutable qrels validation state shared across helpers."""

    errors: list[str] = field(default_factory=list)
    stats: QrelsStats = field(default_factory=QrelsStats)
    missing_refs: QrelsMissingRefs = field(default_factory=QrelsMissingRefs)


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"{GREEN}✅ {message}{END}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"{RED}❌ {message}{END}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    print(f"{YELLOW}⚠️  {message}{END}")


def print_info(message: str) -> None:
    """Print an informational message."""
    print(f"{BLUE}ℹ️  {message}{END}")


def print_header(message: str) -> None:
    """Print a section header."""
    print(f"\n{BOLD}{message}{END}")
    print("=" * len(message))


def validate_corpus(corpus_file: Path) -> tuple[bool, set[str], list[str]]:
    """Validate a corpus JSONL file."""
    print_header("Validating Corpus File")
    result = _validate_jsonl_collection(
        file_path=corpus_file,
        label="corpus",
        required_fields=("_id", "text"),
        optional_string_fields=("title",),
    )
    _report_jsonl_result("passages", result)
    return result.valid, result.item_ids, result.errors


def validate_queries(queries_file: Path) -> tuple[bool, set[str], list[str]]:
    """Validate a queries JSONL file."""
    print_header("Validating Queries File")
    result = _validate_jsonl_collection(
        file_path=queries_file,
        label="queries",
        required_fields=("_id", "text"),
    )
    _report_jsonl_result("queries", result)
    return result.valid, result.item_ids, result.errors


def validate_qrels(
    qrels_file: Path,
    corpus_ids: set[str],
    query_ids: set[str],
) -> tuple[bool, list[str]]:
    """Validate a qrels TSV file and its references to corpus and queries."""
    print_header("Validating Qrels File")
    result = _validate_qrels_file(qrels_file, corpus_ids, query_ids)
    _report_qrels_result(result)
    return result.valid, result.errors


def validate_coverage(corpus_ids: set[str], query_ids: set[str], qrels_file: Path) -> None:
    """Analyze annotation coverage and print recommendations."""
    print_header("Annotation Coverage Analysis")
    try:
        rows = _read_qrels_rows(qrels_file)
    except (OSError, ValueError) as exc:
        print_error(f"Error analyzing coverage: {exc}")
        return

    annotated_queries = {row["query_id"] for row in rows}
    query_coverage = len(annotated_queries) / len(query_ids) * 100 if query_ids else 0
    print_info(
        "Queries with annotations: "
        f"{len(annotated_queries)} / {len(query_ids)} ({query_coverage:.1f}%)"
    )

    if query_coverage < 100:
        unannotated = sorted(query_ids - annotated_queries)
        print_warning(f"{len(unannotated)} queries have no annotations")
        if len(unannotated) <= 5:
            print("  Missing annotations for:")
            for query_id in unannotated:
                print(f"    - {query_id}")

    if not corpus_ids or not query_ids:
        return

    total_possible = len(corpus_ids) * len(query_ids)
    actual_annotations = len(rows)
    coverage_pct = actual_annotations / total_possible * 100 if total_possible else 0
    print_info(
        f"Overall coverage: {actual_annotations:,} / {total_possible:,} ({coverage_pct:.2f}%)"
    )

    if coverage_pct < 1:
        print_warning("Coverage is < 1% (this is normal for large datasets)")
        print_info("BEIR datasets typically have 5-15% coverage")
    if coverage_pct < 0.1:
        print_warning("Coverage is very sparse (< 0.1%)")
        print_info("Recommendation: Annotate at least 100-200 passages per query")


def main() -> None:
    """Parse CLI arguments and validate the configured MTEB corpus files."""
    args = parse_args()
    print(f"{BOLD}MTEB Dataset Validator{END}")
    print("=" * 50)

    corpus_valid, corpus_ids, corpus_errors = validate_corpus(args.corpus)
    queries_valid, query_ids, queries_errors = validate_queries(args.queries)

    qrels_valid = False
    qrels_errors: list[str] = []
    if corpus_valid and queries_valid:
        qrels_valid, qrels_errors = validate_qrels(args.qrels, corpus_ids, query_ids)
    else:
        print_error("Skipping qrels validation due to corpus/queries errors")

    if corpus_valid and queries_valid and qrels_valid:
        validate_coverage(corpus_ids, query_ids, args.qrels)

    all_valid = corpus_valid and queries_valid and qrels_valid
    all_errors = corpus_errors + queries_errors + qrels_errors
    _print_final_summary(all_valid, all_errors)
    sys.exit(0 if all_valid else 1)


def parse_args() -> argparse.Namespace:
    """Build and parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Validate MTEB dataset files (corpus, queries, qrels)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate_mteb_dataset.py --corpus corpus.jsonl --queries queries.jsonl --qrels qrels.tsv
  python validate_mteb_dataset.py --corpus data/corpus.jsonl \\
      --queries data/queries.jsonl \\
      --qrels data/qrels.tsv
        """,
    )
    parser.add_argument("--corpus", type=Path, required=True, help="Path to corpus.jsonl file")
    parser.add_argument("--queries", type=Path, required=True, help="Path to queries.jsonl file")
    parser.add_argument("--qrels", type=Path, required=True, help="Path to qrels.tsv file")
    return parser.parse_args()


def _validate_jsonl_collection(
    *,
    file_path: Path,
    label: str,
    required_fields: tuple[str, ...],
    optional_string_fields: tuple[str, ...] = (),
) -> JsonlValidationResult:
    """Validate a JSONL collection with `_id` and text-like fields."""
    if not file_path.exists():
        message = f"File not found: {file_path}"
        print_error(f"{label.title()} file not found: {file_path}")
        return JsonlValidationResult(valid=False, item_ids=set(), errors=[message])

    state = JsonlValidationState()

    try:
        with file_path.open(encoding="utf-8") as file_obj:
            for line_number, raw_line in enumerate(file_obj, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                record = _decode_json_record(line, line_number, state.errors)
                if record is None:
                    continue
                _validate_record_fields(
                    record=record,
                    line_number=line_number,
                    required_fields=required_fields,
                    optional_string_fields=optional_string_fields,
                    state=state,
                )
    except OSError as exc:
        state.errors.append(f"Error reading {label} file: {exc}")
        return JsonlValidationResult(valid=False, item_ids=set(), errors=state.errors)

    return JsonlValidationResult(
        valid=not state.errors,
        item_ids=state.item_ids,
        errors=state.errors,
        duplicate_ids=state.duplicate_ids,
    )


def _decode_json_record(
    line: str,
    line_number: int,
    errors: list[str],
) -> dict[str, Any] | None:
    """Decode one JSONL record and accumulate JSON errors."""
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        errors.append(f"Line {line_number}: Invalid JSON - {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"Line {line_number}: Record must be a JSON object")
        return None
    return payload


def _validate_record_fields(
    *,
    record: dict[str, Any],
    line_number: int,
    required_fields: tuple[str, ...],
    optional_string_fields: tuple[str, ...],
    state: JsonlValidationState,
) -> None:
    """Validate one record's required and optional fields."""
    missing_fields = [field for field in required_fields if field not in record]
    if missing_fields:
        for field_name in missing_fields:
            state.errors.append(f"Line {line_number}: Missing '{field_name}' field")
        return

    record_id = record["_id"]
    text_value = record["text"]
    if record_id in state.item_ids:
        state.duplicate_ids.append(str(record_id))
        state.errors.append(f"Line {line_number}: Duplicate ID '{record_id}'")
    state.item_ids.add(str(record_id))

    if not isinstance(record_id, str):
        state.errors.append(f"Line {line_number}: '_id' must be a string")
    if not isinstance(text_value, str):
        state.errors.append(f"Line {line_number}: 'text' must be a string")
    elif not text_value.strip():
        state.errors.append(f"Line {line_number}: 'text' field is empty")

    for field_name in optional_string_fields:
        field_value = record.get(field_name)
        if field_value is not None and not isinstance(field_value, str):
            state.errors.append(f"Line {line_number}: '{field_name}' must be a string")


def _validate_qrels_file(
    qrels_file: Path,
    corpus_ids: set[str],
    query_ids: set[str],
) -> QrelsValidationResult:
    """Validate a qrels TSV file and accumulate statistics."""
    if not qrels_file.exists():
        message = f"File not found: {qrels_file}"
        print_error(f"Qrels file not found: {qrels_file}")
        return QrelsValidationResult(valid=False, errors=[message])

    state = QrelsValidationState()
    references = QrelsReferenceSet(query_ids=query_ids, corpus_ids=corpus_ids)

    try:
        with qrels_file.open(encoding="utf-8") as file_obj:
            reader = csv.reader(file_obj, delimiter="\t")
            header = next(reader, None)
            if header != ["query-id", "corpus-id", "score"]:
                return QrelsValidationResult(
                    valid=False,
                    errors=["Invalid header. Expected: query-id\\tcorpus-id\\tscore"],
                )

            for line_number, row in enumerate(reader, start=2):
                _process_qrels_row(
                    row=row,
                    line_number=line_number,
                    references=references,
                    state=state,
                )
    except OSError as exc:
        state.errors.append(f"Error reading qrels file: {exc}")
    except csv.Error as exc:
        state.errors.append(f"Error parsing qrels file: {exc}")

    return QrelsValidationResult(
        valid=not state.errors,
        errors=state.errors,
        stats=state.stats,
        missing_refs=state.missing_refs,
    )


def _process_qrels_row(
    *,
    row: list[str],
    line_number: int,
    references: QrelsReferenceSet,
    state: QrelsValidationState,
) -> None:
    """Validate one qrels row."""
    if len(row) != 3:
        state.errors.append(f"Line {line_number}: Expected 3 columns, got {len(row)}")
        return

    query_id, corpus_id, score_str = row
    state.stats.total_annotations += 1
    state.stats.annotations_per_query[query_id] += 1
    _validate_qrels_references(
        line_number=line_number,
        query_id=query_id,
        corpus_id=corpus_id,
        references=references,
        state=state,
    )
    _validate_qrels_score(
        line_number=line_number,
        score_str=score_str,
        state=state,
    )


def _validate_qrels_references(
    *,
    line_number: int,
    query_id: str,
    corpus_id: str,
    references: QrelsReferenceSet,
    state: QrelsValidationState,
) -> None:
    """Validate qrels query and corpus references."""
    if query_id not in references.query_ids:
        state.missing_refs.query_ids.add(query_id)
        if len(state.missing_refs.query_ids) <= MAX_ERROR_PREVIEW:
            state.errors.append(
                f"Line {line_number}: Query ID '{query_id}' not found in queries file"
            )
    if corpus_id not in references.corpus_ids:
        state.missing_refs.corpus_ids.add(corpus_id)
        if len(state.missing_refs.corpus_ids) <= MAX_ERROR_PREVIEW:
            state.errors.append(
                f"Line {line_number}: Corpus ID '{corpus_id}' not found in corpus file"
            )


def _validate_qrels_score(
    *,
    line_number: int,
    score_str: str,
    state: QrelsValidationState,
) -> None:
    """Validate a qrels relevance score."""
    try:
        score = int(score_str)
    except ValueError:
        state.errors.append(f"Line {line_number}: Score '{score_str}' is not an integer")
        return

    state.stats.score_distribution[score] += 1
    if score not in VALID_QREL_SCORES:
        state.stats.invalid_scores.append(score)
        state.errors.append(f"Line {line_number}: Invalid score '{score}'. Must be 0, 1, 2, or 3")


def _report_jsonl_result(label: str, result: JsonlValidationResult) -> None:
    """Print the validation summary for a JSONL collection."""
    print_info(f"Total {label}: {len(result.item_ids)}")
    if result.duplicate_ids:
        print_error(f"Found {len(result.duplicate_ids)} duplicate IDs")
    if result.errors:
        print_error(f"Found {len(result.errors)} errors")
        _print_error_preview(result.errors)
        return
    print_success(f"File is valid ({len(result.item_ids)} {label})")


def _report_qrels_result(result: QrelsValidationResult) -> None:
    """Print the validation summary for a qrels file."""
    print_info(f"Total annotations: {result.stats.total_annotations}")
    if result.stats.annotations_per_query:
        counts = result.stats.annotations_per_query.values()
        average = sum(counts) / len(result.stats.annotations_per_query)
        print_info(f"Average annotations per query: {average:.1f}")
        print_info(f"Min annotations per query: {min(counts)}")
        print_info(f"Max annotations per query: {max(counts)}")

    print_info("Score distribution:")
    for score in sorted(result.stats.score_distribution):
        count = result.stats.score_distribution[score]
        percentage = (
            count / result.stats.total_annotations * 100 if result.stats.total_annotations else 0
        )
        print(f"  Score {score}: {count} ({percentage:.1f}%)")

    if result.missing_refs.query_ids:
        print_error(
            "Found "
            f"{len(result.missing_refs.query_ids)} query IDs in qrels "
            "not present in queries file"
        )
        _print_preview_warning(result.missing_refs.query_ids)
    if result.missing_refs.corpus_ids:
        print_error(
            "Found "
            f"{len(result.missing_refs.corpus_ids)} corpus IDs in qrels "
            "not present in corpus file"
        )
        _print_preview_warning(result.missing_refs.corpus_ids)
    if result.stats.invalid_scores:
        print_error(f"Found {len(result.stats.invalid_scores)} invalid scores (not in 0-3 range)")

    if result.errors:
        print_error(f"Found {len(result.errors)} errors in qrels file")
        _print_error_preview(result.errors)
        return
    print_success(f"Qrels file is valid ({result.stats.total_annotations} annotations)")


def _print_error_preview(errors: list[str]) -> None:
    """Print the first N validation errors."""
    for error in errors[:MAX_ERROR_PREVIEW]:
        print(f"  - {error}")
    if len(errors) > MAX_ERROR_PREVIEW:
        print_warning(f"  ... and {len(errors) - MAX_ERROR_PREVIEW} more errors")


def _print_preview_warning(values: set[str]) -> None:
    """Print a preview warning when there are many missing references."""
    if len(values) > MAX_ERROR_PREVIEW:
        print_warning(f"  (showing first {MAX_ERROR_PREVIEW} of {len(values)})")


def _read_qrels_rows(qrels_file: Path) -> list[dict[str, str]]:
    """Read qrels rows into a normalized list for coverage reporting."""
    with qrels_file.open(encoding="utf-8") as file_obj:
        reader = csv.reader(file_obj, delimiter="\t")
        header = next(reader, None)
        if header != ["query-id", "corpus-id", "score"]:
            raise ValueError("Invalid header. Expected query-id\\tcorpus-id\\tscore")
        rows = []
        for row in reader:
            if len(row) != 3:
                continue
            rows.append({"query_id": row[0], "corpus_id": row[1], "score": row[2]})
    return rows


def _print_final_summary(all_valid: bool, all_errors: list[str]) -> None:
    """Print the final validation summary block."""
    print_header("Validation Summary")
    if all_valid:
        print_success("All files are valid and cross-references are consistent")
        print("\n✨ Dataset is ready for MTEB evaluation!")
        return

    print_error(f"Validation failed with {len(all_errors)} total errors")
    print("\n🔧 Fix the errors above and re-run validation")


if __name__ == "__main__":
    main()
