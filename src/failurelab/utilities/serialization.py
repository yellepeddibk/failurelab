"""Deterministic serialization helpers."""

from __future__ import annotations

import json
import math
from typing import Any


def ensure_json_serializable(value: Any) -> Any:
    """Ensure nested values are JSON serializable and finite where numeric."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("floating point values must be finite")
        return value
    if isinstance(value, list):
        return [ensure_json_serializable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): ensure_json_serializable(item) for key, item in sorted(value.items())}
    raise ValueError(f"value of type {type(value)!r} is not JSON serializable")


def stable_dumps(value: Any) -> str:
    """Stable JSON serialization without NaN."""
    return json.dumps(
        ensure_json_serializable(value), sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
