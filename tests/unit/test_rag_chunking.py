"""Chunking must be deterministic, readable, and stably identified."""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest
from rag_pipeline.chunking import (
    DEFAULT_MAX_CHARS,
    DEFAULT_OVERLAP_CHARS,
    Document,
    chunk_corpus,
    chunk_document,
    load_corpus,
    parse_document,
)

CORPUS_DIR = Path(__file__).resolve().parents[2] / "examples" / "rag_pipeline" / "corpus"


def test_corpus_loads_in_filename_order() -> None:
    documents = load_corpus(CORPUS_DIR)
    assert documents
    ids = [document.doc_id for document in documents]
    assert ids == sorted(ids)
    assert len(ids) == len(set(ids))


def test_title_comes_from_the_first_heading() -> None:
    document = parse_document("runbook-payments", "# Payments Service Runbook\n\nBody text here.\n")
    assert document.title == "Payments Service Runbook"
    assert document.paragraphs == ("Body text here.",)


def test_document_without_heading_falls_back_to_doc_id() -> None:
    document = parse_document("no-heading", "Just a paragraph.\n")
    assert document.title == "no-heading"
    assert document.paragraphs == ("Just a paragraph.",)


def test_hard_wrapped_lines_are_normalized() -> None:
    document = parse_document("wrapped", "# T\n\nline one\nline two\nline three\n")
    assert document.paragraphs == ("line one line two line three",)


def test_chunk_ids_are_sequential_and_scoped_to_the_document() -> None:
    documents = load_corpus(CORPUS_DIR)
    chunks = chunk_corpus(documents)
    assert len(chunks) == len({chunk.chunk_id for chunk in chunks})
    for document in documents:
        owned = [chunk for chunk in chunks if chunk.doc_id == document.doc_id]
        assert [chunk.chunk_id for chunk in owned] == [
            f"{document.doc_id}#{index}" for index in range(len(owned))
        ]


def test_chunking_is_deterministic() -> None:
    first = chunk_corpus(load_corpus(CORPUS_DIR))
    second = chunk_corpus(load_corpus(CORPUS_DIR))
    assert first == second


def test_chunks_respect_the_budget_plus_overlap() -> None:
    chunks = chunk_corpus(load_corpus(CORPUS_DIR))
    limit = DEFAULT_MAX_CHARS + DEFAULT_OVERLAP_CHARS
    assert chunks
    for chunk in chunks:
        assert len(chunk.text) <= limit


def test_every_chunk_carries_its_document_title() -> None:
    documents = load_corpus(CORPUS_DIR)
    titles = {document.doc_id: document.title for document in documents}
    for chunk in chunk_corpus(documents):
        assert chunk.title == titles[chunk.doc_id]


def test_overlap_repeats_the_tail_of_the_previous_chunk() -> None:
    paragraphs = tuple(
        f"Sentence number {index} padded out to force packing." * 3 for index in range(6)
    )
    document = Document(doc_id="d", title="T", paragraphs=paragraphs)
    chunks = chunk_document(document, max_chars=200, overlap_chars=40)
    assert len(chunks) > 1
    for previous, current in itertools.pairwise(chunks):
        prefix = current.text[:20]
        assert prefix in previous.text


def test_no_overlap_when_disabled() -> None:
    paragraphs = tuple(
        f"Paragraph {index} with enough text to split into units." for index in range(8)
    )
    document = Document(doc_id="d", title="T", paragraphs=paragraphs)
    chunks = chunk_document(document, max_chars=120, overlap_chars=0)
    assert len(chunks) > 1
    rejoined = " ".join(chunk.text for chunk in chunks)
    for index in range(8):
        assert rejoined.count(f"Paragraph {index} ") == 1


def test_oversized_paragraph_splits_on_sentence_boundaries() -> None:
    paragraph = " ".join(f"This is sentence {index}." for index in range(40))
    document = Document(doc_id="d", title="T", paragraphs=(paragraph,))
    chunks = chunk_document(document, max_chars=200, overlap_chars=0)
    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk.text.endswith(".")


def test_single_sentence_longer_than_budget_is_kept_whole() -> None:
    sentence = "word " * 200
    document = Document(doc_id="d", title="T", paragraphs=(sentence.strip() + ".",))
    chunks = chunk_document(document, max_chars=100, overlap_chars=0)
    assert len(chunks) == 1


@pytest.mark.parametrize(
    ("max_chars", "overlap_chars"),
    [(0, 0), (100, -1), (100, 100), (100, 200)],
)
def test_invalid_chunking_bounds_rejected(max_chars: int, overlap_chars: int) -> None:
    document = Document(doc_id="d", title="T", paragraphs=("text",))
    with pytest.raises(ValueError):
        chunk_document(document, max_chars=max_chars, overlap_chars=overlap_chars)
