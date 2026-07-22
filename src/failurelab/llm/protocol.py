"""Vendor-neutral provider protocol for interpretation.

No provider SDK is imported here. Real adapters (a local Ollama adapter, then a
cloud adapter) implement this protocol in later releases and ship behind their
own optional extras. The protocol, request, and response types stay
provider-neutral so no vendor type leaks into the public API.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class InterpretationRequest:
    """A single, self-contained generation request.

    ``evidence`` is the structured, privacy-filtered deterministic evidence.
    ``parameters`` carries execution bounds (max output tokens, timeout) that an
    adapter must honor. There is no conversation state and no follow-up.
    """

    system: str
    evidence: Mapping[str, object]
    parameters: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class ProviderResponse:
    text: str
    model: str
    token_usage: Mapping[str, int] | None = None


@runtime_checkable
class InterpretationProvider(Protocol):
    """Produces exactly one response for one request. No agent loop."""

    name: str

    def generate(self, request: InterpretationRequest) -> ProviderResponse: ...
