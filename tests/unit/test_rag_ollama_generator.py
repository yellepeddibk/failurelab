"""Network-free tests for the Ollama generator.

Every test replaces the module-level opener, so no test opens a socket, starts a
model, or depends on Ollama being installed.
"""

from __future__ import annotations

import io
import json
import urllib.error

import pytest
from rag_pipeline import ollama_generator
from rag_pipeline.chunking import Chunk
from rag_pipeline.ollama_generator import (
    RESPONSE_SCHEMA,
    GeneratorError,
    OllamaGenerator,
    format_context,
)

CONTEXTS = (
    Chunk(chunk_id="a#0", doc_id="a", title="Alpha", text="Alpha body."),
    Chunk(chunk_id="b#0", doc_id="b", title="Beta", text="Beta body."),
)


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _install(monkeypatch, *, payload=None, error=None) -> dict:
    captured: dict = {"calls": 0}

    class _Opener:
        def open(self, request, timeout=None):
            captured["calls"] += 1
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
            if error is not None:
                raise error
            envelope = {"message": {"content": json.dumps(payload)}}
            return _Response(json.dumps(envelope).encode("utf-8"))

    monkeypatch.setattr(ollama_generator, "_OPENER", _Opener())
    return captured


def _valid(**overrides: object) -> dict:
    payload = {"answer": "An answer.", "citations": ["a#0"], "abstained": False}
    payload.update(overrides)
    return payload


def test_schema_forbids_additional_properties() -> None:
    assert RESPONSE_SCHEMA["additionalProperties"] is False
    assert set(RESPONSE_SCHEMA["required"]) == {"answer", "citations", "abstained"}


def test_context_is_rendered_with_citable_identifiers() -> None:
    rendered = format_context(CONTEXTS)
    assert "[a#0] Alpha" in rendered
    assert "[b#0] Beta" in rendered


def test_request_shape_is_deterministic(monkeypatch) -> None:
    captured = _install(monkeypatch, payload=_valid())
    OllamaGenerator(model="gemma3", timeout=12.5).generate("question?", CONTEXTS)

    assert captured["calls"] == 1
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["timeout"] == 12.5
    body = captured["body"]
    assert body["model"] == "gemma3"
    assert body["stream"] is False
    assert body["format"] == RESPONSE_SCHEMA
    assert body["options"] == {"temperature": 0, "seed": 0}
    assert "a#0" in body["messages"][1]["content"]


def test_answer_and_abstention_are_mapped(monkeypatch) -> None:
    _install(monkeypatch, payload=_valid(abstained=True, citations=[]))
    answer = OllamaGenerator(model="gemma3").generate("question?", CONTEXTS)
    assert answer.abstained is True
    assert answer.cited_chunk_ids == ()


def test_unretrieved_citations_are_preserved_not_filtered(monkeypatch) -> None:
    """The whole point of invalid_citation is that the bad identifier survives."""
    _install(monkeypatch, payload=_valid(citations=["a#0", "totally-made-up#9"]))
    answer = OllamaGenerator(model="gemma3").generate("question?", CONTEXTS)
    assert answer.cited_chunk_ids == ("a#0", "totally-made-up#9")


def test_blank_citations_are_dropped(monkeypatch) -> None:
    _install(monkeypatch, payload=_valid(citations=["a#0", "   ", ""]))
    answer = OllamaGenerator(model="gemma3").generate("question?", CONTEXTS)
    assert answer.cited_chunk_ids == ("a#0",)


@pytest.mark.parametrize(
    "payload",
    [
        {"answer": 1, "citations": [], "abstained": False},
        {"answer": "a", "citations": "nope", "abstained": False},
        {"answer": "a", "citations": [1], "abstained": False},
        {"answer": "a", "citations": [], "abstained": "no"},
        ["not", "an", "object"],
    ],
)
def test_unexpected_answer_shapes_rejected(monkeypatch, payload: object) -> None:
    _install(monkeypatch, payload=payload)
    with pytest.raises(GeneratorError):
        OllamaGenerator(model="gemma3").generate("question?", CONTEXTS)


def test_model_not_found_names_the_pull_command(monkeypatch) -> None:
    error = urllib.error.HTTPError("http://localhost:11434", 404, "nf", {}, None)  # type: ignore[arg-type]
    _install(monkeypatch, error=error)
    with pytest.raises(GeneratorError, match="ollama pull gemma3"):
        OllamaGenerator(model="gemma3").generate("question?", CONTEXTS)


def test_http_error_is_sanitized(monkeypatch) -> None:
    error = urllib.error.HTTPError("http://localhost:11434", 500, "boom", {}, None)  # type: ignore[arg-type]
    _install(monkeypatch, error=error)
    with pytest.raises(GeneratorError, match="HTTP status 500"):
        OllamaGenerator(model="gemma3").generate("question?", CONTEXTS)


def test_connection_error_is_actionable(monkeypatch) -> None:
    _install(monkeypatch, error=urllib.error.URLError("refused"))
    with pytest.raises(GeneratorError, match="Install or start Ollama"):
        OllamaGenerator(model="gemma3").generate("question?", CONTEXTS)


def test_timeout_is_reported(monkeypatch) -> None:
    _install(monkeypatch, error=TimeoutError())
    with pytest.raises(GeneratorError, match="timed out"):
        OllamaGenerator(model="gemma3").generate("question?", CONTEXTS)


def test_non_json_content_is_reported(monkeypatch) -> None:
    captured: dict = {}

    class _Opener:
        def open(self, request, timeout=None):
            captured["called"] = True
            envelope = {"message": {"content": "not json at all"}}
            return _Response(json.dumps(envelope).encode("utf-8"))

    monkeypatch.setattr(ollama_generator, "_OPENER", _Opener())
    with pytest.raises(GeneratorError, match="structured output schema"):
        OllamaGenerator(model="gemma3").generate("question?", CONTEXTS)


@pytest.mark.parametrize(
    "host",
    ["", "   ", "ftp://localhost", "http://", "http://user:pw@localhost:11434", "http://x/path"],
)
def test_invalid_hosts_rejected(host: str) -> None:
    with pytest.raises(ValueError):
        OllamaGenerator(model="gemma3", host=host)


@pytest.mark.parametrize("model", ["", "   "])
def test_invalid_models_rejected(model: str) -> None:
    with pytest.raises(ValueError):
        OllamaGenerator(model=model)


def test_construction_makes_no_request(monkeypatch) -> None:
    captured = _install(monkeypatch, payload=_valid())
    OllamaGenerator(model="gemma3")
    assert captured["calls"] == 0
