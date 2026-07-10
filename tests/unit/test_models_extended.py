from __future__ import annotations

import math

import pytest
from pydantic import ValidationError

from failurelab.models.trace import AgentStep, ErrorDetail, TraceRecord


def test_error_detail_validation() -> None:
    detail = ErrorDetail.model_validate(
        {
            "category": "tool",
            "code": "x",
            "message": "bad",
            "retryable": False,
            "metadata": {"a": 1},
        }
    )
    assert detail.category == "tool"
    with pytest.raises(ValidationError):
        ErrorDetail.model_validate({"category": " ", "code": "x", "message": "m"})


def test_agent_step_latency_validation() -> None:
    with pytest.raises(ValidationError):
        AgentStep.model_validate(
            {"step_id": "s", "sequence": 0, "step_type": "tool", "latency_ms": -1}
        )
    with pytest.raises(ValidationError):
        AgentStep.model_validate(
            {
                "step_id": "s",
                "sequence": 0,
                "step_type": "tool",
                "tool_arguments": {"x": math.inf},
            }
        )


def test_trace_step_sorting_and_stable_json() -> None:
    trace = TraceRecord.model_validate(
        {
            "schema_version": "0.1",
            "trace_id": "t1",
            "timestamp": "2026-01-01T00:00:00+00:00",
            "retrieved_sources": ["a"],
            "expected_sources": ["a"],
            "citations": ["a"],
            "agent_steps": [
                {"step_id": "b", "sequence": 2, "step_type": "tool_call"},
                {"step_id": "a", "sequence": 1, "step_type": "tool_call"},
            ],
        }
    )
    assert [step.step_id for step in trace.agent_steps or []] == ["a", "b"]
    assert '"trace_id":"t1"' in trace.to_stable_json()


def test_trace_rejects_empty_source() -> None:
    with pytest.raises(ValidationError):
        TraceRecord.model_validate(
            {
                "schema_version": "0.1",
                "trace_id": "t2",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "retrieved_sources": [""],
            }
        )
