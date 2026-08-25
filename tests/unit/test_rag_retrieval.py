"""Retrieval must be deterministic and totally ordered."""

from __future__ import annotations

from pathlib import Path

import pytest
from rag_pipeline.chunking import Chunk, chunk_corpus, load_corpus
from rag_pipeline.retrieval import BM25Retriever, build_retrievers, tokenize

CORPUS_DIR = Path(__file__).resolve().parents[2] / "examples" / "rag_pipeline" / "corpus"


def _corpus_chunks() -> tuple[Chunk, ...]:
    return chunk_corpus(load_corpus(CORPUS_DIR))


def _toy_chunks() -> tuple[Chunk, ...]:
    return (
        Chunk(chunk_id="d#0", doc_id="d", title="Alpha Handbook", text="shared body text"),
        Chunk(chunk_id="d#1", doc_id="d", title="Alpha Handbook", text="shared body text"),
        Chunk(chunk_id="e#0", doc_id="e", title="Beta Handbook", text="shared body text"),
        Chunk(chunk_id="f#0", doc_id="f", title="Gamma Handbook", text="unique zebra token"),
    )


def test_tokenize_lowercases_and_drops_punctuation() -> None:
    assert tokenize("Severity One: 99th percentile!") == ["severity", "one", "99th", "percentile"]


def test_retrieval_is_deterministic() -> None:
    chunks = _corpus_chunks()
    first = BM25Retriever(chunks=chunks).retrieve("escalation owner", k=5)
    second = BM25Retriever(chunks=chunks).retrieve("escalation owner", k=5)
    assert [item.chunk.chunk_id for item in first] == [item.chunk.chunk_id for item in second]
    assert [item.score for item in first] == [item.score for item in second]


def test_ties_break_by_chunk_id() -> None:
    retriever = BM25Retriever(chunks=_toy_chunks(), title_repeats=0)
    results = retriever.retrieve("shared body text", k=3)
    tied = [item.chunk.chunk_id for item in results if item.score == results[0].score]
    assert tied == sorted(tied)


def test_k_limits_results_and_zero_scores_still_fill() -> None:
    retriever = BM25Retriever(chunks=_toy_chunks())
    results = retriever.retrieve("zebra", k=4)
    assert len(results) == 4
    assert results[0].chunk.chunk_id == "f#0"
    assert results[0].score > 0
    assert results[-1].score == 0.0


def test_rare_term_outranks_common_term() -> None:
    retriever = BM25Retriever(chunks=_toy_chunks(), title_repeats=0)
    rare = retriever.retrieve("zebra", k=1)[0]
    common = retriever.retrieve("shared", k=1)[0]
    assert rare.score > common.score


def test_title_boosting_promotes_a_title_only_match() -> None:
    chunks = _toy_chunks()
    plain = BM25Retriever(chunks=chunks, title_repeats=1)
    boosted = BM25Retriever(chunks=chunks, title_repeats=5)
    query = "Beta"
    plain_score = plain.retrieve(query, k=1)[0].score
    boosted_score = boosted.retrieve(query, k=1)[0].score
    assert boosted.retrieve(query, k=1)[0].chunk.chunk_id == "e#0"
    assert boosted_score > plain_score


def test_query_with_no_known_terms_scores_zero() -> None:
    retriever = BM25Retriever(chunks=_toy_chunks())
    results = retriever.retrieve("nonexistentterm", k=2)
    assert all(item.score == 0.0 for item in results)
    assert [item.chunk.chunk_id for item in results] == ["d#0", "d#1"]


def test_build_retrievers_exposes_both_variants() -> None:
    retrievers = build_retrievers(_corpus_chunks())
    assert set(retrievers) == {"bm25-v1", "bm25-title-boosted"}
    assert retrievers["bm25-v1"].title_repeats == 1
    assert retrievers["bm25-title-boosted"].title_repeats > 1
    for key, retriever in retrievers.items():
        assert retriever.name == key


def test_empty_chunk_collection_rejected() -> None:
    with pytest.raises(ValueError):
        BM25Retriever(chunks=())


@pytest.mark.parametrize("k", [0, -1])
def test_non_positive_k_rejected(k: int) -> None:
    with pytest.raises(ValueError):
        BM25Retriever(chunks=_toy_chunks()).retrieve("query", k=k)


def test_negative_title_repeats_rejected() -> None:
    with pytest.raises(ValueError):
        BM25Retriever(chunks=_toy_chunks(), title_repeats=-1)
