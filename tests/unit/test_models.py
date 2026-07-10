from __future__ import annotations

import pytest
from pydantic import ValidationError

from failurelab.models.trace import AgentStep, TraceRecord


def test_trace_accepts_minimal_valid() -> None:
    trace = TraceRecord.model_validate(
        {"schema_version": "0.1", "trace_id": "abc", "timestamp": "2026-01-01T00:00:00+00:00"}
    )
    assert trace.trace_id == "abc"


def test_trace_rejects_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        TraceRecord.model_validate(
            {"schema_version": "0.1", "trace_id": "abc", "timestamp": "2026-01-01T00:00:00"}
        )


def test_agent_step_rejects_negative_sequence() -> None:
    with pytest.raises(ValidationError):
        AgentStep.model_validate({"step_id": "s1", "sequence": -1, "step_type": "tool_call"})
