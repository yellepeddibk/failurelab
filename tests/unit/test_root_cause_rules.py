from __future__ import annotations

from failurelab.models.trace import TraceRecord
from failurelab.root_cause.analyzer import DeterministicRootCauseAnalyzer


def _analyze(payload: dict) -> str | None:
    trace = TraceRecord.model_validate(payload)
    findings = DeterministicRootCauseAnalyzer().analyze(
        [trace], retrieval_k=1, repeated_tool_threshold=1, excessive_steps_threshold=2
    )
    return findings[0].hypothesis if findings else None


def test_root_cause_rule_coverage() -> None:
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r1",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
                "expected_sources": ["a"],
                "retrieved_sources": ["x"],
            }
        )
        == "retrieval_failure"
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r2",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
                "expected_sources": ["a"],
                "retrieved_sources": ["x", "a"],
            }
        )
        == "ranking_failure"
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r3",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
                "answer": "answer",
                "retrieved_sources": ["a"],
                "citations": [],
            }
        )
        == "citation_missing"
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r4",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
                "agent_steps": [
                    {
                        "step_id": "s1",
                        "sequence": 0,
                        "step_type": "tool_call",
                        "tool_name": "x",
                        "success": False,
                        "error": {
                            "category": "invalid_tool_arguments",
                            "code": "bad",
                            "message": "bad",
                            "retryable": False,
                        },
                    }
                ],
            }
        )
        == "invalid_tool_arguments"
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r5",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
                "agent_steps": [
                    {
                        "step_id": "s1",
                        "sequence": 0,
                        "step_type": "tool_call",
                        "tool_name": "x",
                        "success": False,
                    }
                ],
            }
        )
        == "tool_execution_failure"
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r6",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
                "agent_steps": [
                    {"step_id": "s1", "sequence": 0, "step_type": "tool_call"},
                    {"step_id": "s2", "sequence": 1, "step_type": "tool_call"},
                    {"step_id": "s3", "sequence": 2, "step_type": "tool_call"},
                ],
            }
        )
        == "excessive_agent_steps"
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r7",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
                "agent_steps": [
                    {
                        "step_id": "s1",
                        "sequence": 0,
                        "step_type": "tool_call",
                        "tool_name": "x",
                        "tool_arguments": {"a": 1},
                    },
                    {
                        "step_id": "s2",
                        "sequence": 1,
                        "step_type": "tool_call",
                        "tool_name": "x",
                        "tool_arguments": {"a": 1},
                    },
                ],
            }
        )
        == "repeated_tool_pattern"
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r8",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
                "expected_sources": ["a"],
                "retrieved_sources": ["a"],
            }
        )
        == "possible_reasoning_failure"
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r9",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": False,
            }
        )
        == "unknown"
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r10",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": True,
            }
        )
        is None
    )
    assert (
        _analyze(
            {
                "schema_version": "0.1",
                "trace_id": "r11",
                "timestamp": "2026-01-01T00:00:00+00:00",
                "success": None,
            }
        )
        is None
    )
