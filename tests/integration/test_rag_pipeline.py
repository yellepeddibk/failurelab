"""The pipeline must emit valid, deterministic, FailureLab-analyzable traces.

No test here contacts a model. The scripted generator stands in for one, so the
suite stays offline and free.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rag_pipeline.chunking import chunk_corpus, load_corpus
from rag_pipeline.generation import ScriptedGenerator, build_script
from rag_pipeline.pipeline import FixedClock, RealClock, run_pipeline, write_traces
from rag_pipeline.questions import load_questions
from rag_pipeline.retrieval import build_retrievers

import failurelab as fl
from failurelab.models.trace import TraceRecord

EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "rag_pipeline"

# Seeded so that every outcome the evaluator can classify actually occurs.
OVERRIDES = {
    "q001": "cite_none",
    "q002": "cite_unretrieved",
    "q003": "empty",
    "q004": "abstain",
    "q017": "cite_partial",
    "q025": "cite_wrong",
    "q033": "fabricate",
}


def _fixtures():
    chunks = chunk_corpus(load_corpus(EXAMPLE_DIR / "corpus"))
    questions = load_questions(EXAMPLE_DIR / "questions.json")
    return chunks, questions


def _run(retriever_name: str = "bm25-v1", include_context: bool = False):
    chunks, questions = _fixtures()
    retriever = build_retrievers(chunks)[retriever_name]
    generator = ScriptedGenerator(script=build_script(questions, OVERRIDES))
    return run_pipeline(
        questions=questions,
        retriever=retriever,
        generator=generator,
        clock=FixedClock(),
        run_id=retriever_name,
        include_context=include_context,
    )


def test_one_trace_per_question_in_file_order() -> None:
    _, questions = _fixtures()
    traces = _run()
    assert len(traces) == len(questions)
    assert [t.metadata["question_id"] for t in traces if t.metadata] == [q.id for q in questions]


def test_every_trace_is_a_valid_trace_record() -> None:
    for trace in _run():
        assert isinstance(trace, TraceRecord)
        TraceRecord.model_validate(json.loads(trace.to_stable_json()))


def test_run_is_deterministic() -> None:
    first = [t.to_stable_json() for t in _run()]
    second = [t.to_stable_json() for t in _run()]
    assert first == second


def test_retrieved_context_is_excluded_by_default() -> None:
    for trace in _run():
        assert trace.retrieved_context is None
    with_context = _run(include_context=True)
    assert any(trace.retrieved_context for trace in with_context)


def test_citations_are_preserved_even_when_invalid() -> None:
    """A hallucinated citation must survive into the trace to be diagnosable."""
    traces = {t.metadata["question_id"]: t for t in _run() if t.metadata}
    invalid = traces["q002"]
    assert invalid.failure_type == "invalid_citation"
    assert invalid.citations is not None
    assert not set(invalid.citations) <= set(invalid.retrieved_sources or [])


def test_seeded_outcomes_appear_as_expected() -> None:
    traces = {t.metadata["question_id"]: t for t in _run() if t.metadata}
    assert traces["q001"].failure_type == "grounding_failure"
    assert traces["q003"].failure_type == "empty_answer"
    assert traces["q004"].failure_type == "unwarranted_refusal"
    assert traces["q017"].failure_type == "incomplete_citation"
    assert traces["q025"].failure_type == "wrong_source"
    assert traces["q033"].failure_type == "fabricated_answer"


def test_natural_retrieval_misses_are_recorded() -> None:
    """These come from real BM25 behavior, not from seeding."""
    traces = {t.metadata["question_id"]: t for t in _run() if t.metadata}
    assert traces["q006"].failure_type == "retrieval_miss"
    assert traces["q021"].failure_type == "retrieval_miss"


def test_successful_traces_carry_no_failure_type() -> None:
    for trace in _run():
        if trace.success:
            assert trace.failure_type is None


def test_fixed_clock_produces_stable_timestamps_and_latency() -> None:
    traces = _run()
    assert all(trace.latency_ms == 100.0 for trace in traces)
    stamps = [trace.timestamp for trace in traces]
    assert stamps == sorted(stamps)
    assert len(set(stamps)) == len(stamps)


def test_real_clock_measures_rather_than_fixes_latency() -> None:
    clock = RealClock()
    assert clock.latency_ms(2_500_000) == 2.5
    assert clock.timestamp(0).tzinfo is not None


def test_traces_are_analyzable_by_failurelab() -> None:
    report = fl.analyze([json.loads(t.to_stable_json()) for t in _run()])
    assert report.data_quality.analyzable
    failure_rate = report.metric("failure_rate")
    assert failure_rate is not None and failure_rate.value is not None
    assert 0 < failure_rate.value < 1


def test_combined_runs_expose_a_retriever_version_slice() -> None:
    """A slice on retriever_version needs both runs in one analyzed set.

    Analyzing either run alone gives every trace the same retriever_version, so no
    slice can form on that field.
    """
    combined = [
        json.loads(t.to_stable_json()) for t in (*_run("bm25-v1"), *_run("bm25-title-boosted"))
    ]
    report = fl.analyze(combined)
    by_field = {slice_.name for slice_ in report.failure_slices}
    assert "retriever_version" in by_field

    elevated = [s for s in report.failure_slices if s.name == "retriever_version"]
    assert [s.value for s in elevated] == ["bm25-v1"]
    assert elevated[0].absolute_uplift is not None and elevated[0].absolute_uplift > 0


def test_single_run_cannot_form_a_retriever_version_slice() -> None:
    report = fl.analyze([json.loads(t.to_stable_json()) for t in _run("bm25-v1")])
    assert "retriever_version" not in {slice_.name for slice_ in report.failure_slices}


def test_failed_traces_produce_hypotheses_and_regression_drafts() -> None:
    traces = [json.loads(t.to_stable_json()) for t in _run()]
    report = fl.analyze(traces)
    failed = sum(1 for trace in traces if trace["success"] is False)
    assert failed > 0
    assert len(report.root_cause_hypotheses) == failed
    assert len(report.regression_tests) == failed


def test_write_traces_is_byte_stable(tmp_path: Path) -> None:
    traces = _run()
    first = write_traces(traces, tmp_path / "a.jsonl").read_bytes()
    second = write_traces(traces, tmp_path / "b.jsonl").read_bytes()
    assert first == second
    assert first.endswith(b"\n")
    assert b"\r\n" not in first


@pytest.mark.parametrize(("questions", "run_id"), [((), "r1"), (None, "  ")])
def test_invalid_pipeline_arguments_rejected(questions: object, run_id: str) -> None:
    chunks, loaded = _fixtures()
    retriever = build_retrievers(chunks)["bm25-v1"]
    generator = ScriptedGenerator(script={})
    with pytest.raises(ValueError):
        run_pipeline(
            questions=loaded if questions is None else questions,  # type: ignore[arg-type]
            retriever=retriever,
            generator=generator,
            clock=FixedClock(),
            run_id=run_id,
        )
