"""Exceptions for the optional interpretation layer."""

from __future__ import annotations

from failurelab.exceptions import FailureLabError


class LLMError(FailureLabError):
    """Base class for interpretation-layer errors."""


class MissingLLMDependencyError(LLMError):
    """Raised when a provider adapter's optional dependency is not installed."""


class ProviderError(LLMError):
    """Raised when an interpretation provider fails to generate a response."""


class SanitizedProviderError(ProviderError):
    """A provider error whose message is guaranteed safe to show a user.

    Only adapters that deliberately construct credential-free, body-free
    messages may raise this. ``interpret`` passes it through unchanged; every
    other provider exception is replaced with a generic message so an adapter
    cannot leak secrets by raising a plain ``ProviderError``.
    """


class InterpretationParseError(LLMError):
    """Raised when a provider response does not match the required schema."""
