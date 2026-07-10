from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from failurelab.cli.app import app

runner = CliRunner()


def test_validate_success(tmp_path: Path) -> None:
    path = tmp_path / "ok.jsonl"
    path.write_text(
        '{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 0


def test_analyze_skip_invalid(tmp_path: Path) -> None:
    path = tmp_path / "mix.jsonl"
    path.write_text(
        '{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00","success":true}\nnot-json\n',
        encoding="utf-8",
    )
    out = tmp_path / "reports"
    result = runner.invoke(app, ["analyze", str(path), "--skip-invalid", "--output", str(out)])
    assert result.exit_code == 0
    assert (out / "metrics.json").exists()


def test_compare(tmp_path: Path) -> None:
    baseline = tmp_path / "b.jsonl"
    baseline.write_text(
        '{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00","success":true}\n',
        encoding="utf-8",
    )
    candidate = tmp_path / "c.jsonl"
    candidate.write_text(
        '{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00","success":true}\n',
        encoding="utf-8",
    )
    out = tmp_path / "out"
    result = runner.invoke(app, ["compare", str(baseline), str(candidate), "--output", str(out)])
    assert result.exit_code == 0
    assert (out / "comparison.json").exists()
