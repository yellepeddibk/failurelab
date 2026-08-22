"""Contract tests for the shared interpretation response schema.

The structural test always runs. The canonical-form test runs only when the
optional Anthropic extra is installed, so core CI stays dependency-free.
"""

from __future__ import annotations

from typing import Any

import pytest

from failurelab.llm.schema import RESPONSE_SCHEMA


def _objects(node: Any, path: str = "root") -> list[tuple[str, dict[str, Any]]]:
    """Every subschema with type 'object', paired with where it lives."""
    found: list[tuple[str, dict[str, Any]]] = []
    if isinstance(node, dict):
        if node.get("type") == "object":
            found.append((path, node))
        for key, value in node.items():
            found.extend(_objects(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_objects(value, f"{path}[{index}]"))
    return found


def test_every_object_forbids_additional_properties() -> None:
    """Hosted structured-output APIs reject a schema that omits this.

    Regression test: omitting it produced an HTTP 400 from the Messages API on
    the first real call, which mocked tests could not have caught.
    """
    offenders = [
        path
        for path, schema in _objects(RESPONSE_SCHEMA)
        if schema.get("additionalProperties") is not False
    ]
    assert offenders == [], f"objects missing additionalProperties=false: {offenders}"


def test_schema_declares_the_interpretation_contract() -> None:
    assert RESPONSE_SCHEMA["required"] == ["summary", "observations", "caveats"]
    summary = RESPONSE_SCHEMA["properties"]["summary"]
    assert summary["required"] == ["text", "evidence"]  # the summary must be grounded
    observation = RESPONSE_SCHEMA["properties"]["observations"]["items"]
    assert observation["required"] == ["statement", "evidence"]
    assert "confidence" not in observation["required"]  # optional by design


def test_schema_is_already_in_provider_canonical_form() -> None:
    """The SDK's own transformer should have nothing left to change."""
    anthropic = pytest.importorskip("anthropic", reason="requires the [anthropic] extra")
    assert anthropic.transform_schema(RESPONSE_SCHEMA) == RESPONSE_SCHEMA
