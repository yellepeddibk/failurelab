"""The example datasets, defined once so every consumer agrees.

Three datasets are generated and committed. Two are the answerable partition run
through each retriever, which is what makes a baseline against candidate
comparison meaningful. The third is the abstention partition, kept separate on
purpose: a correct refusal is a nonempty answer with no citations, so mixing
refusals into the answerable set would depress citation metrics while the pipeline
was behaving perfectly.

Seeded failures live here rather than in the corpus. Retrieval failures are real,
produced by BM25 over the real documents. Generation failures are authored,
because a language model cannot be made to fail reproducibly on demand and
continuous integration cannot depend on one that tries.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from failurelab.config.settings import FailureLabConfig, load_config
from failurelab.models.trace import TraceRecord
from rag_pipeline.chunking import Chunk, chunk_corpus, load_corpus
from rag_pipeline.generation import Generator, ScriptedGenerator, build_script
from rag_pipeline.pipeline import Clock, FixedClock, run_pipeline, write_traces
from rag_pipeline.questions import Question, load_questions
from rag_pipeline.retrieval import DEFAULT_K, build_retrievers

# Seeded generation failures, by question id. Every outcome the evaluator can
# classify is reachable, so the datasets exercise the whole decision table.
SEEDED_FAILURES: dict[str, str] = {
    "q001": "cite_none",  # grounding_failure
    "q002": "cite_unretrieved",  # invalid_citation
    "q003": "empty",  # empty_answer
    "q004": "abstain",  # unwarranted_refusal
    "q017": "cite_partial",  # incomplete_citation
    "q025": "cite_wrong",  # wrong_source
    "q033": "fabricate",  # fabricated_answer
}


@dataclass(frozen=True, slots=True)
class DatasetSpec:
    """One generated dataset."""

    filename: str
    retriever: str
    run_id: str
    answerable: bool


DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec("rag_v1.jsonl", "bm25-v1", "v1", answerable=True),
    DatasetSpec("rag_v2.jsonl", "bm25-title-boosted", "v2", answerable=True),
    DatasetSpec("rag_abstention.jsonl", "bm25-v1", "abstention", answerable=False),
)


def analysis_config(directory: Path | None = None) -> FailureLabConfig:
    """Load the analysis config that matches this pipeline.

    The retrieval_k it sets must equal the k the pipeline retrieves with, because
    FailureLab truncates retrieved_sources to the configured k before computing
    recall. A mismatch measures a different metric than the one being reported.
    """
    base = directory or example_dir()
    return load_config(base / "config.yaml")


def example_dir() -> Path:
    """The directory holding the corpus, questions, and generated data."""
    return Path(__file__).resolve().parent


def load_chunks(directory: Path | None = None) -> tuple[Chunk, ...]:
    base = directory or example_dir()
    return chunk_corpus(load_corpus(base / "corpus"))


def load_all_questions(directory: Path | None = None) -> tuple[Question, ...]:
    base = directory or example_dir()
    return load_questions(base / "questions.json")


def partition(questions: Sequence[Question], *, answerable: bool) -> tuple[Question, ...]:
    """Split the question set into its answerable and abstention halves."""
    return tuple(question for question in questions if question.answerable is answerable)


def scripted_generator(questions: Sequence[Question]) -> ScriptedGenerator:
    """The deterministic generator used for the committed datasets.

    Seeds are scoped to the questions actually being run. ``SEEDED_FAILURES``
    spans both partitions, and ``build_script`` rejects an override naming a
    question it was not given, which is what keeps a stale seed from passing
    unnoticed.
    """
    present = {question.id for question in questions}
    overrides = {key: value for key, value in SEEDED_FAILURES.items() if key in present}
    return ScriptedGenerator(script=build_script(questions, overrides))


def generate(
    spec: DatasetSpec,
    *,
    generator: Generator | None = None,
    clock: Clock | None = None,
    k: int = DEFAULT_K,
    include_context: bool = False,
    directory: Path | None = None,
) -> tuple[TraceRecord, ...]:
    """Produce the traces for one dataset."""
    chunks = load_chunks(directory)
    questions = partition(load_all_questions(directory), answerable=spec.answerable)
    return run_pipeline(
        questions=questions,
        retriever=build_retrievers(chunks)[spec.retriever],
        generator=generator or scripted_generator(questions),
        clock=clock or FixedClock(),
        run_id=spec.run_id,
        k=k,
        include_context=include_context,
    )


def generate_all(output_dir: Path, *, directory: Path | None = None) -> list[Path]:
    """Regenerate every committed dataset into ``output_dir``."""
    written: list[Path] = []
    for spec in DATASETS:
        traces = generate(spec, directory=directory)
        written.append(write_traces(traces, output_dir / spec.filename))
    return written
