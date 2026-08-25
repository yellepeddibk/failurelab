"""BM25 retrieval over chunks, implemented with the standard library.

BM25 is used rather than embeddings for three reasons: it needs no model and no
network, it is exactly reproducible, and its failure characteristics are the ones
this example exists to show. Lexical retrieval misses when the question and the
document use different vocabulary, and it is fooled by near-duplicate documents.
Both are real failures that FailureLab can then diagnose from the traces.

Two variants are provided. They differ only in how much weight a document title
carries, so a comparison between them isolates that single change:

``bm25-v1``
    Title tokens are indexed once, exactly like body tokens.

``bm25-title-boosted``
    Title tokens are indexed ``title_repeats`` times, so a title match outweighs
    an equally frequent body match.

Ranking is total and stable: results sort by descending score, then by ascending
``chunk_id``. Two chunks with identical scores therefore always come back in the
same order, on every platform and every run.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol

from rag_pipeline.chunking import Chunk

DEFAULT_K = 5
DEFAULT_K1 = 1.5
DEFAULT_B = 0.75
DEFAULT_TITLE_REPEATS = 3

_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    """Lowercase and split on non-alphanumeric runs."""
    return _TOKEN.findall(text.lower())


@dataclass(frozen=True, slots=True)
class ScoredChunk:
    """A chunk with the score that ranked it."""

    chunk: Chunk
    score: float


class Retriever(Protocol):
    """Anything that can rank chunks for a query."""

    name: str

    def retrieve(self, query: str, k: int = DEFAULT_K) -> tuple[ScoredChunk, ...]:
        """Return the top ``k`` chunks, best first."""
        ...


@dataclass(slots=True)
class BM25Retriever:
    """Okapi BM25 over a fixed chunk collection.

    The index is built once at construction. Nothing here reads the filesystem,
    the clock, or the network, so two retrievers built from the same chunks always
    rank identically.
    """

    chunks: tuple[Chunk, ...]
    name: str = "bm25-v1"
    k1: float = DEFAULT_K1
    b: float = DEFAULT_B
    title_repeats: int = 1
    _term_frequencies: list[Counter[str]] = field(init=False, repr=False, default_factory=list)
    _lengths: list[int] = field(init=False, repr=False, default_factory=list)
    _document_frequency: Counter[str] = field(init=False, repr=False, default_factory=Counter)
    _average_length: float = field(init=False, repr=False, default=0.0)

    def __post_init__(self) -> None:
        if not self.chunks:
            raise ValueError("at least one chunk is required")
        if self.title_repeats < 0:
            raise ValueError("title_repeats must not be negative")

        for chunk in self.chunks:
            tokens = tokenize(chunk.text) + tokenize(chunk.title) * self.title_repeats
            counts = Counter(tokens)
            self._term_frequencies.append(counts)
            self._lengths.append(len(tokens))
            self._document_frequency.update(counts.keys())

        total = sum(self._lengths)
        self._average_length = total / len(self._lengths) if self._lengths else 0.0

    def _inverse_document_frequency(self, term: str) -> float:
        frequency = self._document_frequency.get(term, 0)
        if frequency == 0:
            return 0.0
        count = len(self.chunks)
        return math.log(1.0 + (count - frequency + 0.5) / (frequency + 0.5))

    def score(self, query: str, index: int) -> float:
        """Score one indexed chunk against a query."""
        counts = self._term_frequencies[index]
        length = self._lengths[index]
        denominator_length = (
            self.b * (length / self._average_length) if self._average_length else 0.0
        )
        total = 0.0
        for term in tokenize(query):
            frequency = counts.get(term, 0)
            if frequency == 0:
                continue
            weight = self._inverse_document_frequency(term)
            numerator = frequency * (self.k1 + 1.0)
            denominator = frequency + self.k1 * (1.0 - self.b + denominator_length)
            total += weight * (numerator / denominator)
        return total

    def retrieve(self, query: str, k: int = DEFAULT_K) -> tuple[ScoredChunk, ...]:
        """Return the top ``k`` chunks, best first, ties broken by ``chunk_id``.

        Chunks scoring zero are still returned when ``k`` exceeds the number of
        matches. A retriever that returned nothing would make abstention trivial,
        and the point of the abstention questions is that plausible-looking
        context is retrieved and the answer must still be refused.
        """
        if k <= 0:
            raise ValueError("k must be positive")
        scored = [
            ScoredChunk(chunk=chunk, score=self.score(query, index))
            for index, chunk in enumerate(self.chunks)
        ]
        scored.sort(key=lambda item: (-item.score, item.chunk.chunk_id))
        return tuple(scored[:k])


def build_retrievers(chunks: tuple[Chunk, ...]) -> dict[str, BM25Retriever]:
    """Build the two retriever variants compared by this example."""
    return {
        "bm25-v1": BM25Retriever(chunks=chunks, name="bm25-v1", title_repeats=1),
        "bm25-title-boosted": BM25Retriever(
            chunks=chunks,
            name="bm25-title-boosted",
            title_repeats=DEFAULT_TITLE_REPEATS,
        ),
    }
