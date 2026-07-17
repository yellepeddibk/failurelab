"""Report rendering and atomic output writers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any, cast

import yaml

from failurelab._version import __version__
from failurelab.comparison.service import ComparisonResult
from failurelab.config.settings import FailureLabConfig
from failurelab.discovery.slices import FailureSlice
from failurelab.evals.metrics import MetricResult, metric_dict
from failurelab.models.trace import SCHEMA_VERSION, ValidationIssue
from failurelab.regression.generator import RegressionBundle
from failurelab.root_cause.analyzer import RootCauseHypothesis

KNOWN_OUTPUT_FILES = {
    "metrics.json",
    "findings.json",
    "report.md",
    "regression_tests.yaml",
    "run_manifest.json",
    "invalid_traces.jsonl",
    "comparison.json",
    "comparison.md",
    "gate_result.json",
}


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    _write_text_atomic(
        path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def write_yaml_atomic(path: Path, payload: Any) -> None:
    _write_text_atomic(path, yaml.safe_dump(payload, sort_keys=True, allow_unicode=True))


def write_text_atomic(path: Path, content: str) -> None:
    _write_text_atomic(path, content)


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=str(path.parent)
    ) as handle:
        temp_name = handle.name
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temp_name, path)


def assert_output_path_safe(output_dir: Path, overwrite: bool) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    if overwrite:
        return
    collisions = [name for name in KNOWN_OUTPUT_FILES if (output_dir / name).exists()]
    if collisions:
        joined = ", ".join(sorted(collisions))
        raise FileExistsError(f"output files already exist: {joined}. Use --overwrite to replace.")


def render_markdown_report(
    metrics: list[MetricResult],
    findings: list[FailureSlice],
    hypotheses: list[RootCauseHypothesis],
    regression_bundle: RegressionBundle,
    issues: list[ValidationIssue],
) -> str:
    lines = [
        "# FailureLab Analysis Report",
        "",
        "## 1. Run overview",
        "Deterministic analysis generated from local trace data.",
        "",
        "## 2. Data quality",
        f"Invalid rows detected: {len(issues)}",
        "",
        "## 3. Outcomes",
    ]
    for metric in metrics:
        if metric.name in {"failure_rate", "known_outcome_count", "total_rows"}:
            lines.append(f"- **{metric.name}**: {metric.value}")
    lines.extend(
        [
            "",
            "## 4. Retrieval",
            _metric_line(metrics, "retrieval_recall_at_k"),
            "",
            "## 5. Citations",
            _metric_line(metrics, "citation_presence_rate"),
            "",
            "## 6. Agent/tool metrics",
            _metric_line(metrics, "tool_success_rate"),
            "",
            "## 7. Latency",
            _metric_line(metrics, "latency_average_ms"),
            _metric_line(metrics, "latency_p95_ms"),
            "",
            "## 8. Cost",
            _metric_line(metrics, "cost_total_usd"),
            _metric_line(metrics, "cost_per_successful_trace_usd"),
            "",
            "## 9. Breakdowns",
            "Breakdowns are available in metrics.json.",
            "",
            "## 10. Failure slices",
        ]
    )
    lines.extend(
        [
            f"- {f.name}={f.value} support={f.support} failure_rate={f.failure_rate}"
            for f in findings
        ]
        or ["- No elevated failure slices found."]
    )
    lines.extend(["", "## 11. Root-cause hypotheses"])
    lines.extend(
        [f"- {h.source_trace_id}: {h.hypothesis} ({h.confidence})" for h in hypotheses]
        or ["- No root-cause hypotheses."]
    )
    lines.extend(
        [
            "",
            "## 12. Draft regression tests",
            f"Generated cases: {len(regression_bundle.tests)}",
            "",
            "## 13. Limitations",
            "- Deterministic heuristic analysis only.",
            "- No significance claims.",
            "",
            "## 14. Recommended next steps",
            (
                "- Investigate highest-uplift slices with additional controlled experiments."
                if findings
                else "- No elevated slices to prioritize from this run."
            ),
        ]
    )
    return "\n".join(lines) + "\n"


def _metric_line(metrics: list[MetricResult], name: str) -> str:
    metric = next((item for item in metrics if item.name == name), None)
    if metric is None:
        return f"- {name}: unavailable"
    if metric.value is None:
        return f"- {name}: unavailable ({metric.unavailable_reason})"
    return f"- {name}: {metric.value}"


def render_run_manifest(
    *,
    input_name: str,
    input_sha256: str | None,
    resolved_config: dict[str, Any],
    valid_count: int,
    invalid_count: int,
    generated_files: list[str],
) -> dict[str, Any]:
    run_id = hashlib.sha256(
        f"{input_name}:{input_sha256}:{valid_count}:{invalid_count}".encode("utf-8")
    ).hexdigest()[:12]
    return {
        "failurelab_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "resolved_config": resolved_config,
        "input_file": input_name,
        "input_sha256": input_sha256,
        "valid_trace_count": valid_count,
        "invalid_row_count": invalid_count,
        "generated_files": sorted(generated_files),
        "run_timestamp": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
    }


def render_findings_payload(
    findings: list[FailureSlice], hypotheses: list[RootCauseHypothesis]
) -> dict[str, Any]:
    return {
        "failure_slices": [asdict(finding) for finding in findings],
        "root_cause_hypotheses": [asdict(hypothesis) for hypothesis in hypotheses],
    }


def render_metrics_payload(
    metrics: list[MetricResult], breakdowns: dict[str, Any]
) -> dict[str, Any]:
    return {
        "metrics": metric_dict(metrics),
        "breakdowns": breakdowns,
    }


def write_invalid_traces(path: Path, issues: list[ValidationIssue]) -> None:
    lines = [
        json.dumps(issue.model_dump(exclude_none=True), ensure_ascii=False, sort_keys=True)
        for issue in issues
    ]
    _write_text_atomic(path, "\n".join(lines) + ("\n" if lines else ""))


def render_comparison_markdown(result: ComparisonResult, config: FailureLabConfig) -> str:
    matched_ids = cast(list[str], result.summary.get("matched_ids", []))
    unmatched_baseline_ids = cast(list[str], result.summary.get("unmatched_baseline_ids", []))
    unmatched_candidate_ids = cast(list[str], result.summary.get("unmatched_candidate_ids", []))
    full_scope = cast(dict[str, dict[str, int]], result.summary.get("comparison_scope", {}))
    full_counts = full_scope.get("full_dataset", {})
    matched_counts = full_scope.get("matched_ids", {})
    configured_thresholds = {
        "max_failure_rate_increase": config.gate.max_failure_rate_increase,
        "max_latency_p95_increase_ms": config.gate.max_latency_p95_increase_ms,
    }
    full_deltas = cast(dict[str, dict[str, object]], result.summary.get("full_dataset_deltas", {}))
    matched_deltas = cast(dict[str, dict[str, object]], result.summary.get("matched_id_deltas", {}))
    return (
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
        + "\n"
    )


def render_gate_payload(result: ComparisonResult, config: FailureLabConfig) -> dict[str, Any]:
    configured_thresholds = {
        "max_failure_rate_increase": config.gate.max_failure_rate_increase,
        "max_latency_p95_increase_ms": config.gate.max_latency_p95_increase_ms,
    }
    return {
        "gate_status": result.gate_status,
        "gate_passed": result.gate_passed,
        "gate_scope": result.gate_scope,
        "configured_thresholds": configured_thresholds,
        "violations": [asdict(violation) for violation in result.violations],
    }


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
