"""Deterministic metric computation."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from statistics import mean

from failurelab.models.trace import TraceRecord
from failurelab.utilities.serialization import stable_dumps


@dataclass(slots=True)
class MetricResult:
    name: str
    value: float | int | None
    description: str
    eligible_count: int
    excluded_count: int
    numerator: float | int | None
    denominator: float | int | None
    unit: str
    direction: str
    unavailable_reason: str | None = None


@dataclass(slots=True)
class EvaluationBundle:
    metrics: list[MetricResult]
    breakdowns: dict[str, list[dict[str, object]]]


def _percentile(sorted_values: list[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("empty values")
    if len(sorted_values) == 1:
        return sorted_values[0]
    index = (len(sorted_values) - 1) * q
    lower = int(index)
    upper = min(lower + 1, len(sorted_values) - 1)
    fraction = index - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def compute_metrics(
    traces: list[TraceRecord], retrieval_k: int, excessive_steps_threshold: int
) -> EvaluationBundle:
    metrics: list[MetricResult] = []
    total_rows = len(traces)
    known = [t for t in traces if t.success is not None]
    failures = [t for t in known if t.success is False]
    metrics.append(
        MetricResult(
            name="total_rows",
            value=total_rows,
            description="Total rows ingested as valid traces",
            eligible_count=total_rows,
            excluded_count=0,
            numerator=total_rows,
            denominator=total_rows,
            unit="count",
            direction="higher_is_neutral",
        )
    )
    metrics.append(
        MetricResult(
            name="known_outcome_count",
            value=len(known),
            description="Traces with explicit success outcome",
            eligible_count=total_rows,
            excluded_count=total_rows - len(known),
            numerator=len(known),
            denominator=total_rows,
            unit="count",
            direction="higher_is_better",
        )
    )
    if known:
        metrics.append(
            MetricResult(
                name="failure_rate",
                value=len(failures) / len(known),
                description="failure_count / traces_with_known_outcome",
                eligible_count=len(known),
                excluded_count=total_rows - len(known),
                numerator=len(failures),
                denominator=len(known),
                unit="ratio",
                direction="lower_is_better",
            )
        )
    else:
        metrics.append(
            MetricResult(
                name="failure_rate",
                value=None,
                description="failure_count / traces_with_known_outcome",
                eligible_count=0,
                excluded_count=total_rows,
                numerator=0,
                denominator=0,
                unit="ratio",
                direction="lower_is_better",
                unavailable_reason="no known outcomes",
            )
        )

    _extend_latency_cost_metrics(metrics, traces)
    _extend_retrieval_citation_metrics(metrics, traces, retrieval_k)
    _extend_agent_metrics(metrics, traces, excessive_steps_threshold)

    return EvaluationBundle(metrics=metrics, breakdowns=_compute_breakdowns(traces, retrieval_k))


def _extend_latency_cost_metrics(metrics: list[MetricResult], traces: list[TraceRecord]) -> None:
    latency = sorted(t.latency_ms for t in traces if t.latency_ms is not None)
    if latency:
        metrics.extend(
            [
                MetricResult(
                    "latency_count",
                    len(latency),
                    "Count of known latency values",
                    len(latency),
                    0,
                    len(latency),
                    len(traces),
                    "count",
                    "higher_is_neutral",
                ),
                MetricResult(
                    "latency_average_ms",
                    mean(latency),
                    "Average latency",
                    len(latency),
                    len(traces) - len(latency),
                    sum(latency),
                    len(latency),
                    "ms",
                    "lower_is_better",
                ),
                MetricResult(
                    "latency_min_ms",
                    latency[0],
                    "Minimum latency",
                    len(latency),
                    len(traces) - len(latency),
                    None,
                    None,
                    "ms",
                    "lower_is_better",
                ),
                MetricResult(
                    "latency_max_ms",
                    latency[-1],
                    "Maximum latency",
                    len(latency),
                    len(traces) - len(latency),
                    None,
                    None,
                    "ms",
                    "lower_is_better",
                ),
                MetricResult(
                    "latency_p50_ms",
                    _percentile(latency, 0.50),
                    "50th percentile latency",
                    len(latency),
                    len(traces) - len(latency),
                    None,
                    None,
                    "ms",
                    "lower_is_better",
                ),
                MetricResult(
                    "latency_p95_ms",
                    _percentile(latency, 0.95),
                    "95th percentile latency",
                    len(latency),
                    len(traces) - len(latency),
                    None,
                    None,
                    "ms",
                    "lower_is_better",
                ),
            ]
        )

    cost = sorted(t.cost_usd for t in traces if t.cost_usd is not None)
    if cost:
        successful_with_cost = [
            t.cost_usd for t in traces if t.success is True and t.cost_usd is not None
        ]
        cps: float | None
        cps_reason: str | None = None
        if successful_with_cost:
            cps = sum(successful_with_cost) / len(successful_with_cost)
        else:
            cps = None
            cps_reason = "no successful traces with known cost"
        metrics.extend(
            [
                MetricResult(
                    "cost_count",
                    len(cost),
                    "Count of known cost values",
                    len(cost),
                    len(traces) - len(cost),
                    len(cost),
                    len(traces),
                    "count",
                    "higher_is_neutral",
                ),
                MetricResult(
                    "cost_total_usd",
                    sum(cost),
                    "Total known cost",
                    len(cost),
                    len(traces) - len(cost),
                    sum(cost),
                    len(cost),
                    "USD",
                    "lower_is_better",
                ),
                MetricResult(
                    "cost_average_usd",
                    mean(cost),
                    "Average known cost",
                    len(cost),
                    len(traces) - len(cost),
                    sum(cost),
                    len(cost),
                    "USD",
                    "lower_is_better",
                ),
                MetricResult(
                    "cost_min_usd",
                    cost[0],
                    "Minimum known cost",
                    len(cost),
                    len(traces) - len(cost),
                    None,
                    None,
                    "USD",
                    "lower_is_better",
                ),
                MetricResult(
                    "cost_max_usd",
                    cost[-1],
                    "Maximum known cost",
                    len(cost),
                    len(traces) - len(cost),
                    None,
                    None,
                    "USD",
                    "lower_is_better",
                ),
                MetricResult(
                    "cost_per_successful_trace_usd",
                    cps,
                    "Known cost per successful trace",
                    len(successful_with_cost),
                    len(traces) - len(successful_with_cost),
                    sum(successful_with_cost) if successful_with_cost else None,
                    len(successful_with_cost),
                    "USD",
                    "lower_is_better",
                    cps_reason,
                ),
            ]
        )


def _extend_retrieval_citation_metrics(
    metrics: list[MetricResult], traces: list[TraceRecord], retrieval_k: int
) -> None:
    eligible = [t for t in traces if t.expected_sources]
    recall_values: list[float] = []
    for trace in eligible:
        expected = {source.strip() for source in (trace.expected_sources or []) if source.strip()}
        if not expected:
            continue
        top_k = []
        for item in trace.retrieved_sources or []:
            trimmed = item.strip()
            if trimmed and trimmed not in top_k:
                top_k.append(trimmed)
            if len(top_k) >= retrieval_k:
                break
        found = len(expected.intersection(top_k))
        recall_values.append(found / len(expected))
    if recall_values:
        metrics.append(
            MetricResult(
                name="retrieval_recall_at_k",
                value=mean(recall_values),
                description="Average recall@k across traces with expected sources",
                eligible_count=len(recall_values),
                excluded_count=len(traces) - len(recall_values),
                numerator=sum(recall_values),
                denominator=len(recall_values),
                unit="ratio",
                direction="higher_is_better",
            )
        )
    else:
        metrics.append(
            MetricResult(
                name="retrieval_recall_at_k",
                value=None,
                description="Average recall@k across traces with expected sources",
                eligible_count=0,
                excluded_count=len(traces),
                numerator=0,
                denominator=0,
                unit="ratio",
                direction="higher_is_better",
                unavailable_reason="no eligible traces",
            )
        )

    nonempty_answer = [trace for trace in traces if trace.answer and trace.answer.strip()]
    with_citation = [
        trace for trace in nonempty_answer if any(c.strip() for c in (trace.citations or []))
    ]
    if nonempty_answer:
        metrics.append(
            MetricResult(
                name="citation_presence_rate",
                value=len(with_citation) / len(nonempty_answer),
                description="traces with nonempty answer and at least one citation / traces with nonempty answer",
                eligible_count=len(nonempty_answer),
                excluded_count=len(traces) - len(nonempty_answer),
                numerator=len(with_citation),
                denominator=len(nonempty_answer),
                unit="ratio",
                direction="higher_is_better",
            )
        )


def _extend_agent_metrics(
    metrics: list[MetricResult], traces: list[TraceRecord], excessive_steps_threshold: int
) -> None:
    agent_traces = [trace for trace in traces if trace.agent_steps]
    step_counts = [len(trace.agent_steps or []) for trace in agent_traces]
    tool_steps = [
        step for trace in agent_traces for step in (trace.agent_steps or []) if step.tool_name
    ]
    known_tool = [step for step in tool_steps if step.success is not None]
    success_tool = [step for step in known_tool if step.success is True]
    failed_tool = [step for step in known_tool if step.success is False]
    unknown_tool = [step for step in tool_steps if step.success is None]
    repeated_patterns = 0
    for trace in agent_traces:
        calls = Counter(
            stable_dumps(
                {"tool": (step.tool_name or "").strip().lower(), "args": step.tool_arguments or {}}
            )
            for step in (trace.agent_steps or [])
            if step.tool_name
        )
        repeated_patterns += sum(1 for count in calls.values() if count > 1)

    metrics.extend(
        [
            MetricResult(
                "agent_trace_count",
                len(agent_traces),
                "Traces with agent steps",
                len(traces),
                0,
                len(agent_traces),
                len(traces),
                "count",
                "higher_is_neutral",
            ),
            MetricResult(
                "agent_average_steps",
                mean(step_counts) if step_counts else 0.0,
                "Average steps for traces with agent steps",
                len(step_counts),
                len(traces) - len(step_counts),
                sum(step_counts),
                len(step_counts) if step_counts else 1,
                "count",
                "lower_is_better",
            ),
            MetricResult(
                "agent_max_steps",
                max(step_counts) if step_counts else 0,
                "Maximum agent steps",
                len(step_counts),
                len(traces) - len(step_counts),
                None,
                None,
                "count",
                "lower_is_better",
            ),
            MetricResult(
                "tool_call_count",
                len(tool_steps),
                "Tool call steps",
                len(tool_steps),
                0,
                len(tool_steps),
                len(tool_steps),
                "count",
                "higher_is_neutral",
            ),
            MetricResult(
                "tool_success_count",
                len(success_tool),
                "Successful tool calls with explicit outcomes",
                len(known_tool),
                len(tool_steps) - len(known_tool),
                len(success_tool),
                len(known_tool),
                "count",
                "higher_is_better",
            ),
            MetricResult(
                "tool_failure_count",
                len(failed_tool),
                "Failed tool calls with explicit outcomes",
                len(known_tool),
                len(tool_steps) - len(known_tool),
                len(failed_tool),
                len(known_tool),
                "count",
                "lower_is_better",
            ),
            MetricResult(
                "tool_unknown_outcome_count",
                len(unknown_tool),
                "Tool calls with unknown outcome",
                len(tool_steps),
                0,
                len(unknown_tool),
                len(tool_steps),
                "count",
                "lower_is_better",
            ),
            MetricResult(
                "tool_success_rate",
                len(success_tool) / len(known_tool) if known_tool else None,
                "Successful/known tool outcomes",
                len(known_tool),
                len(tool_steps) - len(known_tool),
                len(success_tool),
                len(known_tool),
                "ratio",
                "higher_is_better",
                None if known_tool else "no known tool outcomes",
            ),
            MetricResult(
                "traces_with_tool_errors",
                len(
                    [
                        t
                        for t in agent_traces
                        if any(step.success is False for step in (t.agent_steps or []))
                    ]
                ),
                "Agent traces containing failed tool steps",
                len(agent_traces),
                0,
                None,
                None,
                "count",
                "lower_is_better",
            ),
            MetricResult(
                "repeated_tool_call_patterns",
                repeated_patterns,
                "Count of repeated normalized tool+argument call patterns",
                len(agent_traces),
                0,
                None,
                None,
                "count",
                "lower_is_better",
            ),
            MetricResult(
                "excessive_step_trace_count",
                len([count for count in step_counts if count > excessive_steps_threshold]),
                "Traces above configured step threshold",
                len(agent_traces),
                0,
                None,
                None,
                "count",
                "lower_is_better",
            ),
        ]
    )


def _compute_breakdowns(
    traces: list[TraceRecord], retrieval_k: int
) -> dict[str, list[dict[str, object]]]:
    fields: dict[str, Callable[[TraceRecord], str | None]] = {
        "project": lambda trace: trace.project,
        "version": lambda trace: trace.version,
        "model": lambda trace: trace.model,
        "prompt_version": lambda trace: trace.prompt_version,
        "retriever_version": lambda trace: trace.retriever_version,
        "failure_type": lambda trace: trace.failure_type,
    }
    result: dict[str, list[dict[str, object]]] = {}
    for field, accessor in fields.items():
        groups: dict[str, list[TraceRecord]] = defaultdict(list)
        for trace in traces:
            value = accessor(trace) or "__unknown__"
            groups[str(value)].append(trace)
        rows: list[dict[str, object]] = []
        for key in sorted(groups):
            bucket = groups[key]
            known = [trace for trace in bucket if trace.success is not None]
            failures = [trace for trace in known if trace.success is False]
            recall_values = []
            for trace in bucket:
                expected = {s.strip() for s in (trace.expected_sources or []) if s.strip()}
                if not expected:
                    continue
                top_k = []
                for source in trace.retrieved_sources or []:
                    s = source.strip()
                    if s and s not in top_k:
                        top_k.append(s)
                    if len(top_k) >= retrieval_k:
                        break
                recall_values.append(len(expected.intersection(top_k)) / len(expected))
            known_latency = [trace.latency_ms for trace in bucket if trace.latency_ms is not None]
            known_cost = [trace.cost_usd for trace in bucket if trace.cost_usd is not None]
            rows.append(
                {
                    "group": key,
                    "trace_count": len(bucket),
                    "known_outcomes": len(known),
                    "failure_count": len(failures),
                    "failure_rate": (len(failures) / len(known)) if known else None,
                    "average_latency_ms": mean(known_latency) if known_latency else None,
                    "average_cost_usd": mean(known_cost) if known_cost else None,
                    "recall_at_k": mean(recall_values) if recall_values else None,
                }
            )
        result[field] = rows
    return result


def metric_dict(metrics: Iterable[MetricResult]) -> dict[str, object]:
    return {
        metric.name: {
            "value": metric.value,
            "description": metric.description,
            "eligible_count": metric.eligible_count,
            "excluded_count": metric.excluded_count,
            "numerator": metric.numerator,
            "denominator": metric.denominator,
            "unit": metric.unit,
            "direction": metric.direction,
            "unavailable_reason": metric.unavailable_reason,
        }
        for metric in metrics
    }
