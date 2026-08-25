"""Deterministic corpus loading and chunking.

A document is a Markdown file whose stem is its ``doc_id``, whose first ATX
heading is its title, and whose remaining paragraphs are its body. Chunking packs
whole paragraphs up to a character budget and never splits a sentence across chunk
bodies. Consecutive chunks additionally repeat a short tail of the previous chunk
as leading context, and that prefix may begin mid-sentence.

Every function here is pure. The same corpus always produces the same chunks in
the same order with the same identifiers, which is what allows the generated
example datasets to be regenerated and compared byte for byte.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DEFAULT_MAX_CHARS = 500
DEFAULT_OVERLAP_CHARS = 80

_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")
_SENTENCE_BREAK = re.compile(r"(?<=[.!?]) +")
_HEADING = re.compile(r"^#\s+(?P<title>.+?)\s*$")


@dataclass(frozen=True, slots=True)
class Document:
    """One source document."""

    doc_id: str
    title: str
    paragraphs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Chunk:
    """One retrievable unit of a document."""

    chunk_id: str
    doc_id: str
    title: str
    text: str


def _normalize(text: str) -> str:
    """Collapse hard-wrapped lines into a single whitespace-normalized string."""
    return " ".join(text.split())


def parse_document(doc_id: str, raw: str) -> Document:
    """Parse Markdown into a title and normalized paragraphs.

    The first ATX heading becomes the title. A document without one uses its
    ``doc_id`` as the title rather than failing, so a corpus stays usable while
    it is being written.
    """
    blocks = [block for block in _PARAGRAPH_BREAK.split(raw) if block.strip()]
    title = doc_id
    body: list[str] = []
    for block in blocks:
        first_line = block.strip().splitlines()[0]
        heading = _HEADING.match(first_line)
        if heading is not None and not body and title == doc_id:
            title = heading.group("title")
            remainder = block.strip().splitlines()[1:]
            if remainder:
                body.append(_normalize("\n".join(remainder)))
            continue
        body.append(_normalize(block))
    return Document(doc_id=doc_id, title=title, paragraphs=tuple(body))


def load_corpus(directory: Path) -> tuple[Document, ...]:
    """Load every Markdown file in ``directory``, ordered by filename."""
    documents = [
        parse_document(path.stem, path.read_text(encoding="utf-8"))
        for path in sorted(directory.glob("*.md"))
    ]
    return tuple(documents)


def _split_oversized(paragraph: str, max_chars: int) -> list[str]:
    """Split a paragraph that exceeds the budget, on sentence boundaries only.

    A single sentence longer than the budget is kept whole. Cutting inside a
    sentence would produce a chunk that cannot be read or cited honestly.
    """
    packed: list[str] = []
    current = ""
    for sentence in _SENTENCE_BREAK.split(paragraph):
        candidate = sentence if not current else f"{current} {sentence}"
        if current and len(candidate) > max_chars:
            packed.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        packed.append(current)
    return packed


def _overlap_prefix(previous: str, overlap_chars: int) -> str:
    """Take the tail of the previous chunk, snapped forward to a word boundary."""
    if overlap_chars <= 0 or not previous:
        return ""
    if len(previous) <= overlap_chars:
        return previous
    tail = previous[-overlap_chars:]
    boundary = tail.find(" ")
    return tail if boundary == -1 else tail[boundary + 1 :]


def chunk_document(
    document: Document,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> tuple[Chunk, ...]:
    """Chunk one document into ``{doc_id}#{index}`` units."""
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must not be negative")
    if overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be smaller than max_chars")

    units: list[str] = []
    for paragraph in document.paragraphs:
        if len(paragraph) <= max_chars:
            units.append(paragraph)
        else:
            units.extend(_split_oversized(paragraph, max_chars))

    bodies: list[str] = []
    current = ""
    for unit in units:
        candidate = unit if not current else f"{current} {unit}"
        if current and len(candidate) > max_chars:
            bodies.append(current)
            current = unit
        else:
            current = candidate
    if current:
        bodies.append(current)

    chunks: list[Chunk] = []
    for index, body in enumerate(bodies):
        prefix = _overlap_prefix(bodies[index - 1], overlap_chars) if index else ""
        text = f"{prefix} {body}".strip() if prefix else body
        chunks.append(
            Chunk(
                chunk_id=f"{document.doc_id}#{index}",
                doc_id=document.doc_id,
                title=document.title,
                text=text,
            )
        )
    return tuple(chunks)


def chunk_corpus(
    documents: tuple[Document, ...],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    overlap_chars: int = DEFAULT_OVERLAP_CHARS,
) -> tuple[Chunk, ...]:
    """Chunk every document, preserving corpus order."""
    chunks: list[Chunk] = []
    for document in documents:
        chunks.extend(chunk_document(document, max_chars=max_chars, overlap_chars=overlap_chars))
    return tuple(chunks)
