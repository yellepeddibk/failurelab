"""Every branch of the evaluation decision table, including its precedence."""

from __future__ import annotations

import pytest
from rag_pipeline.evaluate import FAILURE_TYPES, Evaluation, evaluate
from rag_pipeline.generation import GeneratedAnswer
from rag_pipeline.questions import Question

RETRIEVED = ("a#0", "a#1", "b#0")


def _question(gold: tuple[str, ...], category: str = "multi_source") -> Question:
    return Question(id="q1", category=category, question="q?", gold_chunks=gold)


def _answer(
    text: str = "An answer.",
    cited: tuple[str, ...] = (),
    abstained: bool = False,
) -> GeneratedAnswer:
    return GeneratedAnswer(text=text, cited_chunk_ids=cited, abstained=abstained)


# --- answerable questions ----------------------------------------------------


def test_success_requires_citing_exactly_the_gold_set() -> None:
    result = evaluate(_question(("a#0", "a#1")), RETRIEVED, _answer(cited=("a#0", "a#1")))
    assert result == Evaluation(question_id="q1", success=True, failure_type=None)


def test_citation_order_does_not_matter() -> None:
    result = evaluate(_question(("a#0", "a#1")), RETRIEVED, _answer(cited=("a#1", "a#0")))
    assert result.success is True


def test_abstaining_on_an_answerable_question_is_an_unwarranted_refusal() -> None:
    result = evaluate(_question(("a#0",)), RETRIEVED, _answer(abstained=True))
    assert result.failure_type == "unwarranted_refusal"


def test_missing_gold_from_retrieval_is_a_retrieval_miss() -> None:
    result = evaluate(_question(("z#9",)), RETRIEVED, _answer(cited=("a#0",)))
    assert result.failure_type == "retrieval_miss"


def test_blank_answer_is_an_empty_answer() -> None:
    result = evaluate(_question(("a#0",)), RETRIEVED, _answer(text="   ", cited=("a#0",)))
    assert result.failure_type == "empty_answer"


def test_no_citations_is_a_grounding_failure() -> None:
    result = evaluate(_question(("a#0",)), RETRIEVED, _answer(cited=()))
    assert result.failure_type == "grounding_failure"


def test_citing_something_never_retrieved_is_an_invalid_citation() -> None:
    result = evaluate(_question(("a#0",)), RETRIEVED, _answer(cited=("a#0", "ghost#1")))
    assert result.failure_type == "invalid_citation"


def test_citing_a_retrieved_non_gold_chunk_is_a_wrong_source() -> None:
    result = evaluate(_question(("a#0",)), RETRIEVED, _answer(cited=("a#0", "b#0")))
    assert result.failure_type == "wrong_source"


def test_citing_only_some_gold_chunks_is_an_incomplete_citation() -> None:
    result = evaluate(_question(("a#0", "a#1")), RETRIEVED, _answer(cited=("a#0",)))
    assert result.failure_type == "incomplete_citation"


def test_wrong_source_is_distinct_from_incomplete_citation() -> None:
    """The two used to be conflated; they name genuinely different mistakes."""
    question = _question(("a#0", "a#1"))
    wrong = evaluate(question, RETRIEVED, _answer(cited=("a#0", "a#1", "b#0")))
    incomplete = evaluate(question, RETRIEVED, _answer(cited=("a#0",)))
    assert wrong.failure_type == "wrong_source"
    assert incomplete.failure_type == "incomplete_citation"


# --- precedence --------------------------------------------------------------


def test_retrieval_miss_outranks_a_generation_failure() -> None:
    """Blaming generation for context it never received points at the wrong stage."""
    result = evaluate(_question(("z#9",)), RETRIEVED, _answer(text="", cited=("ghost#1",)))
    assert result.failure_type == "retrieval_miss"


def test_abstention_outranks_retrieval_miss() -> None:
    result = evaluate(_question(("z#9",)), RETRIEVED, _answer(abstained=True))
    assert result.failure_type == "unwarranted_refusal"


def test_empty_answer_outranks_grounding_failure() -> None:
    result = evaluate(_question(("a#0",)), RETRIEVED, _answer(text="", cited=()))
    assert result.failure_type == "empty_answer"


def test_invalid_citation_outranks_wrong_source() -> None:
    result = evaluate(_question(("a#0",)), RETRIEVED, _answer(cited=("b#0", "ghost#1")))
    assert result.failure_type == "invalid_citation"


# --- unanswerable questions --------------------------------------------------


def test_abstaining_without_citations_succeeds() -> None:
    question = _question((), category="unanswerable")
    result = evaluate(question, RETRIEVED, _answer(text="Not enough context.", abstained=True))
    assert result.success is True


def test_abstaining_but_citing_is_a_wrong_source() -> None:
    question = _question((), category="unanswerable")
    result = evaluate(question, RETRIEVED, _answer(abstained=True, cited=("a#0",)))
    assert result.failure_type == "wrong_source"


def test_answering_an_unanswerable_question_is_a_fabricated_answer() -> None:
    question = _question((), category="unanswerable")
    result = evaluate(question, RETRIEVED, _answer(cited=("a#0",)))
    assert result.failure_type == "fabricated_answer"


def test_blank_answer_on_an_unanswerable_question_is_still_fabrication() -> None:
    question = _question((), category="unanswerable")
    result = evaluate(question, RETRIEVED, _answer(text="", cited=()))
    assert result.failure_type == "fabricated_answer"


# --- invariants --------------------------------------------------------------


def test_every_declared_failure_type_is_reachable() -> None:
    answerable = _question(("a#0", "a#1"))
    unanswerable = _question((), category="unanswerable")
    produced = {
        evaluate(answerable, RETRIEVED, _answer(abstained=True)).failure_type,
        evaluate(_question(("z#9",)), RETRIEVED, _answer(cited=("a#0",))).failure_type,
        evaluate(answerable, RETRIEVED, _answer(text="", cited=("a#0", "a#1"))).failure_type,
        evaluate(answerable, RETRIEVED, _answer(cited=())).failure_type,
        evaluate(answerable, RETRIEVED, _answer(cited=("a#0", "a#1", "ghost#1"))).failure_type,
        evaluate(answerable, RETRIEVED, _answer(cited=("a#0", "a#1", "b#0"))).failure_type,
        evaluate(answerable, RETRIEVED, _answer(cited=("a#0",))).failure_type,
        evaluate(unanswerable, RETRIEVED, _answer(cited=("a#0",))).failure_type,
    }
    assert produced == set(FAILURE_TYPES)


def test_success_and_failure_type_cannot_disagree() -> None:
    with pytest.raises(ValueError):
        Evaluation(question_id="q", success=True, failure_type="retrieval_miss")
    with pytest.raises(ValueError):
        Evaluation(question_id="q", success=False, failure_type=None)
