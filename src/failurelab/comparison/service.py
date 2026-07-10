"""Baseline vs candidate comparison service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from failurelab.config.settings import FailureLabConfig
from failurelab.evals.metrics import compute_metrics, metric_dict
from failurelab.models.trace import TraceRecord


@dataclass(slots=True)
class GateViolation:
    metric: str
    baseline_value: float | int | None
    candidate_value: float | int | None
    message: str


@dataclass(slots=True)
class ComparisonResult:
    summary: dict[str, object]
    gate_passed: bool
    violations: list[GateViolation]


def compare_traces(
    baseline: list[TraceRecord],
    candidate: list[TraceRecord],
    config: FailureLabConfig,
) -> ComparisonResult:
    baseline_metrics = metric_dict(
        compute_metrics(
            baseline,
            retrieval_k=config.evaluation.retrieval_k,
            excessive_steps_threshold=config.evaluation.excessive_steps_threshold,
        ).metrics
    )
    candidate_metrics = metric_dict(
        compute_metrics(
            candidate,
            retrieval_k=config.evaluation.retrieval_k,
            excessive_steps_threshold=config.evaluation.excessive_steps_threshold,
        ).metrics
    )

    baseline_ids = {trace.trace_id for trace in baseline}
    candidate_ids = {trace.trace_id for trace in candidate}
    matched = sorted(baseline_ids.intersection(candidate_ids))

    summary: dict[str, object] = {
        "matched_ids": matched,
        "unmatched_baseline_ids": sorted(baseline_ids - candidate_ids),
        "unmatched_candidate_ids": sorted(candidate_ids - baseline_ids),
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
    }

    violations: list[GateViolation] = []
    fail_increase = config.gate.max_failure_rate_increase
    if fail_increase is not None:
        baseline_rate = _metric_value(baseline_metrics, "failure_rate")
        candidate_rate = _metric_value(candidate_metrics, "failure_rate")
        if isinstance(baseline_rate, (int, float)) and isinstance(candidate_rate, (int, float)):
            delta = candidate_rate - baseline_rate
            if delta > fail_increase:
                violations.append(
                    GateViolation(
                        metric="failure_rate",
                        baseline_value=baseline_rate,
                        candidate_value=candidate_rate,
                        message=f"failure_rate delta {delta:.6f} exceeds configured limit {fail_increase:.6f}",
                    )
                )

    latency_limit = config.gate.max_latency_p95_increase_ms
    if latency_limit is not None:
        baseline_p95 = _metric_value(baseline_metrics, "latency_p95_ms")
        candidate_p95 = _metric_value(candidate_metrics, "latency_p95_ms")
        if isinstance(baseline_p95, (int, float)) and isinstance(candidate_p95, (int, float)):
            delta = candidate_p95 - baseline_p95
            if delta > latency_limit:
                violations.append(
                    GateViolation(
                        metric="latency_p95_ms",
                        baseline_value=baseline_p95,
                        candidate_value=candidate_p95,
                        message=f"latency_p95_ms delta {delta:.6f} exceeds configured limit {latency_limit:.6f}",
                    )
                )

    gate_passed = not violations
    return ComparisonResult(summary=summary, gate_passed=gate_passed, violations=violations)


def _metric_value(metrics: dict[str, object], name: str) -> object | None:
    value = metrics.get(name)
    if not isinstance(value, dict):
        return None
    metric = cast(dict[str, object], value)
    return metric.get("value")
