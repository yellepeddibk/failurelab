from __future__ import annotations

import failurelab
from failurelab import (
    AnalysisReport,
    ComparisonReport,
    FailureLabConfig,
    TraceRecord,
    ValidationReport,
    __version__,
    analyze,
    compare,
    validate,
)


def test_version_present() -> None:
    assert __version__ == "0.3.0.dev0"


def test_public_api_surface() -> None:
    for name in (
        "analyze",
        "compare",
        "validate",
        "load_config",
        "AnalysisReport",
        "ComparisonReport",
        "ValidationReport",
        "FailureLabConfig",
        "TraceRecord",
        "AgentStep",
        "FailureLabError",
        "InvalidTraceDataError",
        "ConfigError",
    ):
        assert name in failurelab.__all__
        assert hasattr(failurelab, name)
    assert callable(analyze)
    assert callable(compare)
    assert callable(validate)
    assert AnalysisReport is not None
    assert ComparisonReport is not None
    assert ValidationReport is not None
    assert FailureLabConfig is not None
    assert TraceRecord is not None
