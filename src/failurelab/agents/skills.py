"""Typed deterministic skills and investigation agent."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol

from failurelab.comparison.service import compare_traces
from failurelab.config.settings import FailureLabConfig
from failurelab.discovery.slices import CategoricalFailureSliceDiscoverer
from failurelab.evals.metrics import compute_metrics, metric_dict
from failurelab.models.trace import TraceRecord
from failurelab.regression.generator import generate_regression_tests
from failurelab.root_cause.analyzer import DeterministicRootCauseAnalyzer


@dataclass(slots=True)
class SkillInvocation:
    name: str
    payload: dict[str, Any]


@dataclass(slots=True)
class SkillResult:
    name: str
    success: bool
    output: dict[str, Any]
    error: str | None = None


class Skill(Protocol):
    name: str

    def invoke(self, payload: dict[str, Any]) -> SkillResult: ...


class SkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(self, skill: Skill) -> None:
        self._skills[skill.name] = skill

    def get(self, name: str) -> Skill:
        if name not in self._skills:
            raise KeyError(f"unknown skill: {name}")
        return self._skills[name]


@dataclass(slots=True)
class InvestigationRequest:
    objective: str
    invocations: list[SkillInvocation]


@dataclass(slots=True)
class Evidence:
    skill_name: str
    detail: dict[str, Any]


@dataclass(slots=True)
class Hypothesis:
    summary: str
    limitations: list[str]


@dataclass(slots=True)
class InvestigationPlan:
    objective: str
    steps: list[str]


@dataclass(slots=True)
class InvestigationResult:
    objective: str
    plan: InvestigationPlan
    evidence: list[Evidence]
    hypotheses: list[Hypothesis]


class DeterministicInvestigationAgent:
    def __init__(self, registry: SkillRegistry) -> None:
        self.registry = registry

    def run(self, request: InvestigationRequest) -> InvestigationResult:
        evidence: list[Evidence] = []
        for invocation in request.invocations:
            result = self.registry.get(invocation.name).invoke(invocation.payload)
            evidence.append(
                Evidence(
                    skill_name=result.name,
                    detail=result.output | {"success": result.success, "error": result.error},
                )
            )

        return InvestigationResult(
            objective=request.objective,
            plan=InvestigationPlan(
                objective=request.objective, steps=[inv.name for inv in request.invocations]
            ),
            evidence=evidence,
            hypotheses=[
                Hypothesis(
                    summary="Findings are deterministic outputs from typed skills.",
                    limitations=["No statistical significance claims.", "No causal certainty."],
                )
            ],
        )


class SearchTracesSkill:
    name = "search_traces"

    def __init__(self, traces: list[TraceRecord]) -> None:
        self.traces = traces

    def invoke(self, payload: dict[str, Any]) -> SkillResult:
        project = str(payload.get("project", "")).strip()
        matched = (
            [trace.trace_id for trace in self.traces if (trace.project or "") == project]
            if project
            else [trace.trace_id for trace in self.traces]
        )
        return SkillResult(
            name=self.name, success=True, output={"matched_trace_ids": sorted(matched)}
        )


class CalculateMetricsSkill:
    name = "calculate_metrics"

    def __init__(self, traces: list[TraceRecord], config: FailureLabConfig) -> None:
        self.traces = traces
        self.config = config

    def invoke(self, payload: dict[str, Any]) -> SkillResult:
        _ = payload
        bundle = compute_metrics(
            self.traces,
            self.config.evaluation.retrieval_k,
            self.config.evaluation.excessive_steps_threshold,
        )
        return SkillResult(
            name=self.name, success=True, output={"metrics": metric_dict(bundle.metrics)}
        )


class CompareVersionsSkill:
    name = "compare_versions"

    def __init__(
        self, baseline: list[TraceRecord], candidate: list[TraceRecord], config: FailureLabConfig
    ) -> None:
        self.baseline = baseline
        self.candidate = candidate
        self.config = config

    def invoke(self, payload: dict[str, Any]) -> SkillResult:
        _ = payload
        result = compare_traces(self.baseline, self.candidate, self.config)
        return SkillResult(
            name=self.name,
            success=True,
            output={
                "summary": result.summary,
                "gate_status": result.gate_status,
                "gate_passed": result.gate_passed,
            },
        )


class DiscoverFailureSlicesSkill:
    name = "discover_failure_slices"

    def __init__(self, traces: list[TraceRecord], config: FailureLabConfig) -> None:
        self.traces = traces
        self.config = config
        self.discoverer = CategoricalFailureSliceDiscoverer()

    def invoke(self, payload: dict[str, Any]) -> SkillResult:
        _ = payload
        findings = self.discoverer.discover(
            self.traces,
            self.config.evaluation.retrieval_k,
            self.config.slices.minimum_support,
            self.config.slices.maximum_findings,
        )
        return SkillResult(
            name=self.name,
            success=True,
            output={"findings": [asdict(finding) for finding in findings]},
        )


class InspectAgentStepsSkill:
    name = "inspect_agent_steps"

    def __init__(self, traces: list[TraceRecord]) -> None:
        self.traces = traces

    def invoke(self, payload: dict[str, Any]) -> SkillResult:
        _ = payload
        step_count = sum(len(trace.agent_steps or []) for trace in self.traces)
        return SkillResult(name=self.name, success=True, output={"step_count": step_count})


class ClassifyRootCauseSkill:
    name = "classify_root_cause"

    def __init__(self, traces: list[TraceRecord], config: FailureLabConfig) -> None:
        self.traces = traces
        self.config = config
        self.analyzer = DeterministicRootCauseAnalyzer()

    def invoke(self, payload: dict[str, Any]) -> SkillResult:
        _ = payload
        findings = self.analyzer.analyze(
            self.traces,
            self.config.evaluation.retrieval_k,
            self.config.root_cause.repeated_tool_threshold,
            self.config.evaluation.excessive_steps_threshold,
        )
        return SkillResult(
            name=self.name,
            success=True,
            output={"hypotheses": [asdict(finding) for finding in findings]},
        )


class GenerateRegressionTestsSkill:
    name = "generate_regression_tests"

    def __init__(self, traces: list[TraceRecord], config: FailureLabConfig) -> None:
        self.traces = traces
        self.config = config
        self.discoverer = CategoricalFailureSliceDiscoverer()

    def invoke(self, payload: dict[str, Any]) -> SkillResult:
        _ = payload
        slices = self.discoverer.discover(
            self.traces,
            self.config.evaluation.retrieval_k,
            self.config.slices.minimum_support,
            self.config.slices.maximum_findings,
        )
        tests = generate_regression_tests(
            self.traces, slices, self.config.regression_tests.include_thresholds
        )
        return SkillResult(
            name=self.name,
            success=True,
            output={
                "regression_tests": [test.model_dump(exclude_none=True) for test in tests.tests]
            },
        )


class EstimateCostSkill:
    name = "estimate_cost"

    def __init__(self, traces: list[TraceRecord]) -> None:
        self.traces = traces

    def invoke(self, payload: dict[str, Any]) -> SkillResult:
        _ = payload
        known_costs = [trace.cost_usd for trace in self.traces if trace.cost_usd is not None]
        return SkillResult(
            name=self.name,
            success=True,
            output={"known_cost_total": sum(known_costs), "known_cost_count": len(known_costs)},
        )
