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
    cases: dict[str, RegressionCase] = {}
    for trace in traces:
        if trace.success is not False:
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
            input={"query": trace.query} if trace.query else {},
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
    for finding in slices:
        if not finding.evidence_trace_ids:
            continue
        source_id = finding.evidence_trace_ids[0]
        digest = hashlib.sha256(
            f"slice:{finding.name}:{finding.value}:{source_id}".encode()
        ).hexdigest()[:10]
        identifier = f"slice-{digest}"
        if identifier in cases:
            continue
        cases[identifier] = RegressionCase(
            id=identifier,
            title=f"Slice regression for {finding.name}={finding.value}",
            source_trace_id=source_id,
            source_failure_type=finding.name,
            input={},
            expected_sources=None,
            required_tool_names=None,
            tags=["slice", finding.name, finding.value],
            evidence=[f"support={finding.support}", f"absolute_uplift={finding.absolute_uplift}"],
            metadata={"slice_name": finding.name, "slice_value": finding.value},
        )
    return RegressionBundle(tests=[cases[key] for key in sorted(cases)])
