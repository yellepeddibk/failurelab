"""JSON schema for the interpretation response.

This is the response contract for the interpretation layer, not a detail of any
one provider. Every adapter that supports structured output constrains the model
to this exact schema, so the strict parser in ``interpret`` sees the same shape
regardless of which provider produced it.

The schema mirrors what ``interpret`` requires: a grounded summary object, a list
of observations each carrying evidence references, and a list of caveats.

Every object sets ``additionalProperties: false``. Hosted structured-output APIs
require it and reject a schema that omits it, and it is the stricter contract
locally too: the model cannot invent keys the parser would silently ignore.
"""

from __future__ import annotations

from typing import Any

_EVIDENCE_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {"kind": {"type": "string"}, "id": {"type": "string"}},
    "additionalProperties": False,
    "required": ["kind", "id"],
}

RESPONSE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "evidence": {"type": "array", "items": _EVIDENCE_ITEM_SCHEMA},
            },
            "additionalProperties": False,
            "required": ["text", "evidence"],
        },
        "observations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "statement": {"type": "string"},
                    "evidence": {"type": "array", "items": _EVIDENCE_ITEM_SCHEMA},
                    "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
                },
                "additionalProperties": False,
                "required": ["statement", "evidence"],
            },
        },
        "caveats": {"type": "array", "items": {"type": "string"}},
    },
    "additionalProperties": False,
    "required": ["summary", "observations", "caveats"],
}
