"""Core orchestration services for CLI commands."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from pathlib import Path
from typing import cast

from failurelab.comparison.service import ComparisonResult, compare_traces
from failurelab.config.settings import FailureLabConfig
from failurelab.discovery.slices import CategoricalFailureSliceDiscoverer
from failurelab.evals.metrics import EvaluationBundle, compute_metrics
from failurelab.ingestion.jsonl import IngestionResult, ingest_jsonl
from failurelab.regression.generator import generate_regression_tests
from failurelab.reports.writers import (
    assert_output_path_safe,
    render_findings_payload,
    render_markdown_report,
    render_metrics_payload,
    render_run_manifest,
    write_invalid_traces,
    write_json_atomic,
    write_text_atomic,
    write_yaml_atomic,
)
from failurelab.root_cause.analyzer import DeterministicRootCauseAnalyzer


@dataclass(slots=True)
class AnalyzeResult:
    ingestion: IngestionResult
    metrics: EvaluationBundle | None
    comparison: ComparisonResult | None
    output_files: list[Path]


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

    assert_output_path_safe(output_dir, overwrite)

    metrics = compute_metrics(
        ingestion.traces,
        retrieval_k=config.evaluation.retrieval_k,
        excessive_steps_threshold=config.evaluation.excessive_steps_threshold,
    )
    discoverer = CategoricalFailureSliceDiscoverer()
    findings = discoverer.discover(
        ingestion.traces,
        retrieval_k=config.evaluation.retrieval_k,
        min_support=config.slices.minimum_support,
        max_findings=config.slices.maximum_findings,
    )
    analyzer = DeterministicRootCauseAnalyzer()
    hypotheses = analyzer.analyze(
        ingestion.traces,
        retrieval_k=config.evaluation.retrieval_k,
        repeated_tool_threshold=config.root_cause.repeated_tool_threshold,
        excessive_steps_threshold=config.evaluation.excessive_steps_threshold,
    )
    regression = generate_regression_tests(
        ingestion.traces, findings, config.regression_tests.include_thresholds
    )

    metrics_path = output_dir / "metrics.json"
    findings_path = output_dir / "findings.json"
    markdown_path = output_dir / "report.md"
    regression_path = output_dir / "regression_tests.yaml"
    manifest_path = output_dir / "run_manifest.json"

    write_json_atomic(metrics_path, render_metrics_payload(metrics.metrics, metrics.breakdowns))
    write_json_atomic(findings_path, render_findings_payload(findings, hypotheses))
    markdown = render_markdown_report(
        metrics.metrics, findings, hypotheses, regression, ingestion.issues
    )
    write_text_atomic(markdown_path, markdown)
    write_yaml_atomic(
        regression_path, [case.model_dump(exclude_none=True) for case in regression.tests]
    )
    generated_files = [
        "metrics.json",
        "findings.json",
        "report.md",
        "regression_tests.yaml",
        "run_manifest.json",
    ]
    if ingestion.issues:
        generated_files.append("invalid_traces.jsonl")
    manifest = render_run_manifest(
        input_path=path,
        resolved_config=config.model_dump(),
        valid_count=len(ingestion.traces),
        invalid_count=len(ingestion.issues),
        generated_files=generated_files,
    )
    write_json_atomic(manifest_path, manifest)

    written = [metrics_path, findings_path, markdown_path, regression_path, manifest_path]
    if ingestion.issues:
        invalid_path = output_dir / "invalid_traces.jsonl"
        write_invalid_traces(invalid_path, ingestion.issues)
        written.append(invalid_path)

    return AnalyzeResult(
        ingestion=ingestion, metrics=metrics, comparison=None, output_files=written
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

    assert_output_path_safe(output_dir, overwrite)
    comparison_json = output_dir / "comparison.json"
    comparison_md = output_dir / "comparison.md"
    gate_json = output_dir / "gate_result.json"
    matched_ids = cast(list[str], result.summary.get("matched_ids", []))
    unmatched_baseline_ids = cast(list[str], result.summary.get("unmatched_baseline_ids", []))
    unmatched_candidate_ids = cast(list[str], result.summary.get("unmatched_candidate_ids", []))

    write_json_atomic(comparison_json, result.summary)
    full_scope = cast(dict[str, dict[str, int]], result.summary.get("comparison_scope", {}))
    full_counts = full_scope.get("full_dataset", {})
    matched_counts = full_scope.get("matched_ids", {})
    configured_thresholds = {
        "max_failure_rate_increase": config.gate.max_failure_rate_increase,
        "max_latency_p95_increase_ms": config.gate.max_latency_p95_increase_ms,
    }
    full_deltas = cast(dict[str, dict[str, object]], result.summary.get("full_dataset_deltas", {}))
    matched_deltas = cast(dict[str, dict[str, object]], result.summary.get("matched_id_deltas", {}))
    write_text_atomic(
        comparison_md,
        "\n".join(
            [
                "# FailureLab Comparison Report",
                "",
                f"Gate status: {result.gate_status}",
                f"Gate evaluated: {'no' if result.gate_status == 'not_configured' else 'yes'}",
                (
                    "Gate result: not applicable"
                    if result.gate_status == "not_configured"
                    else f"Gate result: {result.gate_status}"
                ),
                f"Gate scope: {result.gate_scope}",
                "",
                "Configured thresholds:",
                (
                    f"- failure_rate delta <= {_format_markdown_value(configured_thresholds['max_failure_rate_increase'])}, "
                    f"latency_p95_ms delta <= {_format_markdown_value(configured_thresholds['max_latency_p95_increase_ms'])}"
                    if any(v is not None for v in configured_thresholds.values())
                    else "- No gate thresholds configured."
                ),
                "",
                "Full dataset scope:",
                f"- Baseline traces: {full_counts.get('baseline_trace_count', 0)}",
                f"- Candidate traces: {full_counts.get('candidate_trace_count', 0)}",
                "",
                "Matched-ID scope:",
                f"- Matched IDs: {matched_counts.get('matched_count', len(matched_ids))}",
                f"- Unmatched baseline IDs: {matched_counts.get('unmatched_baseline_count', len(unmatched_baseline_ids))}",
                f"- Unmatched candidate IDs: {matched_counts.get('unmatched_candidate_count', len(unmatched_candidate_ids))}",
                "",
                "## Full-dataset deltas",
                "| metric | baseline | candidate | delta | direction | interpretation |",
                "| --- | ---: | ---: | ---: | --- | --- |",
                *[
                    f"| {name} | {_format_markdown_value(payload.get('baseline'))} | {_format_markdown_value(payload.get('candidate'))} | {_format_markdown_value(payload.get('delta'))} | {payload.get('direction')} | {payload.get('interpretation')} |"
                    for name, payload in full_deltas.items()
                ],
                "",
                "## Matched-ID deltas",
                "| metric | baseline | candidate | delta | direction | interpretation |",
                "| --- | ---: | ---: | ---: | --- | --- |",
                *[
                    f"| {name} | {_format_markdown_value(payload.get('baseline'))} | {_format_markdown_value(payload.get('candidate'))} | {_format_markdown_value(payload.get('delta'))} | {payload.get('direction')} | {payload.get('interpretation')} |"
                    for name, payload in matched_deltas.items()
                ],
                "",
                "Gate violations:",
                *([f"- {violation.message}" for violation in result.violations] or ["- none."]),
                "",
                "No statistical significance claims.",
            ]
        )
        + "\n",
    )
    write_json_atomic(
        gate_json,
        {
            "gate_status": result.gate_status,
            "gate_passed": result.gate_passed,
            "gate_scope": result.gate_scope,
            "configured_thresholds": configured_thresholds,
            "violations": [asdict(violation) for violation in result.violations],
        },
    )
    return AnalyzeResult(
        ingestion=IngestionResult(
            traces=baseline.traces + candidate.traces, issues=[], duplicate_ids=0, blank_rows=0
        ),
        metrics=None,
        comparison=result,
        output_files=[comparison_json, comparison_md, gate_json],
    )


def _format_markdown_value(value: object) -> str:
    if value is None:
        return "unavailable"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not isfinite(value):
            return "unavailable"
        return format(value, ".12g")
    return str(value)
