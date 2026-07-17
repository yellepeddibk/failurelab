"""Core orchestration services for CLI commands.

``run_analysis`` is the pure, filesystem-free engine shared by the Python API
and these compatibility wrappers. The wrappers ingest a path, run the engine,
build a report, and persist it, returning the ``AnalyzeResult`` shape that
existing callers expect.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from failurelab.comparison.service import ComparisonResult, compare_traces
from failurelab.config.settings import FailureLabConfig
from failurelab.discovery.slices import CategoricalFailureSliceDiscoverer
from failurelab.evals.metrics import EvaluationBundle, compute_metrics
from failurelab.ingestion.jsonl import IngestionResult, ingest_jsonl
from failurelab.models.trace import TraceRecord
from failurelab.regression.generator import generate_regression_tests
from failurelab.reports.models import (
    AnalysisComputation,
    InputMetadata,
    analysis_report,
    comparison_report,
)
from failurelab.root_cause.analyzer import DeterministicRootCauseAnalyzer


@dataclass(slots=True)
class AnalyzeResult:
    ingestion: IngestionResult
    metrics: EvaluationBundle | None
    comparison: ComparisonResult | None
    output_files: list[Path]


def run_analysis(traces: list[TraceRecord], config: FailureLabConfig) -> AnalysisComputation:
    """Compute all deterministic analysis artifacts in memory (no I/O)."""
    metrics = compute_metrics(
        traces,
        retrieval_k=config.evaluation.retrieval_k,
        excessive_steps_threshold=config.evaluation.excessive_steps_threshold,
    )
    discoverer = CategoricalFailureSliceDiscoverer()
    findings = discoverer.discover(
        traces,
        retrieval_k=config.evaluation.retrieval_k,
        min_support=config.slices.minimum_support,
        max_findings=config.slices.maximum_findings,
    )
    analyzer = DeterministicRootCauseAnalyzer()
    hypotheses = analyzer.analyze(
        traces,
        retrieval_k=config.evaluation.retrieval_k,
        repeated_tool_threshold=config.root_cause.repeated_tool_threshold,
        excessive_steps_threshold=config.evaluation.excessive_steps_threshold,
    )
    regression = generate_regression_tests(
        traces, findings, config.regression_tests.include_thresholds
    )
    return AnalysisComputation(
        metrics=metrics, findings=findings, hypotheses=hypotheses, regression=regression
    )


def validate(path: Path, strict: bool) -> IngestionResult:
    return ingest_jsonl(path, strict=strict)


def analyze(
    path: Path, output_dir: Path, config: FailureLabConfig, strict: bool, overwrite: bool
) -> AnalyzeResult:
    config = config.model_copy(deep=True)
    config.ingestion.mode = "strict" if strict else "skip_invalid"
    ingestion = ingest_jsonl(path, strict=strict)
    if strict and ingestion.issues:
        return AnalyzeResult(ingestion=ingestion, metrics=None, comparison=None, output_files=[])

    computation = run_analysis(ingestion.traces, config)
    report = analysis_report(computation, ingestion, InputMetadata.from_path(path), config)
    written = report.write(output_dir, overwrite=overwrite)
    return AnalyzeResult(
        ingestion=ingestion, metrics=computation.metrics, comparison=None, output_files=written
    )


def compare(
    baseline_path: Path,
    candidate_path: Path,
    output_dir: Path,
    config: FailureLabConfig,
    overwrite: bool,
) -> AnalyzeResult:
    baseline = ingest_jsonl(baseline_path, strict=True)
    candidate = ingest_jsonl(candidate_path, strict=True)
    if baseline.issues or candidate.issues:
        issues = baseline.issues + candidate.issues
        return AnalyzeResult(
            ingestion=IngestionResult(traces=[], issues=issues, duplicate_ids=0, blank_rows=0),
            metrics=None,
            comparison=None,
            output_files=[],
        )

    result = compare_traces(baseline.traces, candidate.traces, config)
    report = comparison_report(
        result,
        baseline,
        candidate,
        InputMetadata.from_path(baseline_path),
        InputMetadata.from_path(candidate_path),
        config,
    )
    written = report.write(output_dir, overwrite=overwrite)
    return AnalyzeResult(
        ingestion=IngestionResult(
            traces=baseline.traces + candidate.traces, issues=[], duplicate_ids=0, blank_rows=0
        ),
        metrics=None,
        comparison=result,
        output_files=written,
    )
