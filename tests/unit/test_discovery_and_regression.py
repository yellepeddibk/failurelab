from __future__ import annotations

from pathlib import Path

from failurelab.config.settings import FailureLabConfig
from failurelab.discovery.slices import CategoricalFailureSliceDiscoverer
from failurelab.ingestion.jsonl import ingest_jsonl
from failurelab.models.trace import TraceRecord
from failurelab.regression.generator import generate_regression_tests
from failurelab.root_cause.analyzer import DeterministicRootCauseAnalyzer


def _trace(trace_id: str, **kwargs: object) -> TraceRecord:
    payload: dict[str, object] = {
        "schema_version": "0.1",
        "trace_id": trace_id,
        "timestamp": "2026-01-01T00:00:00+00:00",
    }
    payload.update(kwargs)
    return TraceRecord.model_validate(payload)


def test_discovery_emits_only_elevated_slices() -> None:
    traces = [
        _trace("a", model="m1", success=False, query="q"),
        _trace("b", model="m1", success=False, query="q"),
        _trace("c", model="m2", success=True, query="q"),
        _trace("d", model="m2", success=True, query="q"),
    ]
    slices = CategoricalFailureSliceDiscoverer().discover(
        traces,
        retrieval_k=1,
        min_support=2,
        max_findings=10,
    )
    assert [(slice_item.name, slice_item.value) for slice_item in slices] == [("model", "m1")]
    assert slices[0].absolute_uplift is not None and slices[0].absolute_uplift > 0


def test_regression_cases_require_failed_trace_with_input() -> None:
    traces = [
        _trace("f1", success=False, query="hello", failure_type="retrieval"),
        _trace("f2", success=False, query=""),
        _trace("s1", success=True, query="keep"),
    ]
    bundle = generate_regression_tests(traces, [], include_thresholds=False)
    assert [case.source_trace_id for case in bundle.tests] == ["f1"]
    assert bundle.tests[0].input == {"query": "hello"}


def test_mixed_example_success_only_has_no_hypotheses_or_regression() -> None:
    traces = ingest_jsonl(Path("examples/rag_traces.jsonl"), strict=True).traces
    config = FailureLabConfig()
    slices = CategoricalFailureSliceDiscoverer().discover(
        traces,
        config.evaluation.retrieval_k,
        config.slices.minimum_support,
        config.slices.maximum_findings,
    )
    assert slices == []

    hypotheses = DeterministicRootCauseAnalyzer().analyze(
        traces,
        config.evaluation.retrieval_k,
        config.root_cause.repeated_tool_threshold,
        config.evaluation.excessive_steps_threshold,
    )
    assert all(hypothesis.source_trace_id for hypothesis in hypotheses)
    assert all(hypothesis.hypothesis for hypothesis in hypotheses)

    regression = generate_regression_tests(traces, slices, include_thresholds=False)
    assert all(case.input for case in regression.tests)
