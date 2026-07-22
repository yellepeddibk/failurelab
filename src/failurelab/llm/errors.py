"""Exceptions for the optional interpretation layer."""

from __future__ import annotations

from failurelab.exceptions import FailureLabError


class LLMError(FailureLabError):
    """Base class for interpretation-layer errors."""


class MissingLLMDependencyError(LLMError):
    """Raised when a provider adapter's optional dependency is not installed."""


class ProviderError(LLMError):
    """Raised when an interpretation provider fails to generate a response."""


class InterpretationParseError(LLMError):
    """Raised when a provider response does not match the required schema."""
