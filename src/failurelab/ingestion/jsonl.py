"""Incremental JSONL ingestion."""

from __future__ import annotations

import codecs
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from failurelab.models.trace import TraceRecord, ValidationIssue


@dataclass(slots=True)
class IngestionResult:
    traces: list[TraceRecord]
    issues: list[ValidationIssue]
    duplicate_ids: int
    blank_rows: int


def ingest_jsonl(path: Path, *, strict: bool) -> IngestionResult:
    traces: list[TraceRecord] = []
    issues: list[ValidationIssue] = []
    seen_ids: set[str] = set()
    duplicate_ids = 0
    blank_rows = 0

    if not path.exists():
        issues.append(
            ValidationIssue(
                row_number=1,
                error_type="file_error",
                message="file not found",
                input_file=path.name,
            )
        )
        return _strict_or_return(strict, traces, issues, duplicate_ids, blank_rows)

    if path.is_dir():
        issues.append(
            ValidationIssue(
                row_number=1,
                error_type="file_error",
                message="path is a directory",
                input_file=path.name,
            )
        )
        return _strict_or_return(strict, traces, issues, duplicate_ids, blank_rows)

    try:
        with path.open("rb") as handle:
            for row_number, raw_line in enumerate(handle, start=1):
                if row_number == 1:
                    raw_line = raw_line.removeprefix(codecs.BOM_UTF8)
                try:
                    line = raw_line.decode("utf-8")
                except UnicodeDecodeError:
                    issues.append(
                        ValidationIssue(
                            row_number=row_number,
                            error_type="file_error",
                            message="invalid UTF-8",
                            input_file=path.name,
                        )
                    )
                    if strict:
                        break
                    continue

                stripped = line.strip()
                if not stripped:
                    blank_rows += 1
                    continue
                if stripped.startswith("#"):
                    issues.append(
                        ValidationIssue(
                            row_number=row_number,
                            error_type="json_error",
                            message="comments are not allowed in JSONL",
                            input_file=path.name,
                        )
                    )
                    if strict:
                        break
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as error:
                    issues.append(
                        ValidationIssue(
                            row_number=row_number,
                            error_type="json_error",
                            message=f"malformed JSON: {error.msg}",
                            safe_excerpt=stripped[:120],
                            input_file=path.name,
                        )
                    )
                    if strict:
                        break
                    continue

                try:
                    trace = TraceRecord.model_validate(payload)
                except ValidationError as error:
                    issue = error.errors()[0]
                    field_path = ".".join(str(item) for item in issue["loc"])
                    issues.append(
                        ValidationIssue(
                            row_number=row_number,
                            trace_id=payload.get("trace_id") if isinstance(payload, dict) else None,
                            error_type="schema_error",
                            field_path=field_path or None,
                            message=issue["msg"],
                            input_file=path.name,
                        )
                    )
                    if strict:
                        break
                    continue

                if trace.trace_id in seen_ids:
                    duplicate_ids += 1
                    issues.append(
                        ValidationIssue(
                            row_number=row_number,
                            trace_id=trace.trace_id,
                            error_type="duplicate_id",
                            field_path="trace_id",
                            message="duplicate trace_id",
                            input_file=path.name,
                        )
                    )
                    if strict:
                        break
                    continue

                seen_ids.add(trace.trace_id)
                traces.append(trace)
    except OSError as error:
        issues.append(
            ValidationIssue(
                row_number=1,
                error_type="file_error",
                message=str(error),
                input_file=path.name,
            )
        )

    return _strict_or_return(strict, traces, issues, duplicate_ids, blank_rows)


def _strict_or_return(
    strict: bool,
    traces: list[TraceRecord],
    issues: list[ValidationIssue],
    duplicate_ids: int,
    blank_rows: int,
) -> IngestionResult:
    if strict and issues:
        return IngestionResult(
            traces=[], issues=issues, duplicate_ids=duplicate_ids, blank_rows=blank_rows
        )
    return IngestionResult(
        traces=traces, issues=issues, duplicate_ids=duplicate_ids, blank_rows=blank_rows
    )
