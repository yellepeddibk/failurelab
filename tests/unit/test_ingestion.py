from __future__ import annotations

from pathlib import Path

from failurelab.ingestion.jsonl import ingest_jsonl


def test_ingest_skip_invalid(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text(
        '{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00"}\n{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    result = ingest_jsonl(path, strict=False)
    assert len(result.traces) == 1
    assert len(result.issues) == 1
    assert result.issues[0].error_type == "duplicate_id"


def test_ingest_strict_returns_no_traces_on_error(tmp_path: Path) -> None:
    path = tmp_path / "trace.jsonl"
    path.write_text(
        '{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00"}\nnot-json\n',
        encoding="utf-8",
    )
    result = ingest_jsonl(path, strict=True)
    assert result.traces == []
    assert result.issues
