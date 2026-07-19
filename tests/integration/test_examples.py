from __future__ import annotations

import subprocess
import sys
from pathlib import Path

EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"

ANALYSIS_FILES = (
    "metrics.json",
    "findings.json",
    "report.md",
    "regression_tests.yaml",
    "run_manifest.json",
)
COMPARISON_FILES = ("comparison.json", "comparison.md", "gate_result.json")


def _run(script: str, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(EXAMPLES_DIR / script), *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def test_analyze_in_memory_example_runs_and_writes(tmp_path: Path) -> None:
    # Foreign cwd confirms the example needs no repository files.
    out = tmp_path / "analysis"
    result = _run("analyze_in_memory.py", tmp_path, "--output", str(out))
    assert result.returncode == 0, result.stderr
    assert "failure_rate=" in result.stdout
    for name in ANALYSIS_FILES:
        assert (out / name).is_file(), name


def test_analyze_from_jsonl_example_runs_and_writes(tmp_path: Path) -> None:
    # Foreign cwd confirms fixtures resolve relative to the script.
    out = tmp_path / "reports"
    result = _run("analyze_from_jsonl.py", tmp_path, "--output", str(out))
    assert result.returncode == 0, result.stderr
    assert "gate_status=" in result.stdout
    for name in ANALYSIS_FILES:
        assert (out / "analysis" / name).is_file(), name
    for name in COMPARISON_FILES:
        assert (out / "comparison" / name).is_file(), name
