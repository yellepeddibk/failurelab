from __future__ import annotations

from pathlib import Path

from failurelab.ingestion.jsonl import ingest_jsonl


def test_ingestion_handles_bom_and_blank_and_comments(tmp_path: Path) -> None:
    path = tmp_path / "bom.jsonl"
    path.write_bytes(
        b"\xef\xbb\xbf"
        + b'{"schema_version":"0.1","trace_id":"t1","timestamp":"2026-01-01T00:00:00+00:00"}\r\n\r\n# nope\n'
    )
    result = ingest_jsonl(path, strict=False)
    assert len(result.traces) == 1
    assert len(result.issues) == 1


def test_ingestion_file_and_directory_errors(tmp_path: Path) -> None:
    missing = ingest_jsonl(tmp_path / "missing.jsonl", strict=True)
    assert missing.issues and missing.issues[0].error_type == "file_error"

    directory = tmp_path / "dir"
    directory.mkdir()
    as_dir = ingest_jsonl(directory, strict=True)
    assert as_dir.issues and as_dir.issues[0].error_type == "file_error"
