"""Optional interpretation layer.

Everything here is provider-neutral and offline. Real provider adapters ship in
later releases behind their own optional extras. Nothing in this package is
activated by the environment; a caller must construct a provider explicitly and
call ``interpret``.
"""

from __future__ import annotations

from failurelab.llm.errors import (
    InterpretationParseError,
    LLMError,
    MissingLLMDependencyError,
    ProviderError,
    SanitizedProviderError,
)
from failurelab.llm.fake import FakeProvider
from failurelab.llm.interpret import interpret
from failurelab.llm.models import (
    Confidence,
    EvidenceKind,
    EvidenceReference,
    GenerationMetadata,
    InterpretationReport,
    Observation,
)
from failurelab.llm.ollama import OllamaProvider
from failurelab.llm.protocol import (
    InterpretationProvider,
    InterpretationRequest,
    ProviderResponse,
)

__all__ = [
    "Confidence",
    "EvidenceKind",
    "EvidenceReference",
    "FakeProvider",
    "GenerationMetadata",
    "InterpretationParseError",
    "InterpretationProvider",
    "InterpretationReport",
    "InterpretationRequest",
    "LLMError",
    "MissingLLMDependencyError",
    "Observation",
    "OllamaProvider",
    "ProviderError",
    "ProviderResponse",
    "SanitizedProviderError",
    "interpret",
]
