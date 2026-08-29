"""The committed datasets must stay reproducible and honestly configured."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rag_pipeline.datasets import (
    DATASETS,
    SEEDED_FAILURES,
    analysis_config,
    example_dir,
    generate_all,
    load_all_questions,
    partition,
)
from rag_pipeline.evaluate import FAILURE_TYPES
from rag_pipeline.retrieval import DEFAULT_K

import failurelab as fl

DATA_DIR = example_dir() / "data"


def _rows(filename: str) -> list[dict]:
    text = (DATA_DIR / filename).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def test_analysis_config_k_matches_the_pipeline_k() -> None:
    """A mismatch silently measures recall at a different k than was retrieved.

    FailureLab truncates retrieved_sources to the configured retrieval_k. With the
    default of 3 against a pipeline retrieving 5, both retrievers scored an
    identical 0.90625 and the difference between them was invisible.
    """
    assert analysis_config().evaluation.retrieval_k == DEFAULT_K


def test_committed_datasets_are_reproducible(tmp_path: Path) -> None:
    """Regenerating must reproduce the committed bytes exactly."""
    generate_all(tmp_path)
    for spec in DATASETS:
        committed = (DATA_DIR / spec.filename).read_bytes()
        regenerated = (tmp_path / spec.filename).read_bytes()
        assert regenerated == committed, f"{spec.filename} drifted from the pipeline"


def test_every_committed_dataset_validates() -> None:
    for spec in DATASETS:
        result = fl.validate(DATA_DIR / spec.filename)
        assert result.is_valid
        assert result.data_quality.invalid_count == 0


def test_partitions_have_the_expected_sizes() -> None:
    questions = load_all_questions()
    answerable = partition(questions, answerable=True)
    abstention = partition(questions, answerable=False)
    assert len(answerable) + len(abstention) == len(questions)
    assert answerable and abstention
    assert all(question.gold_chunks for question in answerable)
    assert not any(question.gold_chunks for question in abstention)


def test_seeded_failures_reference_real_questions() -> None:
    known = {question.id for question in load_all_questions()}
    assert set(SEEDED_FAILURES) <= known


def test_abstention_dataset_reports_recall_as_unavailable() -> None:
    """No question has expected sources, so recall has no eligible observations."""
    report = fl.analyze(DATA_DIR / "rag_abstention.jsonl", config=analysis_config())
    recall = report.metric("retrieval_recall_at_k")
    assert recall is not None
    assert recall.value is None
    assert recall.eligible_count == 0
    assert recall.excluded_count > 0
    assert recall.unavailable_reason


def test_title_boosting_improves_recall_on_the_frozen_question_set() -> None:
    """Measured, not assumed. The question set was frozen before either run."""
    config = analysis_config()
    v1 = fl.analyze(DATA_DIR / "rag_v1.jsonl", config=config).metric("retrieval_recall_at_k")
    v2 = fl.analyze(DATA_DIR / "rag_v2.jsonl", config=config).metric("retrieval_recall_at_k")
    assert v1 is not None and v2 is not None
    assert v1.value is not None and v2.value is not None
    assert v2.value > v1.value


def test_combined_datasets_expose_the_retriever_version_slice() -> None:
    combined = [*_rows("rag_v1.jsonl"), *_rows("rag_v2.jsonl")]
    report = fl.analyze(combined, config=analysis_config())
    slices = [s for s in report.failure_slices if s.name == "retriever_version"]
    assert slices
    assert slices[0].value == "bm25-v1"


def test_every_failure_type_occurs_across_the_datasets() -> None:
    observed: set[str] = set()
    for spec in DATASETS:
        for row in _rows(spec.filename):
            if row.get("failure_type"):
                observed.add(row["failure_type"])
    assert observed == set(FAILURE_TYPES)


def test_no_dataset_leaks_retrieved_context() -> None:
    for spec in DATASETS:
        for row in _rows(spec.filename):
            assert "retrieved_context" not in row


@pytest.mark.parametrize("spec", DATASETS, ids=lambda spec: spec.filename)
def test_dataset_files_end_with_a_newline_and_use_lf(spec: object) -> None:
    raw = (DATA_DIR / spec.filename).read_bytes()  # type: ignore[attr-defined]
    assert raw.endswith(b"\n")
    assert b"\r\n" not in raw
