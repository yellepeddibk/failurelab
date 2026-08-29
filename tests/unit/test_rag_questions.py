"""The question set is ground truth, so its structure is enforced."""

from __future__ import annotations

from pathlib import Path

import pytest
from rag_pipeline.chunking import chunk_corpus, load_corpus
from rag_pipeline.questions import CATEGORIES, load_questions, parse_questions

EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "rag_pipeline"


def _questions() -> tuple:
    return load_questions(EXAMPLE_DIR / "questions.json")


def test_every_gold_chunk_exists_in_the_chunked_corpus() -> None:
    known = {chunk.chunk_id for chunk in chunk_corpus(load_corpus(EXAMPLE_DIR / "corpus"))}
    for question in _questions():
        for chunk_id in question.gold_chunks:
            assert chunk_id in known, f"{question.id} references unknown chunk {chunk_id}"


def test_every_category_is_represented() -> None:
    present = {question.category for question in _questions()}
    assert present == set(CATEGORIES)


def test_unanswerable_questions_have_no_gold_evidence() -> None:
    for question in _questions():
        assert bool(question.gold_chunks) == question.answerable


def test_multi_source_questions_span_more_than_one_chunk() -> None:
    chunks = {c.chunk_id: c.text for c in chunk_corpus(load_corpus(EXAMPLE_DIR / "corpus"))}
    multi = [q for q in _questions() if q.category == "multi_source"]
    assert multi
    for question in multi:
        assert len(question.gold_chunks) >= 2
        assert len({chunks[c] for c in question.gold_chunks}) == len(question.gold_chunks)


def test_question_ids_are_unique() -> None:
    ids = [question.id for question in _questions()]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"questions": []},
        {
            "questions": [
                {"id": "", "category": "single_source", "question": "q", "gold_chunks": ["a"]}
            ]
        },
        {"questions": [{"id": "a", "category": "nope", "question": "q", "gold_chunks": ["a"]}]},
        {
            "questions": [
                {"id": "a", "category": "single_source", "question": "", "gold_chunks": ["a"]}
            ]
        },
        {
            "questions": [
                {"id": "a", "category": "single_source", "question": "q", "gold_chunks": []}
            ]
        },
        {
            "questions": [
                {"id": "a", "category": "unanswerable", "question": "q", "gold_chunks": ["a"]}
            ]
        },
        {
            "questions": [
                {"id": "a", "category": "multi_source", "question": "q", "gold_chunks": ["a"]}
            ]
        },
        {
            "questions": [
                {"id": "a", "category": "single_source", "question": "q", "gold_chunks": ["a", "a"]}
            ]
        },
        {
            "questions": [
                {"id": "a", "category": "single_source", "question": "q", "gold_chunks": ["a"]},
                {"id": "a", "category": "single_source", "question": "q", "gold_chunks": ["b"]},
            ]
        },
    ],
)
def test_invalid_question_payloads_rejected(payload: dict) -> None:
    with pytest.raises(ValueError):
        parse_questions(payload)
