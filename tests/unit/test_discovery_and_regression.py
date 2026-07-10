from __future__ import annotations

from pathlib import Path

from failurelab.config.settings import FailureLabConfig
from failurelab.discovery.slices import CategoricalFailureSliceDiscoverer
from failurelab.ingestion.jsonl import ingest_jsonl
from failurelab.regression.generator import generate_regression_tests
from failurelab.root_cause.analyzer import DeterministicRootCauseAnalyzer


def test_discovery_root_cause_and_regression() -> None:
    traces = ingest_jsonl(Path("examples/rag_traces.jsonl"), strict=True).traces
    config = FailureLabConfig()
    slices = CategoricalFailureSliceDiscoverer().discover(
        traces,
        config.evaluation.retrieval_k,
        config.slices.minimum_support,
        config.slices.maximum_findings,
    )
    assert slices

    hypotheses = DeterministicRootCauseAnalyzer().analyze(
        traces,
        config.evaluation.retrieval_k,
        config.root_cause.repeated_tool_threshold,
        config.evaluation.excessive_steps_threshold,
    )
    assert len(hypotheses) == len(traces)

    regression = generate_regression_tests(traces, slices, include_thresholds=False)
    assert regression.tests
