from __future__ import annotations

import json
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
    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["resolved_config"]["ingestion"]["mode"] == "skip_invalid"
    assert manifest["valid_trace_count"] == 1
    assert manifest["invalid_row_count"] == 1


def test_analyze_default_records_strict_mode(tmp_path: Path) -> None:
    path = tmp_path / "mix.jsonl"
    path.write_text(
        '{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00","success":true}\n',
        encoding="utf-8",
    )
    out = tmp_path / "reports"
    result = runner.invoke(app, ["analyze", str(path), "--output", str(out)])
    assert result.exit_code == 0
    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["resolved_config"]["ingestion"]["mode"] == "strict"


def test_cli_override_wins_over_config_file(tmp_path: Path) -> None:
    data = tmp_path / "mix.jsonl"
    data.write_text(
        '{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00","success":true}\nnot-json\n',
        encoding="utf-8",
    )
    cfg = tmp_path / "cfg.yaml"
    cfg.write_text("ingestion:\n  mode: strict\n", encoding="utf-8")
    out = tmp_path / "reports"
    result = runner.invoke(
        app,
        ["analyze", str(data), "--config", str(cfg), "--skip-invalid", "--output", str(out)],
    )
    assert result.exit_code == 0
    manifest = json.loads((out / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["resolved_config"]["ingestion"]["mode"] == "skip_invalid"
    assert manifest["invalid_row_count"] == 1


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
    gate = json.loads((out / "gate_result.json").read_text(encoding="utf-8"))
    assert gate["gate_status"] == "not_configured"
    assert gate["gate_passed"] is None
