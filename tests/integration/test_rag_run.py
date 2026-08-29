"""The example runner must work offline and write where it is told."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from rag_pipeline import run as runner
from rag_pipeline.datasets import DATASETS


def test_list_prints_every_dataset(capsys: pytest.CaptureFixture[str]) -> None:
    assert runner.main(["--list"]) == 0
    printed = capsys.readouterr().out
    for spec in DATASETS:
        assert spec.filename in printed


def test_scripted_run_writes_requested_datasets(tmp_path: Path) -> None:
    assert runner.main(["--output", str(tmp_path), "--dataset", "rag_v1.jsonl"]) == 0
    written = tmp_path / "rag_v1.jsonl"
    assert written.exists()
    rows = [json.loads(line) for line in written.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 32
    assert all("retrieved_context" not in row for row in rows)


def test_scripted_run_reproduces_the_committed_dataset(tmp_path: Path) -> None:
    runner.main(["--output", str(tmp_path), "--dataset", "rag_v1.jsonl"])
    committed = (runner.Path(__file__).resolve().parents[2] / "examples" / "rag_pipeline").joinpath(
        "data", "rag_v1.jsonl"
    )
    assert (tmp_path / "rag_v1.jsonl").read_bytes() == committed.read_bytes()


def test_include_context_is_opt_in(tmp_path: Path) -> None:
    runner.main(["--output", str(tmp_path), "--dataset", "rag_v1.jsonl", "--include-context"])
    rows = [
        json.loads(line)
        for line in (tmp_path / "rag_v1.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert any("retrieved_context" in row for row in rows)


def test_ollama_requires_a_model(tmp_path: Path) -> None:
    """The live path must not silently fall back to a default model."""
    with pytest.raises(SystemExit):
        runner.main(["--output", str(tmp_path), "--generator", "ollama"])


def test_default_run_writes_nothing_into_the_repository(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert runner.main(["--dataset", "rag_abstention.jsonl"]) == 0
    assert "temporary directory" in capsys.readouterr().out
