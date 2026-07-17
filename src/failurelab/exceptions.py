"""Public exception types for the FailureLab Python API."""

from __future__ import annotations

from failurelab.models.trace import ValidationIssue


class FailureLabError(Exception):
    """Base class for all FailureLab errors."""


class InvalidTraceDataError(FailureLabError):
    """Raised when strict analysis encounters invalid or unusable trace input.

    The full list of validation issues is available on ``issues`` so callers can
    inspect every problem, not only the first.
    """

    def __init__(self, issues: list[ValidationIssue]) -> None:
        self.issues = issues
        first = issues[0] if issues else None
        detail = first.message if first is not None else "invalid trace data"
        super().__init__(detail)


class ConfigError(FailureLabError, ValueError):
    """Raised when configuration cannot be loaded or fails validation.

    Subclasses ``ValueError`` so existing ``except ValueError`` handlers keep
    working.
    """
