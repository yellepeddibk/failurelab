from __future__ import annotations

import pytest
from pydantic import ValidationError

from failurelab.models.trace import ValidationIssue
from failurelab.utilities.serialization import ensure_json_serializable


def test_validation_issue_row_positive() -> None:
    with pytest.raises(ValidationError):
        ValidationIssue(
            row_number=0,
            error_type="json_error",
            message="x",
            input_file="in.jsonl",
        )


def test_serialization_float_and_unsupported_type() -> None:
    assert ensure_json_serializable(1.5) == 1.5
    with pytest.raises(ValueError):
        ensure_json_serializable({1, 2, 3})
