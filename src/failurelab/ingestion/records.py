"""In-memory trace ingestion.

Mirrors the JSONL ingestion contract for iterables of already-parsed traces or
mappings, so the analysis engine receives an identical ``IngestionResult`` no
matter whether the input came from a file or from Python objects. There is no
file or blank-row concept here, so ``blank_rows`` is always ``0``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import ValidationError

from failurelab.ingestion.jsonl import IngestionResult
from failurelab.models.trace import TraceRecord, ValidationIssue

IN_MEMORY_SOURCE = "<in-memory>"


def ingest_records(
    items: Iterable[TraceRecord | Mapping[str, Any]], *, strict: bool
) -> IngestionResult:
    traces: list[TraceRecord] = []
    issues: list[ValidationIssue] = []
    seen_ids: set[str] = set()
    duplicate_ids = 0

    for row_number, item in enumerate(items, start=1):
        if isinstance(item, TraceRecord):
            trace = item
        elif isinstance(item, Mapping):
            payload = dict(item)
            try:
                trace = TraceRecord.model_validate(payload)
            except ValidationError as error:
                first = error.errors()[0]
                field_path = ".".join(str(part) for part in first["loc"])
                trace_id = payload.get("trace_id")
                issues.append(
                    ValidationIssue(
                        row_number=row_number,
                        trace_id=trace_id if isinstance(trace_id, str) else None,
                        error_type="schema_error",
                        field_path=field_path or None,
                        message=first["msg"],
                        input_file=IN_MEMORY_SOURCE,
                    )
                )
                if strict:
                    break
                continue
        else:
            raise TypeError(f"trace input items must be TraceRecord or Mapping, got {type(item)!r}")

        if trace.trace_id in seen_ids:
            duplicate_ids += 1
            issues.append(
                ValidationIssue(
                    row_number=row_number,
                    trace_id=trace.trace_id,
                    error_type="duplicate_id",
                    field_path="trace_id",
                    message="duplicate trace_id",
                    input_file=IN_MEMORY_SOURCE,
                )
            )
            if strict:
                break
            continue

        seen_ids.add(trace.trace_id)
        traces.append(trace)

    if strict and issues:
        return IngestionResult(traces=[], issues=issues, duplicate_ids=duplicate_ids, blank_rows=0)
    return IngestionResult(traces=traces, issues=issues, duplicate_ids=duplicate_ids, blank_rows=0)
