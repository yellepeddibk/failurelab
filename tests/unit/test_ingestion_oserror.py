from __future__ import annotations

from typing import BinaryIO

from failurelab.ingestion.jsonl import ingest_jsonl


class FakePath:
    name = "broken.jsonl"

    def exists(self) -> bool:
        return True

    def is_dir(self) -> bool:
        return False

    def open(self, mode: str) -> BinaryIO:  # pragma: no cover - raises immediately
        raise OSError("permission denied")


def test_ingestion_oserror_branch() -> None:
    result = ingest_jsonl(FakePath(), strict=True)  # type: ignore[arg-type]
    assert result.issues and result.issues[0].error_type == "file_error"
