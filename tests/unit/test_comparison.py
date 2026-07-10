from __future__ import annotations

from failurelab.comparison.service import compare_traces
from failurelab.config.settings import FailureLabConfig
from failurelab.models.trace import TraceRecord


def _trace(trace_id: str, success: bool, latency: float, cost: float) -> TraceRecord:
    return TraceRecord.model_validate(
        {
            "schema_version": "0.1",
            "trace_id": trace_id,
            "timestamp": "2026-01-01T00:00:00+00:00",
            "success": success,
            "latency_ms": latency,
            "cost_usd": cost,
            "expected_sources": ["a"],
            "retrieved_sources": ["a" if success else "x"],
        }
    )


def test_compare_gate_not_configured_and_deltas_present() -> None:
    cfg = FailureLabConfig()
    baseline = [_trace("a", True, 10.0, 0.1), _trace("b", False, 20.0, 0.2)]
    candidate = [_trace("a", False, 30.0, 0.3), _trace("c", False, 40.0, 0.4)]
    result = compare_traces(baseline, candidate, cfg)
    assert result.gate_status == "not_configured"
    assert result.gate_passed is None
    assert result.summary["unmatched_candidate_ids"] == ["c"]
    full_deltas = result.summary["full_dataset_deltas"]
    assert isinstance(full_deltas, dict)
    assert full_deltas["failure_rate"]["interpretation"] == "regression"


def test_compare_gate_threshold_failure() -> None:
    cfg = FailureLabConfig.model_validate(
        {"gate": {"max_failure_rate_increase": 0.0}, "comparison": {"scope": "all_valid_traces"}}
    )
    baseline = [_trace("a", True, 10.0, 0.1)]
    candidate = [_trace("a", False, 10.0, 0.1)]
    result = compare_traces(baseline, candidate, cfg)
    assert result.gate_status == "failed"
    assert result.gate_passed is False
    assert result.violations[0].metric == "failure_rate"
