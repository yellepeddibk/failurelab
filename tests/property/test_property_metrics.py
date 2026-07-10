from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from failurelab.evals.metrics import compute_metrics
from failurelab.models.trace import TraceRecord


@given(st.lists(st.booleans() | st.none(), min_size=1, max_size=20))
def test_failure_rate_bounds(values: list[bool | None]) -> None:
    traces = [
        TraceRecord.model_validate(
            {
                "schema_version": "0.1",
                "trace_id": f"t{i}",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": value,
            }
        )
        for i, value in enumerate(values)
    ]
    metric = next(
        item
        for item in compute_metrics(traces, retrieval_k=1, excessive_steps_threshold=3).metrics
        if item.name == "failure_rate"
    )
    if metric.value is not None:
        assert 0 <= metric.value <= 1
