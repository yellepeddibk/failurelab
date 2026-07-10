from __future__ import annotations

from pathlib import Path

from failurelab.ingestion.jsonl import ingest_jsonl


def test_invalid_utf8_skip_invalid(tmp_path: Path) -> None:
    path = tmp_path / "bad_utf8.jsonl"
    path.write_bytes(b"\xff\xfe\x00")
    result = ingest_jsonl(path, strict=False)
    assert result.issues
    assert result.issues[0].message == "invalid UTF-8"


def test_comment_strict_stops(tmp_path: Path) -> None:
    path = tmp_path / "comments.jsonl"
    path.write_text(
        '# comment\n{"schema_version":"0.1","trace_id":"a","timestamp":"2026-01-01T00:00:00+00:00"}\n',
        encoding="utf-8",
    )
    result = ingest_jsonl(path, strict=True)
    assert result.traces == []
    assert result.issues and result.issues[0].error_type == "json_error"
