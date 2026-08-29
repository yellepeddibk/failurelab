"""The scripted generator must reproduce every classifiable outcome."""

from __future__ import annotations

import pytest
from rag_pipeline.chunking import Chunk
from rag_pipeline.generation import (
    ABSTENTION_TEXT,
    UNRETRIEVED_CHUNK_ID,
    ScriptedGenerator,
    build_script,
)
from rag_pipeline.questions import Question

CONTEXTS = (
    Chunk(chunk_id="a#0", doc_id="a", title="A", text="Gold one. Extra detail."),
    Chunk(chunk_id="a#1", doc_id="a", title="A", text="Gold two. More detail."),
    Chunk(chunk_id="b#0", doc_id="b", title="B", text="Distractor text. Not relevant."),
)
GOLD = ("a#0", "a#1")
QUESTION = "what is the answer?"


def _generator(behavior: str) -> ScriptedGenerator:
    return ScriptedGenerator(script={QUESTION: (behavior, GOLD)})


def test_cite_gold_cites_every_retrieved_gold_chunk() -> None:
    answer = _generator("cite_gold").generate(QUESTION, CONTEXTS)
    assert answer.cited_chunk_ids == GOLD
    assert answer.text
    assert answer.abstained is False


def test_cite_none_produces_text_without_citations() -> None:
    answer = _generator("cite_none").generate(QUESTION, CONTEXTS)
    assert answer.cited_chunk_ids == ()
    assert answer.text
    assert answer.abstained is False


def test_cite_partial_cites_a_strict_subset_of_gold() -> None:
    answer = _generator("cite_partial").generate(QUESTION, CONTEXTS)
    assert set(answer.cited_chunk_ids) < set(GOLD)
    assert answer.cited_chunk_ids


def test_cite_wrong_cites_a_retrieved_non_gold_chunk() -> None:
    answer = _generator("cite_wrong").generate(QUESTION, CONTEXTS)
    assert answer.cited_chunk_ids == ("b#0",)


def test_cite_unretrieved_keeps_the_hallucinated_identifier() -> None:
    answer = _generator("cite_unretrieved").generate(QUESTION, CONTEXTS)
    assert UNRETRIEVED_CHUNK_ID in answer.cited_chunk_ids
    retrieved = {chunk.chunk_id for chunk in CONTEXTS}
    assert not set(answer.cited_chunk_ids) <= retrieved


def test_empty_behavior_returns_blank_text() -> None:
    answer = _generator("empty").generate(QUESTION, CONTEXTS)
    assert answer.text == ""
    assert answer.abstained is False


def test_abstain_sets_the_structured_flag() -> None:
    answer = _generator("abstain").generate(QUESTION, CONTEXTS)
    assert answer.abstained is True
    assert answer.cited_chunk_ids == ()
    assert answer.text == ABSTENTION_TEXT


def test_fabricate_answers_substantively() -> None:
    answer = _generator("fabricate").generate(QUESTION, CONTEXTS)
    assert answer.abstained is False
    assert answer.text.strip()


def test_generation_is_deterministic() -> None:
    generator = _generator("cite_gold")
    assert generator.generate(QUESTION, CONTEXTS) == generator.generate(QUESTION, CONTEXTS)


def test_unknown_question_uses_the_default_behavior() -> None:
    answer = ScriptedGenerator(script={}).generate("unseen", CONTEXTS)
    assert answer.abstained is False


def test_unknown_behavior_rejected() -> None:
    with pytest.raises(ValueError):
        ScriptedGenerator(script={QUESTION: ("teleport", GOLD)})


def test_unknown_default_behavior_rejected() -> None:
    with pytest.raises(ValueError):
        ScriptedGenerator(script={}, default_behavior="teleport")


def _questions() -> tuple[Question, ...]:
    return (
        Question(id="q1", category="single_source", question="answerable?", gold_chunks=("a#0",)),
        Question(id="q2", category="unanswerable", question="unanswerable?", gold_chunks=()),
    )


def test_build_script_defaults_by_category() -> None:
    script = build_script(_questions(), {})
    assert script["answerable?"] == ("cite_gold", ("a#0",))
    assert script["unanswerable?"] == ("abstain", ())


def test_build_script_applies_overrides_by_question_id() -> None:
    script = build_script(_questions(), {"q1": "cite_none"})
    assert script["answerable?"][0] == "cite_none"


def test_build_script_rejects_unknown_question_ids() -> None:
    with pytest.raises(ValueError, match="unknown question ids"):
        build_script(_questions(), {"nope": "cite_none"})
