from __future__ import annotations

from failurelab.evals.metrics import compute_metrics
from failurelab.models.trace import TraceRecord


def _trace(
    trace_id: str,
    success: bool | None,
    expected: list[str] | None,
    retrieved: list[str] | None,
    citations: list[str] | None,
) -> TraceRecord:
    return TraceRecord.model_validate(
        {
            "schema_version": "0.1",
            "trace_id": trace_id,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "success": success,
            "expected_sources": expected,
            "retrieved_sources": retrieved,
            "citations": citations,
            "answer": "x",
            "latency_ms": 10.0,
            "cost_usd": 0.1,
        }
    )


def test_recall_metric() -> None:
    traces = [_trace("a", True, ["s1"], ["s1"], ["s1"]), _trace("b", False, ["s2"], ["x"], [])]
    bundle = compute_metrics(traces, retrieval_k=1, excessive_steps_threshold=3)
    metric = next(item for item in bundle.metrics if item.name == "retrieval_recall_at_k")
    assert metric.value == 0.5


def test_unavailable_agent_metrics_are_null() -> None:
    traces = [_trace("a", True, None, None, None)]
    bundle = compute_metrics(traces, retrieval_k=1, excessive_steps_threshold=3)
    average = next(item for item in bundle.metrics if item.name == "agent_average_steps")
    maximum = next(item for item in bundle.metrics if item.name == "agent_max_steps")
    assert average.value is None
    assert average.denominator == 0
    assert average.unavailable_reason == "no traces with agent steps"
    assert maximum.value is None
    assert maximum.unavailable_reason == "no traces with agent steps"


def test_unavailable_latency_and_cost_metrics_are_null() -> None:
    trace = TraceRecord.model_validate(
        {
            "schema_version": "0.1",
            "trace_id": "a",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "success": True,
        }
    )
    bundle = compute_metrics([trace], retrieval_k=1, excessive_steps_threshold=3)
    latency = next(item for item in bundle.metrics if item.name == "latency_average_ms")
    cost = next(item for item in bundle.metrics if item.name == "cost_average_usd")
    assert latency.value is None
    assert cost.value is None


def test_unavailable_citation_metric_uses_contract_direction() -> None:
    trace = TraceRecord.model_validate(
        {
            "schema_version": "0.1",
            "trace_id": "a",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "success": True,
            "answer": "   ",
        }
    )
    bundle = compute_metrics([trace], retrieval_k=1, excessive_steps_threshold=3)
    citation = next(item for item in bundle.metrics if item.name == "citation_presence_rate")
    assert citation.value is None
    assert citation.direction == "higher_is_better"
    assert citation.unavailable_reason == "no traces with nonempty answer"
