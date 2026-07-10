from __future__ import annotations

from pathlib import Path

from failurelab.agents.skills import (
    CalculateMetricsSkill,
    ClassifyRootCauseSkill,
    CompareVersionsSkill,
    DeterministicInvestigationAgent,
    DiscoverFailureSlicesSkill,
    EstimateCostSkill,
    GenerateRegressionTestsSkill,
    InspectAgentStepsSkill,
    InvestigationRequest,
    SearchTracesSkill,
    SkillInvocation,
    SkillRegistry,
)
from failurelab.config.settings import FailureLabConfig
from failurelab.ingestion.jsonl import ingest_jsonl
from failurelab.services.pipeline import analyze, compare


def _load(path: str) -> list:
    return ingest_jsonl(Path(path), strict=True).traces


def test_pipeline_analyze_and_compare(tmp_path: Path) -> None:
    config = FailureLabConfig()
    output = tmp_path / "analyze"
    result = analyze(
        Path("examples/rag_traces.jsonl"),
        output,
        config,
        strict=False,
        overwrite=True,
    )
    assert (output / "metrics.json").exists()
    assert (output / "report.md").exists()
    assert result.metrics is not None

    cmp_out = tmp_path / "compare"
    cmp_result = compare(
        Path("examples/baseline_traces.jsonl"),
        Path("examples/candidate_traces.jsonl"),
        cmp_out,
        config,
        overwrite=True,
    )
    assert (cmp_out / "comparison.json").exists()
    assert cmp_result.comparison is not None


def test_skills_and_agent() -> None:
    config = FailureLabConfig()
    rag = _load("examples/rag_traces.jsonl")
    baseline = _load("examples/baseline_traces.jsonl")
    candidate = _load("examples/candidate_traces.jsonl")

    registry = SkillRegistry()
    registry.register(SearchTracesSkill(rag))
    registry.register(CalculateMetricsSkill(rag, config))
    registry.register(CompareVersionsSkill(baseline, candidate, config))
    registry.register(DiscoverFailureSlicesSkill(rag, config))
    registry.register(InspectAgentStepsSkill(rag))
    registry.register(ClassifyRootCauseSkill(rag, config))
    registry.register(GenerateRegressionTestsSkill(rag, config))
    registry.register(EstimateCostSkill(rag))

    request = InvestigationRequest(
        objective="investigate reliability",
        invocations=[
            SkillInvocation("search_traces", {"project": "kb"}),
            SkillInvocation("calculate_metrics", {}),
            SkillInvocation("discover_failure_slices", {}),
            SkillInvocation("classify_root_cause", {}),
            SkillInvocation("generate_regression_tests", {}),
            SkillInvocation("estimate_cost", {}),
        ],
    )
    result = DeterministicInvestigationAgent(registry).run(request)
    assert result.evidence
    assert result.plan.steps[0] == "search_traces"
