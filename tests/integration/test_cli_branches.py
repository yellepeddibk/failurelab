from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from failurelab.cli.app import app

runner = CliRunner()


def test_validate_strict_schema_error() -> None:
    result = runner.invoke(app, ["validate", "examples/invalid_traces.jsonl"])
    assert result.exit_code == 3


def test_analyze_mutually_exclusive_flags() -> None:
    result = runner.invoke(
        app,
        ["analyze", "examples/rag_traces.jsonl", "--strict", "--skip-invalid"],
    )
    assert result.exit_code == 2


def test_analyze_bad_config(tmp_path: Path) -> None:
    cfg = tmp_path / "bad.yaml"
    cfg.write_text("evaluation:\n  retrieval_k: 0\n", encoding="utf-8")
    result = runner.invoke(app, ["analyze", "examples/rag_traces.jsonl", "--config", str(cfg)])
    assert result.exit_code == 2


def test_analyze_collision_file_error(tmp_path: Path) -> None:
    out = tmp_path / "reports"
    out.mkdir()
    (out / "metrics.json").write_text("{}", encoding="utf-8")
    result = runner.invoke(
        app,
        ["analyze", "examples/rag_traces.jsonl", "--output", str(out)],
    )
    assert result.exit_code == 4


def test_compare_invalid_input() -> None:
    result = runner.invoke(
        app,
        ["compare", "examples/invalid_traces.jsonl", "examples/candidate_traces.jsonl"],
    )
    assert result.exit_code == 3
