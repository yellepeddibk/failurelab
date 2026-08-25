"""Classify one answered question into exactly one outcome.

What this measures, stated plainly: whether the pipeline retrieved the required
evidence and cited exactly that evidence. It is an evidence and grounding
criterion, not answer correctness. A fluent but wrong answer that cites the right
chunks is scored as a success here. Gold sets are authored to be exhaustive, which
is what makes ``wrong_source`` and ``incomplete_citation`` distinguishable instead
of one vague mismatch.

Conditions are checked in pipeline order, so a trace that could not possibly have
succeeded is attributed upstream. A question whose evidence was never retrieved is
a retrieval failure even if the generator also misbehaved, because blaming
generation for missing context would point the reader at the wrong stage.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal, get_args

from rag_pipeline.generation import GeneratedAnswer
from rag_pipeline.questions import Question

FailureType = Literal[
    "retrieval_miss",
    "empty_answer",
    "grounding_failure",
    "invalid_citation",
    "wrong_source",
    "incomplete_citation",
    "unwarranted_refusal",
    "fabricated_answer",
]
FAILURE_TYPES: tuple[str, ...] = get_args(FailureType)


@dataclass(frozen=True, slots=True)
class Evaluation:
    """The outcome for one question."""

    question_id: str
    success: bool
    failure_type: str | None

    def __post_init__(self) -> None:
        if self.success and self.failure_type is not None:
            raise ValueError("a successful evaluation cannot carry a failure type")
        if not self.success and self.failure_type is None:
            raise ValueError("a failed evaluation requires a failure type")


def _succeeded(question_id: str) -> Evaluation:
    return Evaluation(question_id=question_id, success=True, failure_type=None)


def _failed(question_id: str, failure_type: str) -> Evaluation:
    return Evaluation(question_id=question_id, success=False, failure_type=failure_type)


def evaluate(
    question: Question,
    retrieved_chunk_ids: Sequence[str],
    answer: GeneratedAnswer,
) -> Evaluation:
    """Classify one answered question.

    ``retrieved_chunk_ids`` is what retrieval actually returned, and
    ``answer.cited_chunk_ids`` is what the generator actually cited, preserved
    verbatim. Comparing the two is what makes a hallucinated citation visible.
    """
    retrieved = set(retrieved_chunk_ids)
    cited = set(answer.cited_chunk_ids)
    expected = set(question.gold_chunks)

    if not question.answerable:
        if answer.abstained:
            return _succeeded(question.id) if not cited else _failed(question.id, "wrong_source")
        return _failed(question.id, "fabricated_answer")

    if answer.abstained:
        return _failed(question.id, "unwarranted_refusal")
    if not expected <= retrieved:
        return _failed(question.id, "retrieval_miss")
    if not answer.text.strip():
        return _failed(question.id, "empty_answer")
    if not cited:
        return _failed(question.id, "grounding_failure")
    if not cited <= retrieved:
        return _failed(question.id, "invalid_citation")
    if cited - expected:
        return _failed(question.id, "wrong_source")
    if expected - cited:
        return _failed(question.id, "incomplete_citation")
    return _succeeded(question.id)
