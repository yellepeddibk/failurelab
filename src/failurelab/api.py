"""Public Python API for FailureLab.

These functions are the supported entry points for using FailureLab as a
library. They accept a JSONL path, or an iterable of ``TraceRecord`` objects or
mappings, normalize everything through a single boundary, and return a report
object. The Python API performs no filesystem writes; call ``report.write(...)``
to persist artifacts.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from failurelab.comparison.service import compare_traces
from failurelab.config.settings import FailureLabConfig
from failurelab.exceptions import InvalidTraceDataError
from failurelab.ingestion.jsonl import IngestionResult, ingest_jsonl
from failurelab.ingestion.records import ingest_records
from failurelab.models.trace import TraceRecord
from failurelab.reports.models import (
    AnalysisReport,
    ComparisonReport,
    InputMetadata,
    ValidationReport,
    analysis_report,
    comparison_report,
    validation_report,
)
from failurelab.services.pipeline import run_analysis

TraceInput = str | os.PathLike[str] | Iterable[TraceRecord | Mapping[str, Any]]


def _ingest(source: TraceInput, *, strict: bool) -> IngestionResult:
    if isinstance(source, (str, os.PathLike)):
        return ingest_jsonl(Path(os.fspath(source)), strict=strict)
    return ingest_records(list(source), strict=strict)


def _provenance(source: TraceInput, ingestion: IngestionResult) -> InputMetadata:
    if isinstance(source, (str, os.PathLike)):
        return InputMetadata.from_path(Path(os.fspath(source)))
    return InputMetadata.from_records(ingestion.traces)


def _resolve_config(
    config: FailureLabConfig | None, *, strict: bool | None
) -> tuple[FailureLabConfig, bool]:
    resolved = (config if config is not None else FailureLabConfig()).model_copy(deep=True)
    effective_strict = (resolved.ingestion.mode == "strict") if strict is None else strict
    resolved.ingestion.mode = "strict" if effective_strict else "skip_invalid"
    return resolved, effective_strict


def validate(source: TraceInput) -> ValidationReport:
    """Validate trace input and report every issue found.

    Always inspects the complete input; it does not stop at the first problem
    and never raises for invalid data. Usage errors (an unsupported item type)
    still raise ``TypeError``.
    """
    return validation_report(_ingest(source, strict=False))


def analyze(
    source: TraceInput,
    *,
    config: FailureLabConfig | None = None,
    strict: bool | None = None,
) -> AnalysisReport:
    """Analyze traces and return an in-memory report.

    ``strict`` defaults to the configured ingestion mode (strict). In strict
    mode any invalid input raises ``InvalidTraceDataError``. In skip-invalid mode the
    report is computed over the valid traces and carries the issues; when no
    traces are usable the report is honest and ``data_quality.analyzable`` is
    ``False``.
    """
    resolved, effective_strict = _resolve_config(config, strict=strict)
    ingestion = _ingest(source, strict=effective_strict)
    if effective_strict and ingestion.issues:
        raise InvalidTraceDataError(ingestion.issues)
    provenance = _provenance(source, ingestion)
    computation = run_analysis(ingestion.traces, resolved)
    return analysis_report(computation, ingestion, provenance, resolved)


def compare(
    baseline: TraceInput,
    candidate: TraceInput,
    *,
    config: FailureLabConfig | None = None,
) -> ComparisonReport:
    """Compare baseline and candidate traces and return an in-memory report.

    Both inputs are ingested strictly; invalid input on either side raises
    ``InvalidTraceDataError``.
    """
    resolved = (config if config is not None else FailureLabConfig()).model_copy(deep=True)

    baseline_ingestion = _ingest(baseline, strict=True)
    if baseline_ingestion.issues:
        raise InvalidTraceDataError(baseline_ingestion.issues)
    candidate_ingestion = _ingest(candidate, strict=True)
    if candidate_ingestion.issues:
        raise InvalidTraceDataError(candidate_ingestion.issues)

    result = compare_traces(baseline_ingestion.traces, candidate_ingestion.traces, resolved)
    return comparison_report(
        result,
        baseline_ingestion,
        candidate_ingestion,
        _provenance(baseline, baseline_ingestion),
        _provenance(candidate, candidate_ingestion),
        resolved,
    )
