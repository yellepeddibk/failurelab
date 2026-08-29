"""Answer generation against a local Ollama server.

This is the live path for the example. It uses only the standard library, so
running the example adds nothing to the install footprint. The Ollama runtime and
the model itself remain prerequisites you install and pull yourself.

Structured output is requested so that abstention is a boolean the model sets
rather than a phrase this code has to recognize. Every object in the schema sets
``additionalProperties: false``: hosted structured-output APIs reject a schema
that omits it, and locally it stops the model inventing keys the parser would
silently drop.

Citations are returned exactly as the model produced them. Filtering out a
citation that was never retrieved would destroy the evidence for the very failure
this example exists to surface.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from rag_pipeline.chunking import Chunk
from rag_pipeline.generation import GeneratedAnswer

DEFAULT_HOST = "http://localhost:11434"
# Local models are slow. A gemma3 answer over five retrieved chunks measured 33 to
# 47 seconds on ordinary hardware, and a 60 second budget produced real timeouts
# partway through a full run. The default is generous so the example works out of
# the box; the runner exposes --timeout for anything slower.
DEFAULT_TIMEOUT = 180.0
MAX_RESPONSE_BYTES = 1_048_576

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
        "abstained": {"type": "boolean"},
    },
    "additionalProperties": False,
    "required": ["answer", "citations", "abstained"],
}

SYSTEM_PROMPT = (
    "You answer questions using only the numbered context passages provided. "
    "Cite the exact passage identifiers you used, in the citations array. "
    "Never cite an identifier that does not appear in the context. "
    "If the context does not contain the answer, set abstained to true, leave "
    "citations empty, and say that the context is insufficient. "
    "Do not use knowledge from outside the context."
)


def _build_restricted_opener() -> urllib.request.OpenerDirector:
    """Build an opener that can only speak HTTP and HTTPS.

    The generic ``urlopen`` entry point also understands ``file:``, ``ftp:``, and
    ``data:`` URLs. Restricting the handler set means a misconfigured host cannot
    be used to read a local file.
    """
    opener = urllib.request.OpenerDirector()
    opener.add_handler(urllib.request.HTTPHandler())
    opener.add_handler(urllib.request.HTTPSHandler())
    opener.add_handler(urllib.request.HTTPDefaultErrorHandler())
    opener.add_handler(urllib.request.HTTPErrorProcessor())
    opener.add_handler(urllib.request.UnknownHandler())
    return opener


_OPENER = _build_restricted_opener()


class GeneratorError(RuntimeError):
    """A sanitized generation failure naming the host, model, and status only."""


def _normalize_host(host: str) -> str:
    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be a non-empty string")
    candidate = host.strip().rstrip("/")
    parts = urllib.parse.urlsplit(candidate)
    if parts.scheme not in ("http", "https"):
        raise ValueError("host must use the http or https scheme")
    if not parts.hostname:
        raise ValueError("host must include a hostname")
    if parts.username or parts.password:
        raise ValueError("host must not embed a username or password")
    if parts.path not in ("", "/"):
        raise ValueError("host must not contain a path")
    return candidate


def format_context(contexts: Sequence[Chunk]) -> str:
    """Render retrieved chunks so the model can cite them by identifier."""
    return "\n\n".join(f"[{chunk.chunk_id}] {chunk.title}\n{chunk.text}" for chunk in contexts)


@dataclass(slots=True)
class OllamaGenerator:
    """Generate answers with a local or self-hosted Ollama model."""

    model: str
    host: str = DEFAULT_HOST
    name: str = "ollama"
    timeout: float = DEFAULT_TIMEOUT

    def __post_init__(self) -> None:
        if not isinstance(self.model, str) or not self.model.strip():
            raise ValueError("model must be a non-empty string")
        self.model = self.model.strip()
        self.host = _normalize_host(self.host)

    def generate(self, question: str, contexts: Sequence[Chunk]) -> GeneratedAnswer:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Context:\n{format_context(contexts)}\n\nQuestion: {question}",
                },
            ],
            "stream": False,
            "format": RESPONSE_SCHEMA,
            "options": {"temperature": 0, "seed": 0},
        }
        request = urllib.request.Request(
            f"{self.host}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with _OPENER.open(request, timeout=self.timeout) as response:
                body = response.read(MAX_RESPONSE_BYTES + 1)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise GeneratorError(
                    f"Ollama model {self.model!r} was not found at {self.host}. "
                    f"Run: ollama pull {self.model}"
                ) from None
            raise GeneratorError(
                f"Ollama request to {self.host} failed with HTTP status {error.code}."
            ) from None
        except TimeoutError:
            raise GeneratorError(
                f"Ollama request to {self.host} timed out after {self.timeout} seconds."
            ) from None
        except urllib.error.URLError:
            raise GeneratorError(
                f"Could not connect to Ollama at {self.host}. Install or start Ollama, then retry."
            ) from None

        if len(body) > MAX_RESPONSE_BYTES:
            raise GeneratorError(f"Ollama at {self.host} returned an oversized response.")
        return self._parse(body)

    def _parse(self, body: bytes) -> GeneratedAnswer:
        try:
            envelope = json.loads(body.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise GeneratorError(f"Ollama at {self.host} returned malformed JSON.") from None
        message = envelope.get("message") if isinstance(envelope, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise GeneratorError(f"Ollama response from {self.host} contained no content.")

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            raise GeneratorError(
                f"Ollama at {self.host} did not honor the structured output schema."
            ) from None
        if not isinstance(parsed, dict):
            raise GeneratorError(f"Ollama at {self.host} returned an unexpected answer shape.")

        answer = parsed.get("answer")
        citations = parsed.get("citations")
        abstained = parsed.get("abstained")
        if not isinstance(answer, str) or not isinstance(abstained, bool):
            raise GeneratorError(f"Ollama at {self.host} returned an unexpected answer shape.")
        if not isinstance(citations, list) or not all(isinstance(c, str) for c in citations):
            raise GeneratorError(f"Ollama at {self.host} returned unexpected citations.")

        # Preserved exactly as produced, including identifiers that were never
        # retrieved. Filtering here would hide invalid_citation failures.
        return GeneratedAnswer(
            text=answer,
            cited_chunk_ids=tuple(citation.strip() for citation in citations if citation.strip()),
            abstained=abstained,
        )
