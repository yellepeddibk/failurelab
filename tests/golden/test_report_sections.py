from __future__ import annotations

from failurelab.discovery.slices import FailureSlice
from failurelab.evals.metrics import MetricResult
from failurelab.regression.generator import RegressionBundle
from failurelab.reports.writers import render_markdown_report
from failurelab.root_cause.analyzer import RootCauseHypothesis


def test_markdown_sections_present() -> None:
    markdown = render_markdown_report(
        metrics=[MetricResult("failure_rate", 0.5, "", 1, 0, 1, 2, "ratio", "lower_is_better")],
        findings=[
            FailureSlice(
                "model", "m", 2, 2, 1, 0.5, 0.4, 0.1, 1.25, None, None, None, ["t1"], ["x"], "next"
            )
        ],
        hypotheses=[RootCauseHypothesis("t1", "retrieval_failure", "high", "RC001", ["e"], ["l"])],
        regression_bundle=RegressionBundle(tests=[]),
        issues=[],
    )
    assert "## 1. Run overview" in markdown
    assert "## 14. Recommended next steps" in markdown
