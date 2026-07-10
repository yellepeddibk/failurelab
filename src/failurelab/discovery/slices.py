"""Failure slice discovery."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean

from failurelab.models.trace import TraceRecord


@dataclass(slots=True)
class FailureSlice:
    name: str
    value: str
    support: int
    known_outcomes: int
    failure_count: int
    failure_rate: float | None
    global_failure_rate: float | None
    absolute_uplift: float | None
    relative_risk: float | None
    recall_delta: float | None
    latency_delta_ms: float | None
    cost_delta_usd: float | None
    evidence_trace_ids: list[str]
    caveats: list[str]
    recommended_next_analysis: str


class FailureSliceDiscoverer:
    def discover(
        self, traces: list[TraceRecord], retrieval_k: int, min_support: int, max_findings: int
    ) -> list[FailureSlice]:
        raise NotImplementedError


class CategoricalFailureSliceDiscoverer(FailureSliceDiscoverer):
    fields = ["model", "prompt_version", "retriever_version", "version", "failure_type"]

    def discover(
        self, traces: list[TraceRecord], retrieval_k: int, min_support: int, max_findings: int
    ) -> list[FailureSlice]:
        known_global = [trace for trace in traces if trace.success is not None]
        failed_global = [trace for trace in known_global if trace.success is False]
        global_failure_rate = (len(failed_global) / len(known_global)) if known_global else None

        findings: list[FailureSlice] = []
        for field in self.fields:
            values = sorted({str(getattr(trace, field) or "__unknown__") for trace in traces})
            for value in values:
                subset = [
                    trace
                    for trace in traces
                    if str(getattr(trace, field) or "__unknown__") == value
                ]
                if len(subset) < min_support:
                    continue
                known = [trace for trace in subset if trace.success is not None]
                failure = [trace for trace in known if trace.success is False]
                failure_rate = (len(failure) / len(known)) if known else None
                absolute_uplift = (
                    (failure_rate - global_failure_rate)
                    if failure_rate is not None and global_failure_rate is not None
                    else None
                )
                relative_risk = (
                    (failure_rate / global_failure_rate)
                    if failure_rate is not None and global_failure_rate not in (None, 0)
                    else None
                )
                recall_delta = _group_recall(subset, retrieval_k) - _group_recall(
                    traces, retrieval_k
                )
                latency_delta = _group_mean(subset, "latency_ms") - _group_mean(
                    traces, "latency_ms"
                )
                cost_delta = _group_mean(subset, "cost_usd") - _group_mean(traces, "cost_usd")
                findings.append(
                    FailureSlice(
                        name=field,
                        value=value,
                        support=len(subset),
                        known_outcomes=len(known),
                        failure_count=len(failure),
                        failure_rate=failure_rate,
                        global_failure_rate=global_failure_rate,
                        absolute_uplift=absolute_uplift,
                        relative_risk=relative_risk,
                        recall_delta=recall_delta if recall_delta == recall_delta else None,
                        latency_delta_ms=latency_delta if latency_delta == latency_delta else None,
                        cost_delta_usd=cost_delta if cost_delta == cost_delta else None,
                        evidence_trace_ids=[
                            trace.trace_id
                            for trace in sorted(subset, key=lambda item: item.trace_id)[:5]
                        ],
                        caveats=[
                            "No statistical significance claims.",
                            "Associative pattern only.",
                        ],
                        recommended_next_analysis=f"Compare {field}={value} against nearest alternative with same workload.",
                    )
                )
        ordered = sorted(
            findings,
            key=lambda item: (
                item.absolute_uplift if item.absolute_uplift is not None else -10.0,
                item.support,
                item.name,
                item.value,
            ),
            reverse=True,
        )
        return ordered[:max_findings]


def _group_recall(traces: list[TraceRecord], k: int) -> float:
    recalls: list[float] = []
    for trace in traces:
        expected = {s.strip() for s in (trace.expected_sources or []) if s.strip()}
        if not expected:
            continue
        top_k: list[str] = []
        for source in trace.retrieved_sources or []:
            s = source.strip()
            if s and s not in top_k:
                top_k.append(s)
            if len(top_k) >= k:
                break
        recalls.append(len(expected.intersection(top_k)) / len(expected))
    return mean(recalls) if recalls else 0.0


def _group_mean(traces: list[TraceRecord], field: str) -> float:
    values = [getattr(trace, field) for trace in traces if getattr(trace, field) is not None]
    return mean(values) if values else 0.0
