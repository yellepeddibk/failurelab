"""FailureLab: deterministic AI reliability analysis for RAG and agent traces.

The names exported here, together with the result types documented at their
submodule paths, are the supported public API. Other modules are internal.
"""

from __future__ import annotations

from failurelab._version import __version__
from failurelab.api import analyze, compare, validate
from failurelab.config.settings import FailureLabConfig, load_config
from failurelab.exceptions import ConfigError, FailureLabError, InvalidTraceDataError
from failurelab.models.trace import AgentStep, TraceRecord
from failurelab.reports.models import AnalysisReport, ComparisonReport, ValidationReport

__all__ = [
    "AgentStep",
    "AnalysisReport",
    "ComparisonReport",
    "ConfigError",
    "FailureLabConfig",
    "FailureLabError",
    "InvalidTraceDataError",
    "TraceRecord",
    "ValidationReport",
    "__version__",
    "analyze",
    "compare",
    "load_config",
    "validate",
]
