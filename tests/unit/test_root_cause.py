from __future__ import annotations

from failurelab.models.trace import TraceRecord
from failurelab.root_cause.analyzer import DeterministicRootCauseAnalyzer


def test_retrieval_failure_rule() -> None:
    trace = TraceRecord.model_validate(
        {
            "schema_version": "0.1",
            "trace_id": "t1",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "success": False,
            "expected_sources": ["a"],
            "retrieved_sources": ["b"],
        }
    )
    result = DeterministicRootCauseAnalyzer().analyze(
        [trace], retrieval_k=1, repeated_tool_threshold=2, excessive_steps_threshold=4
    )
    assert result[0].hypothesis == "retrieval_failure"
