from __future__ import annotations

from typer.testing import CliRunner

from failurelab.cli.app import app

runner = CliRunner()


def test_version_and_help() -> None:
    version = runner.invoke(app, ["--version"])
    assert version.exit_code == 0
    help_result = runner.invoke(app, ["--help"])
    assert help_result.exit_code == 0


def test_validate_missing_file() -> None:
    result = runner.invoke(app, ["validate", "missing.jsonl"])
    assert result.exit_code == 4


def test_analyze_strict_invalid() -> None:
    result = runner.invoke(
        app,
        [
            "analyze",
            "examples/mixed_traces.jsonl",
            "--strict",
            "--output",
            "reports",
            "--overwrite",
        ],
    )
    assert result.exit_code == 3


def test_compare_fail_on_regression(tmp_path) -> None:
    config = tmp_path / "cfg.yaml"
    config.write_text(
        "gate:\n  max_failure_rate_increase: 0.0\n  max_latency_p95_increase_ms: 0.0\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "compare",
            "examples/baseline_traces.jsonl",
            "examples/candidate_traces.jsonl",
            "--config",
            str(config),
            "--fail-on-regression",
            "--output",
            str(tmp_path / "out"),
            "--overwrite",
        ],
    )
    assert result.exit_code == 10


def test_compare_report_includes_scope_and_deltas(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "compare",
            "examples/baseline_traces.jsonl",
            "examples/candidate_traces.jsonl",
            "--output",
            str(tmp_path / "out"),
            "--overwrite",
        ],
    )
    assert result.exit_code == 0
    report = (tmp_path / "out" / "comparison.md").read_text(encoding="utf-8")
    assert "Gate status: not_configured" in report
    assert "## Full-dataset deltas" in report
    assert "| failure_rate |" in report
