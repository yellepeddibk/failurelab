"""Baseline vs candidate comparison service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast

from failurelab.config.settings import FailureLabConfig
from failurelab.evals.metrics import compute_metrics, metric_dict
from failurelab.models.trace import TraceRecord

TRACKED_METRICS: tuple[tuple[str, str], ...] = (
    ("failure_rate", "lower_is_better"),
    ("latency_average_ms", "lower_is_better"),
    ("latency_p95_ms", "lower_is_better"),
    ("retrieval_recall_at_k", "higher_is_better"),
    ("citation_presence_rate", "higher_is_better"),
    ("tool_success_rate", "higher_is_better"),
    ("cost_average_usd", "lower_is_better"),
    ("cost_total_usd", "lower_is_better"),
    ("cost_per_successful_trace_usd", "lower_is_better"),
)


@dataclass(slots=True)
class GateViolation:
    metric: str
    scope: str
    baseline_value: float | int | None
    candidate_value: float | int | None
    delta: float
    message: str


@dataclass(slots=True)
class ComparisonResult:
    summary: dict[str, object]
    gate_status: str
    gate_scope: str
    gate_passed: bool | None
    violations: list[GateViolation]


def compare_traces(
    baseline: list[TraceRecord],
    candidate: list[TraceRecord],
    config: FailureLabConfig,
) -> ComparisonResult:
    baseline_metrics = _compute_metric_map(baseline, config)
    candidate_metrics = _compute_metric_map(candidate, config)

    baseline_ids = {trace.trace_id for trace in baseline}
    candidate_ids = {trace.trace_id for trace in candidate}
    matched = sorted(baseline_ids.intersection(candidate_ids))
    matched_set = set(matched)
    matched_baseline = [trace for trace in baseline if trace.trace_id in matched_set]
    matched_candidate = [trace for trace in candidate if trace.trace_id in matched_set]
    matched_baseline_metrics = _compute_metric_map(matched_baseline, config)
    matched_candidate_metrics = _compute_metric_map(matched_candidate, config)
    full_dataset_deltas = _metric_deltas(baseline_metrics, candidate_metrics)
    matched_id_deltas = _metric_deltas(matched_baseline_metrics, matched_candidate_metrics)

    summary: dict[str, object] = {
        "matched_ids": matched,
        "unmatched_baseline_ids": sorted(baseline_ids - candidate_ids),
        "unmatched_candidate_ids": sorted(candidate_ids - baseline_ids),
        "baseline_metrics": baseline_metrics,
        "candidate_metrics": candidate_metrics,
        "comparison_scope": {
            "full_dataset": {
                "baseline_trace_count": len(baseline),
                "candidate_trace_count": len(candidate),
            },
            "matched_ids": {
                "matched_count": len(matched),
                "unmatched_baseline_count": len(baseline_ids - candidate_ids),
                "unmatched_candidate_count": len(candidate_ids - baseline_ids),
            },
        },
        "full_dataset_deltas": full_dataset_deltas,
        "matched_id_deltas": matched_id_deltas,
    }

    configured_thresholds = {
        "max_failure_rate_increase": config.gate.max_failure_rate_increase,
        "max_latency_p95_increase_ms": config.gate.max_latency_p95_increase_ms,
    }
    any_threshold = any(value is not None for value in configured_thresholds.values())
    scope = config.comparison.scope
    selected_deltas = matched_id_deltas if scope == "matched_ids" else full_dataset_deltas
    violations: list[GateViolation] = []
    _maybe_add_violation(
        violations,
        selected_deltas,
        scope,
        "failure_rate",
        configured_thresholds["max_failure_rate_increase"],
    )
    _maybe_add_violation(
        violations,
        selected_deltas,
        scope,
        "latency_p95_ms",
        configured_thresholds["max_latency_p95_increase_ms"],
    )

    if not any_threshold:
        gate_status = "not_configured"
        gate_passed: bool | None = None
    elif violations:
        gate_status = "failed"
        gate_passed = False
    else:
        gate_status = "passed"
        gate_passed = True
    return ComparisonResult(
        summary=summary,
        gate_status=gate_status,
        gate_scope=scope,
        gate_passed=gate_passed,
        violations=violations,
    )


def _metric_value(metrics: dict[str, object], name: str) -> object | None:
    value = metrics.get(name)
    if not isinstance(value, dict):
        return None
    metric = cast(dict[str, object], value)
    return metric.get("value")


def _compute_metric_map(traces: list[TraceRecord], config: FailureLabConfig) -> dict[str, object]:
    return metric_dict(
        compute_metrics(
            traces,
            retrieval_k=config.evaluation.retrieval_k,
            excessive_steps_threshold=config.evaluation.excessive_steps_threshold,
        ).metrics
    )


def _metric_deltas(
    baseline_metrics: dict[str, object], candidate_metrics: dict[str, object]
) -> dict[str, dict[str, Any]]:
    deltas: dict[str, dict[str, Any]] = {}
    for name, expected_direction in TRACKED_METRICS:
        base = _metric_as_dict(baseline_metrics.get(name))
        cand = _metric_as_dict(candidate_metrics.get(name))
        baseline_value = base.get("value")
        candidate_value = cand.get("value")
        direction = str(base.get("direction") or cand.get("direction") or expected_direction)
        delta: float | None = None
        interpretation = "unavailable"
        if isinstance(baseline_value, (int, float)) and isinstance(candidate_value, (int, float)):
            delta = float(candidate_value - baseline_value)
            if direction == "lower_is_better":
                interpretation = (
                    "regression" if delta > 0 else "improvement" if delta < 0 else "neutral"
                )
            elif direction == "higher_is_better":
                interpretation = (
                    "improvement" if delta > 0 else "regression" if delta < 0 else "neutral"
                )
            else:
                interpretation = "neutral"
        deltas[name] = {
            "baseline": baseline_value,
            "candidate": candidate_value,
            "delta": delta,
            "direction": direction,
            "interpretation": interpretation,
        }
    return deltas


def _metric_as_dict(value: object) -> dict[str, object]:
    if isinstance(value, dict):
        return cast(dict[str, object], value)
    return {}


def _maybe_add_violation(
    violations: list[GateViolation],
    deltas: dict[str, dict[str, Any]],
    scope: str,
    metric: str,
    threshold: float | None,
) -> None:
    if threshold is None:
        return
    delta = deltas.get(metric, {}).get("delta")
    if isinstance(delta, (int, float)) and float(delta) > threshold:
        baseline = deltas[metric].get("baseline")
        candidate = deltas[metric].get("candidate")
        violations.append(
            GateViolation(
                metric=metric,
                scope=scope,
                baseline_value=baseline if isinstance(baseline, (int, float)) else None,
                candidate_value=candidate if isinstance(candidate, (int, float)) else None,
                delta=float(delta),
                message=f"{metric} delta {float(delta):.6f} exceeds configured limit {threshold:.6f}",
            )
        )
