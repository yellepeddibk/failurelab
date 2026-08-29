"""Run the pipeline end to end and emit FailureLab traces.

The stages are retrieve, generate, evaluate, record. Everything except generation
is deterministic, and timing is injected rather than read from the ambient clock,
so a run with the scripted generator produces byte-identical traces every time.
That is what allows the committed example datasets to be regenerated and compared.

Raw retrieved context is excluded unless explicitly requested. An example that
leaked its context by default would contradict the privacy posture of the tool it
demonstrates.
"""

from __future__ import annotations

import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from failurelab.models.trace import TraceRecord
from rag_pipeline.chunking import Chunk
from rag_pipeline.evaluate import evaluate
from rag_pipeline.generation import Generator
from rag_pipeline.questions import Question
from rag_pipeline.retrieval import DEFAULT_K, Retriever

PROJECT = "rag-example"
PROMPT_VERSION = "rag-prompt-1"
CORPUS_VERSION = "corpus-1"


class Clock(Protocol):
    """Supplies timestamps and latency, so runs can be made reproducible."""

    def timestamp(self, index: int) -> datetime:
        """The timestamp for the trace at ``index``."""
        ...

    def latency_ms(self, elapsed_ns: int) -> float:
        """The latency to record for a step that took ``elapsed_ns``."""
        ...


@dataclass(frozen=True, slots=True)
class FixedClock:
    """Deterministic timing for reproducible fixtures.

    Real durations and wall-clock timestamps cannot appear in a committed dataset
    that continuous integration regenerates and compares byte for byte.
    """

    start: datetime = datetime(2026, 1, 1, tzinfo=UTC)
    step: timedelta = timedelta(seconds=1)
    fixed_latency_ms: float = 100.0

    def timestamp(self, index: int) -> datetime:
        return self.start + self.step * index

    def latency_ms(self, elapsed_ns: int) -> float:
        return self.fixed_latency_ms


@dataclass(frozen=True, slots=True)
class RealClock:
    """Wall-clock timestamps and measured latency, for live runs."""

    def timestamp(self, index: int) -> datetime:
        return datetime.now(UTC)

    def latency_ms(self, elapsed_ns: int) -> float:
        return elapsed_ns / 1_000_000


def run_pipeline(
    *,
    questions: Sequence[Question],
    retriever: Retriever,
    generator: Generator,
    clock: Clock,
    run_id: str,
    k: int = DEFAULT_K,
    include_context: bool = False,
) -> tuple[TraceRecord, ...]:
    """Answer every question and return one trace per question, in file order."""
    if not questions:
        raise ValueError("at least one question is required")
    if not run_id.strip():
        raise ValueError("run_id must be non-empty")

    traces: list[TraceRecord] = []
    for index, question in enumerate(questions):
        started = time.perf_counter_ns()
        scored = retriever.retrieve(question.question, k=k)
        contexts: tuple[Chunk, ...] = tuple(item.chunk for item in scored)
        answer = generator.generate(question.question, contexts)
        elapsed = time.perf_counter_ns() - started

        retrieved_ids = [chunk.chunk_id for chunk in contexts]
        outcome = evaluate(question, retrieved_ids, answer)

        traces.append(
            TraceRecord.model_validate(
                {
                    "schema_version": "0.1",
                    "trace_id": f"rag-{run_id}-{question.id}",
                    "project": PROJECT,
                    "run_id": run_id,
                    "version": CORPUS_VERSION,
                    "timestamp": clock.timestamp(index),
                    "query": question.question,
                    "answer": answer.text,
                    "success": outcome.success,
                    "failure_type": outcome.failure_type,
                    "model": generator.model,
                    "prompt_version": PROMPT_VERSION,
                    "retriever_version": retriever.name,
                    "retrieved_sources": retrieved_ids,
                    "expected_sources": list(question.gold_chunks),
                    # Preserved verbatim. Filtering to the retrieved set here
                    # would erase every invalid_citation before it was recorded.
                    "citations": list(answer.cited_chunk_ids),
                    "retrieved_context": (
                        [chunk.text for chunk in contexts] if include_context else None
                    ),
                    "latency_ms": clock.latency_ms(elapsed),
                    "metadata": {"question_id": question.id, "category": question.category},
                }
            )
        )
    return tuple(traces)


def write_traces(traces: Sequence[TraceRecord], path: Path) -> Path:
    """Write traces as JSONL with a stable key order and a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [trace.to_stable_json() for trace in traces]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path
