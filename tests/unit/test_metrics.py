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
