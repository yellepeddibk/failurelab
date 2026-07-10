"""Report rendering and atomic output writers."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from failurelab import __version__
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
    input_path: Path,
    resolved_config: dict[str, Any],
    valid_count: int,
    invalid_count: int,
    generated_files: list[str],
) -> dict[str, Any]:
    digest = (
        hashlib.sha256(input_path.read_bytes()).hexdigest()
        if input_path.exists() and input_path.is_file()
        else None
    )
    run_id = hashlib.sha256(
        f"{input_path.name}:{digest}:{valid_count}:{invalid_count}".encode("utf-8")
    ).hexdigest()[:12]
    return {
        "failurelab_version": __version__,
        "schema_version": SCHEMA_VERSION,
        "resolved_config": resolved_config,
        "input_file": input_path.name,
        "input_sha256": digest,
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
