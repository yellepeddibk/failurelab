"""Draft regression test generation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict

from failurelab.discovery.slices import FailureSlice
from failurelab.models.trace import SCHEMA_VERSION, TraceRecord


class RegressionCase(BaseModel):
    schema_version: str = SCHEMA_VERSION
    id: str
    title: str
    review_status: str = "draft"
    source_trace_id: str
    source_failure_type: str | None = None
    input: dict[str, Any]
    expected_success: bool = True
    expected_sources: list[str] | None = None
    required_tool_names: list[str] | None = None
    latency_threshold_ms: float | None = None
    cost_threshold_usd: float | None = None
    tags: list[str]
    evidence: list[str]
    metadata: dict[str, Any]

    model_config = ConfigDict(extra="forbid")


@dataclass(slots=True)
class RegressionBundle:
    tests: list[RegressionCase]


def generate_regression_tests(
    traces: list[TraceRecord],
    slices: list[FailureSlice],
    include_thresholds: bool,
) -> RegressionBundle:
    _ = slices
    cases: dict[str, RegressionCase] = {}
    for trace in traces:
        if trace.success is not False:
            continue
        query = (trace.query or "").strip()
        if not query:
            continue
        digest = hashlib.sha256(trace.trace_id.encode("utf-8")).hexdigest()[:10]
        identifier = f"reg-{digest}"
        tool_names = (
            sorted({step.tool_name for step in (trace.agent_steps or []) if step.tool_name}) or None
        )
        cases[identifier] = RegressionCase(
            id=identifier,
            title=f"Regression for trace {trace.trace_id}",
            source_trace_id=trace.trace_id,
            source_failure_type=trace.failure_type,
            input={"query": query},
            expected_sources=trace.expected_sources,
            required_tool_names=tool_names,
            latency_threshold_ms=trace.latency_ms if include_thresholds else None,
            cost_threshold_usd=trace.cost_usd if include_thresholds else None,
            tags=sorted({"trace", trace.failure_type or "unknown"}),
            evidence=[
                f"source_trace_id={trace.trace_id}",
                "generated from deterministic failed trace rule",
            ],
            metadata={"project": trace.project, "version": trace.version},
        )
    return RegressionBundle(tests=[cases[key] for key in sorted(cases)])
