"""Loading and structural validation of the question set.

Gold chunk sets are exhaustive: a correct answer cites exactly the gold chunks and
nothing else. That convention is what makes ``wrong_source`` and
``incomplete_citation`` distinguishable rather than a single vague mismatch.

An unanswerable question carries an empty gold set. Its evidence is deliberately
absent from the corpus, so a pipeline that answers it at all has fabricated the
answer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, get_args

Category = Literal["single_source", "multi_source", "distractor", "unanswerable"]
CATEGORIES: tuple[str, ...] = get_args(Category)


@dataclass(frozen=True, slots=True)
class Question:
    """One evaluation question with its exhaustive gold evidence set."""

    id: str
    category: str
    question: str
    gold_chunks: tuple[str, ...]

    @property
    def answerable(self) -> bool:
        return self.category != "unanswerable"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def parse_questions(payload: Any) -> tuple[Question, ...]:
    """Validate the question payload and return it in file order."""
    _require(isinstance(payload, dict), "question payload must be an object")
    raw = payload.get("questions")
    _require(isinstance(raw, list) and bool(raw), "questions must be a non-empty list")

    questions: list[Question] = []
    seen: set[str] = set()
    for entry in raw:
        _require(isinstance(entry, dict), "each question must be an object")
        identifier = entry.get("id")
        category = entry.get("category")
        text = entry.get("question")
        gold = entry.get("gold_chunks")

        _require(isinstance(identifier, str) and bool(identifier.strip()), "id must be non-empty")
        _require(identifier not in seen, f"duplicate question id: {identifier}")
        _require(category in CATEGORIES, f"{identifier}: unknown category {category!r}")
        _require(isinstance(text, str) and bool(text.strip()), f"{identifier}: question is empty")
        _require(isinstance(gold, list), f"{identifier}: gold_chunks must be a list")
        _require(len(gold) == len(set(gold)), f"{identifier}: duplicate gold chunk")

        answerable = category != "unanswerable"
        _require(bool(gold) == answerable, f"{identifier}: gold set does not match its category")
        if category == "multi_source":
            _require(len(gold) >= 2, f"{identifier}: multi_source needs at least two gold chunks")
        if category in ("single_source", "distractor"):
            _require(len(gold) == 1, f"{identifier}: {category} needs exactly one gold chunk")

        seen.add(identifier)
        questions.append(
            Question(
                id=identifier,
                category=str(category),
                question=text.strip(),
                gold_chunks=tuple(str(item) for item in gold),
            )
        )
    return tuple(questions)


def load_questions(path: Path) -> tuple[Question, ...]:
    """Load and validate ``questions.json``."""
    return parse_questions(json.loads(path.read_text(encoding="utf-8")))
